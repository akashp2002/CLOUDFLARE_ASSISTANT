---
title: How we found a bug in the hyper HTTP library
url: https://blog.cloudflare.com/hyper-bug/
date: 2026-06-22
---

The __Images__ service, built in Rust on __Workers__, runs on every machine in Cloudflare’s edge network. To handle client connections, we use __hyper__, an open-source HTTP library for Rust.

Last year, we __introduced the Images binding__ to enable custom, programmatic workflows for processing remote images in Workers. At the end of 2025, we rearchitected the binding to provide a more direct, local connection between the Workers runtime and the Images service.

Shortly after rollout, we received reports that transformation requests from the binding were failing — but only intermittently and only for larger images. Even stranger, the responses for these requests returned a `200` status without any errors logged. The image data was simply cut short: A response that should have been two megabytes might arrive with a few hundred kilobytes instead.

We spent six weeks chasing a nearly invisible bug — a race condition that occurred only under specific conditions — in the hyper library that impacted how the Images binding returned processed image data back to the client. In the end, it took four lines of code to fix it.

    
### Hops, handoffs, and hyper

      
        
      
     
    When developers build on Cloudflare, they compose full-stack applications from a set of platform services that are accessible to Workers through bindings. __Bindings__ provide direct APIs to resources on the Developer Platform like __compute__, __storage__, __AI inference__, and __media processing__.

The Images binding decouples image optimization from delivery; you can transcode, composite, or manipulate images without needing to return the output as an HTTP response. It also lets you apply __optimization parameters__ in any order, rather than following the fixed sequence imposed by the __URL interface__. Here, a worker can pass image data directly to the Images API, chain operations together, and get the processed result back as a stream:

            ```
const result = await env.IMAGES
  .input(image)
  .transform({ width: 800, rotate: 90 })
  .output({ format: "image/avif" });
return result.response();
```

            At a high level, this is how image data moves through our various services:

          *The pipe represents a socket connection between the intermediary and Images, where data is handed off from one process to the next through the kernel’s buffer.*

The binding communicates with Images through a socket connection managed by the Workers runtime. A socket connection is a communication channel between two processes. Each end of the socket has buffers that are managed by the operating system’s kernel; these buffers are temporary holding areas where data sits after one side writes it but before the other side reads it.

Hyper manages the connection on the Images service’s side, reading incoming requests from the socket and writing responses back to it.

When a request uses the Images binding, the Images service reads the input, performs the requested optimization operations, and encodes the result. It then passes the entire encoded image to hyper as a single in-memory block. 

Hyper writes this response data into its own internal buffer. At this point, hyper considers the encoding work as complete, since it has all the bytes that it needs to send. The next step is to flush its internal buffer to the socket’s outbound buffer, moving the data from the Images service to the intermediary on the other end.

If the reader on the other end is fast, then hyper can flush everything in one pass — the outbound buffer will have room because the reader is consuming data as quickly as it arrives. Once all data is sent, hyper issues a `shutdown` on the socket, signaling that the connection is finished and no more data will be written. But if the reader is slower (even by a few milliseconds), then the outbound buffer fills up, and hyper needs to wait until there’s room to continue writing.

    
    All incoming traffic on Cloudflare's network passes through FL, an internal intermediary service that runs security and performance features and routes requests to the appropriate backend. When we first launched the binding, image data flowed from the Workers runtime, through FL, to the Images service.

This path was a natural fit for our initial release and follows the same architecture as our URL interface. Over time, though, this coupling with FL became a constraint: Every change to the binding had to follow FL’s release cycle.

In December 2025, the Images team replaced FL with a new intermediary service, an internal worker binding that runs on the same machine. In the original architecture, data moved through FL over network sockets; this path carried the overhead of FL’s full processing pipeline, such as DNS lookups and routing.

The internal binding replaced these with Unix sockets to directly connect the services on the same machine, bypassing FL and the overhead of the network stack. This made the request path to Images faster and gave the team independent control over binding releases.

Within days of the rollout, we received our first customer report.

    
    The first sign of trouble came from a customer with a non-standard setup: two layers of image processing, where one pipeline was nested inside another.

First, their worker used the Images binding to composite multiple large source images from R2 — a JPEG background plus PNG overlay layers — into a single combined JPEG. Second, they further compressed, transcoded, and resized the result through the URL interface.

          *The bug originated in the inner pipeline’s return path, where the response was truncated before reaching the outer pipeline.*

The inner pipeline (transformation binding) handled compositing. The outer pipeline (transformation URL) handled delivery optimizations like scaling and format conversion. This layered approach meant that when the inner pipeline silently returned a truncated response, the only visible error appeared one level up:

            `error reading a body from connection: end of file before message length reached`

            The outer pipeline received HTTP `200` from the inner one, with a `Content-Length` header that promised several megabytes. The actual body was only a fraction of that: In one request, only ~200 KB arrived out of an expected 3.3 MB. The error surfaced in the outer pipeline, but the truncation could have originated in the binding, the intermediary service, the Images service, or somewhere in between.

When a browser receives a truncated image, the result is visible. Depending on the format, the image either renders partially (e.g., with the bottom half missing or gray) or fails to decode entirely, instead displaying a broken image.

    
    From here, we worked inward through the request path, testing each layer to isolate where the truncation was happening. Some of these efforts hit dead ends; others left breadcrumbs that narrowed the search:

- **Building a reproduction.**We built a worker that mimicked the customer’s nested setup, then stripped away layers until we could trigger the bug with the binding alone. A small script let us fire requests in batches. In one early run, 19 out of 25 requests failed. The amount of data that did arrive — roughly 200 KB — was suspiciously close to the size of the socket buffer in production. This confirmed that the problem wasn’t tied to the customer’s configuration and gave us a reliable way to trigger the bug on demand.
 
- **Investigating timeouts.**Early on, we suspected the truncation might be related to timeout behavior (i.e., the connection was being closed after a time limit). This theory didn’t hold, as the truncation wasn’t correlated with request duration.
 
- **Updating hyper version.**When the bug was first reported, we were running 0.14.x, while the latest hyper version was around 1.8.x. We tested across hyper versions 0.14, 1.7, and 1.8, just in case the most obvious answer was the correct (and easiest) one. But the bug appeared in each version, which meant that there wasn’t an upstream fix.
 
- **Reproducing locally.**We ran local integration tests on macOS and a Debian VM. Even under considerable load, our local requests never triggered any failure. Making direct curl requests to the binding socket and replaying captured requests always seemed to work. The bug only appeared on the full production path when there was real concurrency and a real Workers runtime client on the other end of the socket. This led us to suspect the runtime itself.
 
- **Ruling out the Workers runtime.**We examined the HTTP client that the Workers runtime uses to communicate with Images through the binding socket. None of the traces from either side of the connection showed any syscalls that indicated an unexpected close or early termination. We observed that the client behaved correctly and multiple other services used the same client without issues.
 
- **Distributed tracing.**By inspecting request traces end-to-end, we confirmed that the truncated body was already present before it reached the outer transformation layer in the customer’s setup. That narrowed the problem to the inner pipeline — the binding path through the Images service.
 
- **Instrumenting the intermediary service.**We added instrumentation to the intermediary service to measure body sizes before forwarding the response data. The bodies were already truncated by the time they left the Images service, so the intermediary was ruled out.
 
- **Deeper tracing within the Images service.**At the service level, the request was processed, the image was properly encoded, and the response was sent with HTTP- `200`.
 

The only consistent signal was that the bug was timing-dependent: It appeared only on the production path, with real concurrency, and only for larger images.

    
    Tools for application-level debugging told only what the system thought it was doing. But according to the system, everything was fine: Tracing said the response was sent; logging reported no errors, and the Images service returned `200` on every request.

To see what the system was actually doing, we attached `strace` to the Images service. `strace` records the syscalls that a process makes to the kernel, which could show us exactly which bytes were written, when a shutdown was called, and whether the client sent any termination signal.

Setting up the trace was delicate. `strace` works by intercepting syscalls as they happen, which adds a small amount of timing overhead to each one. Filtering for a narrow set of syscalls kept that overhead minimal. Broadening the filter, however, slowed the process just enough to shift the timing between the flush and the shutdown check — and make the bug disappear entirely. That alone reinforced our theory that the issue was timing-sensitive.

Using a reproduction worker, we triggered the bug and compared the syscall output between successful and failing requests.

In a successful request, the response is written in chunks as the socket buffer allows, with shutdown called only after all the data is sent. For example, this may look like:

            ```
sendto(42, "HTTP/1.1 200 OK\r\nContent-Length: 14991808\r\n...", ...) = 219264
sendto(42, "\xff\xd8\xff\xe0...", 292352) = 292352
// ... keeps writing until buffer drains ...
sendto(42, "...", 292352) = 292352
shutdown(42, SHUT_WR) = 0
```

            When we reproduced the bug, a failing request looked like:

            ```
sendto(42, "HTTP/1.1 200 OK\r\nContent-Length: 14991808\r\n...", ...) = 219264
shutdown(42, SHUT_WR) = 0
```

            Here, there is only one write — just enough for the headers and a sliver of the body — before the shutdown is immediately called. Out of a 14.9 MB response, only about 219 KB was sent. The remaining ~14.8 MB of image data never left hyper’s internal buffer, nor was there any termination signal from the client between the write and the shutdown. Instead, the Images service prematurely shut down the connection on its own, genuinely believing it was finished.

The failing requests confirmed that the bug was a race condition that triggered intermittently. Whether a request succeeded or failed depended on whether the flush and shutdown operations overlapped, which changed from request to request. When the buffer was still full at the exact moment that hyper decided the connection was finished, data was lost.

          *When the reader consumes slower than hyper writes, the outbound buffer fills up. If hyper shuts down the connection before the buffer drains, then only a fraction of the response makes it to the intermediary; this incomplete data gets forwarded back to the Workers runtime and the client.*

The December rearchitecture didn't introduce this bug, which had been present in hyper for years across multiple major versions. But the new intermediary changed who was reading on the response side of the socket. Our working theory is that FL, the previous intermediary, consumed data fast enough that the socket buffer rarely filled during a response. The new reader read at a pace that occasionally let the buffer fill during larger responses.

These few milliseconds of backpressure, introduced by an improvement that made everything else faster, were all it took to surface a flaw that had been hiding in plain sight.

    
    Hyper's HTTP/1 connection lifecycle is driven by a state machine in a file called `dispatch.rs`. It runs a loop that reads requests, writes responses, flushes the write buffer to the socket, and decides when to shut down. In simplified form:

            ```
fn poll_loop(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), Error>> {
    loop {
        let _ = self.poll_read(cx)?;
        let _ = self.poll_write(cx)?;
        let _ = self.poll_flush(cx)?;
        if !self.conn.wants_read_again() {
            return Poll::Ready(Ok(()));
        }
    }
}
```

            More precisely, the `let _` before `poll_flush` is where the bug lives.

In Rust, `let _ = expr` discards the expression's result, including `Poll::Pending`, the signal that the flush isn’t done yet. The flush might still have megabytes sitting in its buffer, but the loop never finds out.

When a request fails, this is the exact sequence of events:

- The Images service finishes encoding the image and hands the entire response to hyper as a single in-memory block. 
- Hyper writes the block into its internal buffer and marks its write state as - `Writing::Closed`. From an encoding standpoint, the work is done — there is nothing left to encode.
 
- Hyper calls - `poll_flush`to move the buffered data to the socket. In our previous example, the socket accepted about 219 KB. The remaining ~14.8 MB stays in hyper's buffer. The socket is full, so the kernel returns- `Poll::Pending`.
 
- `poll_loop`discards the- `Poll::Pending`with- `let _`.
 
- It checks - `wants_read_again()`. The full request was already received, so this returns- `false`.
 
- `poll_loop`returns- `Poll::Ready(Ok(()))`, signaling that the loop is finished, even though the flush is not.
 
- `poll_shutdown()`fires. The- `SHUT_WR`syscall is issued.
 
- The client receives 219 KB and an EOF (end-of-file) indicating that the connection is closed, even though it expects 14.9 MB. 

In the second step, hyper marks the write operation as complete as soon as the response body is buffered (i.e., when encoding is finished), rather than when it has actually been flushed. Most of the time, the flush completes in a single pass and this distinction is invisible. On the rare occasions when the socket buffer is full, the flush has to wait — even though hyper doesn't. The bytes are still sitting in hyper’s buffer, waiting to be flushed to the socket. Hyper proceeds to shut down the connection with this data still in the buffer.

This also explains why curl never triggered the bug. Curl reads data as fast as it arrives: The socket buffer never fills, the flush always completes immediately, and the discarded return value is harmless. The production path, with a reader that occasionally paused for a few milliseconds, was the only configuration where the buffer filled at exactly the wrong moment.

    
    After weeks of investigation, the fix itself was conceptually simple. Hyper needed to check whether the flush was actually done before moving on.

Our reproduction worker confirmed that the bug existed, but it couldn't tell us why a given request failed. Before writing the fix, we needed a test that could trigger the exact socket conditions inside hyper.

We knew the conditions that triggered the bug: a socket that accepts one chunk of data and then blocks. To test with a controlled scenario, we built a custom wrapper around a TCP stream that simulated a full socket buffer. The wrapper accepted 8 KB on the first write, then returned `Poll::Pending` on every subsequent write, mimicking a reader that stopped draining the buffer.

The test sent a 500 KB response through this constrained socket and checked whether hyper called shutdown while 492 KB was still buffered. Without a fix, it did. With the fix, it waited.

Initially, we applied the fix in hyper’s dispatch loop. Instead of discarding the result of `poll_flush`, we checked to see whether the flush was actually done:

            ```
let flush_result = self.poll_flush(cx)?;
if flush_result.is_pending() {
    return Poll::Pending;
}
if !self.conn.wants_read_again() {
    return Poll::Ready(Ok(()));
}
```

            If the flush hasn't completed, then the loop returns `Poll::Pending` to the asynchronous runtime. The runtime waits for the socket to become writable, then wakes the task back up to continue the flush. The connection shuts down only after all data has been sent.

When we deployed this fix, we observed that every byte was written and the shutdown was called only after the buffer was actually empty. The customer who made the first report also confirmed that the issue disappeared.

While our initial solution worked, the dispatch loop wasn’t the right place for the fix. Returning `Poll::Pending` early could slow down other operations on the same connection by reducing how frequently reads are polled, causing unintended backpressure. It also doesn't correctly handle keepalive connections, where a single connection handles multiple requests in sequence — these should remain reusable even while the previous response is still being flushed. Neither issue affected our particular service (where keepalive is disabled), but both could affect other hyper users if the fix were contributed upstream.

We traced through hyper's connection lifecycle and found a more targeted approach. Rather than changing how the dispatch loop behaves, we applied the fix at the point where shutdown is actually called. Before shutting down the socket, hyper should first flush any remaining data in its buffer:

            ```
pub(crate) fn poll_shutdown(
    &mut self,
    cx: &mut Context<'_>,
) -> Poll<io::Result<()>> {
    ready!(self.poll_flush(cx)?);
    Pin::new(&mut self.io).poll_shutdown(cx)
}
```

            This leaves the dispatch loop unchanged. It adds a flush only at the exact point where data loss would otherwise occur — the moment before shutdown.

    
    None of the tools at the application level surfaced any errors, crashes, or log entries that provided useful clues. Application-level observability can have a blind spot for bugs that live below its awareness.

The failure occurred intermittently, scaled with response size, couldn’t be reproduced with simple tools like curl, and disappeared when we observed the system more closely. These signals pointed to a timing-dependent bug in the connection layer, not in the application logic.

Our breakthrough came from using kernel-level tooling with `strace`, the one layer that records what actually happened on the socket. The underlying bug lived in the few milliseconds between a partial flush and a premature shutdown — a window that opened only after we made the system faster.

We merged our fix and the deterministic test into `hyperium/hyper` via __PR #4018__. It will be available in a future hyper release, ensuring that any service using hyper’s HTTP/1 implementation won’t lose response data to the same race condition.

In the meantime, we’re running an internal fork with the patch applied. This fix stabilized the binding’s architecture, creating a reliable foundation to expand its functionality.

The Images binding initially covered only transformations of remote images. Earlier this month, we announced that __the Images binding now supports operations for hosted images__, giving developers a unified way to build media-rich applications on Cloudflare.

Read more about how the binding works in __our documentation__.