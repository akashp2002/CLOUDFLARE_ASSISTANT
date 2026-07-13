---
title: Your Worker can now have its own cache in front of it
url: https://blog.cloudflare.com/workers-cache/
date: 2026-07-06
---

Today we are launching **Workers Cache**: a __tiered cache__ that sits in front of your Worker, configured by a single line of Wrangler config and the same `Cache-Control` headers you already know.

When Workers Cache is enabled, every __cacheable__ request to your Worker hits Cloudflare's cache first. If there's a fresh cached response, Cloudflare returns it directly — your Worker doesn't run, and you don't pay CPU time for it. On a miss, your Worker runs, and if your response is cacheable, Cloudflare stores it for the next request. The next request from anywhere on Earth can be served straight from cache.

          The whole thing is one config block:

            ```
{
  "name": "my-worker",
  "main": "src/index.ts",
  "compatibility_date": "2026-05-01",
  "cache": {
    "enabled": true
  }
}
```

            After that, you control caching the way HTTP has always wanted you to — by setting headers on your responses:

            ```
return new Response(body, {
  headers: {
    "Cache-Control": "public, max-age=300, stale-while-revalidate=3600",
    "Cache-Tag": "products,product:123",
  },
});
```

            And when content changes, your Worker purges its own cache:

            `await ctx.cache.purge({ tags: ["product:123"] });`

            That's the whole API. There is no zone to configure, no rules engine to set up, no separate cache to provision, and no second product to log into. The Worker's code is the configuration surface, and the cache follows the Worker wherever it runs — on a custom domain, on `workers.dev`, behind a service binding, in a preview, in a __Workers for Platforms__ tenant. One Worker, one cache, configured once.

That's the surface area. There’s a lot underneath: tiered caching across our entire network, full support for __stale-while-revalidate____Vary____ctx.props__

Workers Cache is available today to every Worker on any plan, enabled in Wrangler.

This is the caching API we've always wanted Workers to have. Here's why it took us this long, what becomes possible because of it, and what's coming next.

    
## Why server-rendered apps need a cache in front

      
        
      
     
    When we __introduced Workers in 2017__, the pitch was that you could run code on Cloudflare's network to transform requests on their way to your origin. The Worker sat *in front of* the cache and the origin:

          This was the right model for the use cases we were targeting. If you wanted to add a header to every request, rewrite a URL, do an A/B split, or filter traffic before it reached your origin, putting the Worker in front of the cache and the origin gave you full control over what got cached and what didn't. Customers built incredible things with it.

But the world changed. Workers stopped being a thing you bolted onto an origin and started being *the* origin. Frameworks like __Astro__, __TanStack Start__, __Next.js__, __Remix__, and __SvelteKit__ all ship a Cloudflare adapter that builds your app as a Worker. There's no origin behind them. The Worker *is* the server.

When the Worker is the origin, the original architecture has nothing to cache. Every request runs your code, even when the response would be byte-for-byte identical to the one you returned a second ago. The __Workers runtime is fast enough that this works__ — it routinely handles tens of millions of requests per second without breaking a sweat — but "fast enough to render every request" still costs you latency on every page load and CPU time on every invocation. And on a server-rendered app, every page load is, by definition, a render.

Workers Cache flips the architecture. Cloudflare's cache now sits in front of the Worker:

          On a cache hit, your Worker doesn't run at all. Cloudflare returns the cached response and your CPU billing stays at zero. On a miss, your Worker runs once, populates the cache, and the next request — from anywhere — gets served from cache without invoking your code.

This is what was missing for server-side rendering on Workers. You used to have to choose between two unsatisfying options:

- **Prerender everything at build time**("static site generation"). Fast page loads, but every change requires a full rebuild and redeploy. For a docs site with a few thousand pages, that's 5–10 minutes. For a large e-commerce site, it's worse — and the build runs every single time you touch anything.
 
- **Render every page on every request.**Up-to-date content, but every page load pays the rendering cost and every visitor pays the latency.
 

Workers Cache gives you a third option: server-render on demand, cache the rendered response, refresh it on a time-to-live (__TTL__) you choose. The first request to a new page still renders. Every subsequent request, until the cache expires, is served as if the page were static. When the cache expires, the next request triggers a re-render — and with `stale-while-revalidate`, even that one doesn't wait.

You get the speed of a static site without the build time, and the freshness of server rendering without the cost. No framework-specific machinery like Incremental Static Regeneration. Just HTTP caching, working the way it was designed to work, in front of code that was designed to be the origin.

    
      `stale-while-revalidate` is the part that makes it feel instant

      
        
      
     
    The __stale-while-revalidate__*while it refreshes the response in the background*. Cloudflare __shipped full support for ____stale-while-revalidate____ earlier this year__, and it's the directive that turns "we cache your Worker" into "your Worker's site feels static."

Without it, the first request after a cache entry expires has to wait for the Worker to render the page from scratch. The user sees that latency. With it, the first request after expiration gets the stale page immediately (with a `Cf-Cache-Status: UPDATING` header), and the Worker runs in the background to refill the cache. Every user, including the one who triggered the refresh, gets a cache-speed response.

          In practice, this looks like:

            ```
 export default {
  async fetch(request) {
    const html = await renderPage(request);
    return new Response(html, {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        // Treat as fresh for 5 minutes; serve stale for up to an hour
        // while a background refresh runs.
        "Cache-Control": "public, max-age=300, stale-while-revalidate=3600",
      },
    });
  },
};
```

            The mental model that makes this click:

- **Fresh window**(- `max-age`): Cloudflare serves the cached response. Your Worker doesn't run.
 
- **Stale window**(- `stale-while-revalidate`): Cloudflare serves the cached response. Your Worker runs in the background to refresh it. No user waits.
 
- **Outside both windows**: Cloudflare runs your Worker to generate a fresh response, and the user waits for that one render.
 

You pick the windows. For a product catalog that updates every few minutes, `max-age=300`, `stale-while-revalidate=3600` means visitors basically never wait, and your Worker still runs often enough to keep content fresh. For a blog archive that almost never changes, `max-age=86400`, `stale-while-revalidate=2592000` means your Worker runs once a day per page.

The first request to a brand-new page is the only one that pays the full render cost. After that, the page behaves like static output for visitors, while your Worker still owns how the page gets generated.

    
## One URL, many representations: `Vary` works

      
        
      
     
    Real apps rarely return the same bytes to every client. The same product page might be HTML for a browser and JSON for an API client. The same image might be WebP for clients that support it and JPEG for the ones that don't. The same homepage might come back in English, French, or Japanese depending on the user.

Doing this without a cache is easy — your Worker just reads the request header and returns the right thing. Doing it *with* a cache is where it usually gets ugly. Most caches give you two bad options: cache nothing on URLs that have multiple representations, or cache one representation and serve it to everyone.

Workers Cache supports the standard HTTP `Vary` header, which is the right way to solve this. When your Worker returns a response with `Vary: Accept-Encoding` (or `Accept`, or `Accept-Language`, or any other request header), Cloudflare stores a separate cached variant per distinct combination of those headers — and only returns a variant whose stored values match the incoming request.

            ```
export default {
  async fetch(request) {
    const accept = request.headers.get("Accept") ?? "";
    const wantsWebp = accept.includes("image/webp");
    const body = wantsWebp ? await fetchWebpImage() : await fetchJpegImage();
    return new Response(body, {
      headers: {
        "Content-Type": wantsWebp ? "image/webp" : "image/jpeg",
        "Cache-Control": "public, max-age=3600",
        // Cache a separate variant per distinct Accept header value.
        Vary: "Accept",
      },
    });
  },
};
```

            One URL, two cached variants. A browser that sends `Accept: image/webp,*/*` gets the WebP. A browser that sends `Accept: image/jpeg` gets the JPEG. Both come from cache. Your Worker writes both variants on the first request to each, and then runs zero times for either after that.

This is the well-trodden HTTP standard for content negotiation, and Workers Cache implements it the way __RFC 9110__ and __RFC 9111__ describe. There's no allowlist of what headers you can `Vary` on. You list whatever you need, and Cloudflare keys variants on the verbatim values. The docs go through the __edge cases__ — how to keep variant fan-out under control by normalizing headers in a gateway Worker, why purges invalidate all variants of a URL together, and the one case (`Vary: *`) that disables caching entirely.

    
## This is your Worker's cache, not your zone's

      
        
      
     
    Before we get to what becomes possible with all this, there's a conceptual shift worth naming.

Cloudflare has had a cache forever. It's configured at the zone level: Cache Rules, Page Rules, the cached-file-extensions list, Cache Reserve, Tiered Cache topology, custom cache keys. All of it is set per zone, and historically a Worker had to either fit into that zone's configuration or work around it.

Workers Cache is different. It's **your Worker's cache** — it belongs to the Worker, not to a zone. This has a bunch of consequences that turn out to matter:

- **There is no zone configuration to manage.**Cache Rules, cache level settings, the file-extensions list, Page Rules — none of them apply to Workers Cache. The Worker's- `Cache-Control`headers are the configuration.
 
- **The cache follows the Worker, not the hostname.**A Worker that's bound to- `api.example.com`,- `api.example.net`, and invoked over a service binding shares one cache across all three. A request to- `/users/42`hits the same cached entry regardless of which way in it came.
 
- **The cache works on **- **workers.dev**
- **.**It works in- __preview URLs__(each preview gets its own cache, so testing a change doesn't poison production). It works in- __Workers for Platforms__(each user Worker has its own cache, isolated from the dispatcher and from other tenants). All of these used to be second-class citizens for caching. They aren't anymore.
 
- **Purges are scoped to the Worker’s entrypoint.**When you call- `ctx.cache.purge({ purgeEverything: true })`, you're only purging your Worker entrypoint's cache. No risk of nuking your zone's other content. No risk of one Worker's deploy invalidating another's data.
 

What you configure about caching, you configure in code: which paths get longer TTLs (branch on the path and set a different `max-age`), which requests bypass the cache (return `Cache-Control: private`), how the cache key is shaped (control what gets into `ctx.props`, normalize the URL in a gateway Worker before dispatching). The Worker you already wrote is the configuration surface.

The full docs go deep on this in __Workers Cache: your Worker's cache__.

    
## Two tiers, every Worker, no configuration

      
        
      
     
    Workers Cache is **regionally tiered by default**. There are two layers:

- **A lower tier**in the Cloudflare data center closest to the user. Every data center that receives traffic for your Worker has its own lower-tier cache.
 
- **An upper tier**that aggregates fills across the whole network. There are fewer of these, and every lower tier consults the upper tier on a miss.
 

A request hits the lower tier first. On a hit, the response is served and that's the end of it. On a miss, the lower tier asks the upper tier. On a hit there, the response is returned and also stored in the lower tier on the way back. Only if both tiers miss does your Worker actually run — and the response from that run gets stored in both tiers.

          The reason this matters is that the **first request anywhere in the world** populates the upper tier. Every subsequent request, from any data center, can be served from the upper tier without your Worker running — even if the lower tier at that data center has never seen the request before. Cache hit ratios are dramatically higher than they would be with a single flat cache layer, which is exactly what you want when your Worker is the origin.

This is the same topology that powers __Tiered Cache__ for zones today, except you don't configure it. There is no dialog for "turn on tiered cache for my Worker." Every Worker that has caching enabled gets tiering for free.

If your Worker uses __Smart Placement__, the cache composes cleanly with it: tiers are consulted first, and only if both miss does Smart Placement route execution close to your origin. We have more to say about how those layers interact, including a few rough edges we're __planning to smooth out__, in the docs.

    
## Run your app near the user *and* near the data

      
        
      
     
    There's a recurring tension in web performance that nobody has fully resolved: you want your code to run close to the user (because the round-trip between user and server is on the critical path), and you want your code to run close to the data (because every database query is also a round-trip). Pick one, and the other gets slow.

We've spent years chasing both. Our network puts us __within ~50ms__ of about 95% of the world's Internet users. __Smart Placement__ and __Placement Hints__ let you keep your code close to your data without ever having to think about cloud regions. But until now, the two pieces didn't fully compose. You could do "near the user" or "near the data," and if you wanted both halves of your app to be in the right place at the same time, you had to be a Cloudflare expert. __We knew we could do better.__

Workers Cache is the piece that closes the gap. Because the cache belongs to the Worker (not the zone), and because __service bindings__ and __ctx.exports__

The architecture looks like this:

          - **Worker A**runs near the user. It handles the cheap, latency-sensitive parts of every request: authentication, rate limiting, routing, header normalization, rendering the- __outer "shell"__of an HTML page that doesn't depend on data.
 
- **Worker B**runs near the data, courtesy of Smart Placement or an explicit Placement Hint. It does the heavy work: server-rendering pages that fetch data, reading product catalogs, generating search results, aggregating APIs, expensive transforms.
 
- **Workers Cache sits in front of Worker B.**When Worker A calls Worker B over a service binding, Cloudflare checks Worker B's cache first. On a hit, Worker A receives the response and Worker B doesn't run at all — no data-center hop, no database query, no rendering work.
 

The cache hit path becomes: user → Worker A near the user → cache hit for Worker B → response. The data hop is paid only on a miss. Your hot pages run at the speed of code-in-front-of-the-user, and your cold pages still benefit from running near the data when they do execute.

You don't have to architect anything special to get this. Write your app as two Workers, point one at the other with a service binding, turn caching on in Worker B’s `wrangler.jsonc` file, and you're done.

          
    
## Multi-tenant by default, with `ctx.props`

      
        
      
     
    If you're caching a Worker that returns user-specific data — say, an API that serves different content per logged-in user — you need a way to make sure one user can never see another user's cached response. The standard solution is "don't cache authenticated requests," and Cloudflare's __automatic bypass__ for Authorization headers does exactly that. But "don't cache anything" gives up the entire performance win.

Workers Cache solves this by making the caller's __ctx.props__`ctx.props` with a user ID, tenant ID, or any other identifier, callers with different props get separate cache entries. One user's response can never leak into another user's cache.

            ```
import { WorkerEntrypoint } from "cloudflare:workers";
interface Props { userId: string; }
export default class Backend extends WorkerEntrypoint<Env, Props> {
  async fetch(request: Request): Promise<Response> {
    // ctx.props.userId is part of the cache key. User A and User B
    // requesting the same URL get separate cached entries.
    const { userId } = this.ctx.props;
    const data = await loadUserData(userId);
    return new Response(JSON.stringify(data), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=300",
      },
    });
  }
}
```

            The typical pattern is to authenticate the request in a gateway Worker, strip the `Authorization` header, set the authenticated user's ID into `ctx.props`, and then call the cached backend Worker. The gateway runs on every request (it has to, to authenticate), but the expensive backend only runs when there's no cache entry for that user yet. Auth'd APIs go from "uncacheable" to "cached per user with full safety," and the cache key does the isolation for you. The docs walk through this in detail in __Multi-tenant safety with ctx.props__ and the example in __Per-user authenticated responses__.

Other CDNs make you choose between correctness and hit ratio: key the cache by each user’s token, or send every request back to origin for authorization. Workers Cache lets you share cached API responses at the edge while preserving per-request authorization boundaries. We don’t know of another CDN that offers this as a built-in model for authenticated, multi-tenant APIs. We’re pretty proud of it.

    
## A cache between every Worker entrypoint

      
        
      
     
    Here is the part of Workers Cache that we think is the biggest unlock, and it's the part that's hardest to see if you're thinking about it as "a CDN cache that happens to work in front of Workers."

**Workers Cache sits in front of every Worker entrypoint** — the default export, every named __WorkerEntrypoint____ctx.exports__

When one entrypoint calls another via `ctx.exports`, the cache evaluates that call the same way it would evaluate a request from a browser. A hit returns the cached response and the callee never runs. A miss runs the callee and stores its response under its own cache key — keyed by the callee's entrypoint, path, query string, and `ctx.props`. The caller still runs on every request, but anything it hands off to the callee is memoized independently.

You decide, per entrypoint, which ones cache. In your Wrangler config, the `exports` map lets you turn caching on or off for each entrypoint by name (`"default"` is the default export). Opt an entrypoint **in** to cache the responses it produces; opt one **out** to keep it running on every request. A gateway or router entrypoint — anything that authenticates, normalizes, or dispatches — should be opted out, so it always runs, and its own output is never served from cache.

That gives you a primitive you can compose. You can author a Worker as a chain of small entrypoints — auth, normalization, routing, the expensive read, the data layer — and let Workers Cache slot in wherever you want it. Each cached entrypoint is a unit of memoization with its own key, its own TTL, and its own tag namespace for purging. Anything you would want to configure about caching — when it runs, what it keys on, when it invalidates — is expressed as ordinary Worker code: which entrypoint you call, what request you forward, what `ctx.props` you pass, what `Cache-Control` you set.

To make this concrete, here's a single Worker that does three things you couldn't easily do together on any other platform: it authenticates every request, caches the expensive backend behind a multi-tenant-safe cache key, and invalidates that cache when data changes.

Caching is configured per entrypoint. The gateway must run on every request — both to authenticate and because a cached gateway response would skip that auth check — so we disable caching on the default entrypoint and enable it only on the inner one:

            ```
{
  "name": "my-worker",
  "main": "src/index.ts",
  "compatibility_date": "2026-05-01",
  "cache": { "enabled": true },
  "exports": {
    // The gateway runs on every request — don't cache it.
    "default": { "type": "worker", "cache": { "enabled": false } },
    // Cache the expensive inner entrypoint.
    "CachedBackend": { "type": "worker", "cache": { "enabled": true } }
  }
}
```

            
            ```
import { WorkerEntrypoint } from "cloudflare:workers";
interface Env { API_TOKEN: string; }
interface Props { userId: string; }
// Inner entrypoint: the expensive work. Workers Cache sits in front
// of this — on a hit, this code never runs.
export class CachedBackend extends WorkerEntrypoint<Env, Props> {
  async fetch(request: Request): Promise<Response> {
    // ctx.props.userId is part of the cache key, so this is cached
    // separately for every user.
    const { userId } = this.ctx.props;
    const data = await loadExpensiveData(userId);
    return new Response(JSON.stringify(data), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "public, max-age=300, stale-while-revalidate=3600",
        "Cache-Tag": `user:${userId}`,
      },
    });
  }
  // Invalidate a user's cached response. purge() is scoped to the
  // entrypoint that calls it, so it must run inside CachedBackend —
  // the entrypoint that owns the cached response.
  async invalidate(userId: string): Promise<void> {
    await this.ctx.cache.purge({ tags: [`user:${userId}`] });
  }
}
// Outer entrypoint: runs on every request to authenticate and route.
// Caching is disabled for it in Wrangler config (above), so it always
// runs and the auth check is never skipped by a cache hit.
export default {
  async fetch(request, env, ctx): Promise<Response> {
    const userId = await authenticate(request, env);
    if (!userId) return new Response("Unauthorized", { status: 401 });
    // Invalidate this user's cache on writes, from the entrypoint that
    // owns it.
    if (request.method === "POST") {
      await handleWrite(request, userId);
      await ctx.exports.CachedBackend.invalidate(userId);
      return new Response("OK");
    }
    // For reads: strip Authorization (otherwise Cloudflare's automatic
    // bypass fires and nothing caches), then dispatch to the cached
    // backend with the authenticated user's identity in ctx.props.
    const forwarded = new Request(request);
    forwarded.headers.delete("Authorization");
    return ctx.exports.CachedBackend.fetch(forwarded, {
      props: { userId },
    });
  },
} satisfies ExportedHandler<Env>;
```

            The whole thing is one Worker. One source file. One deploy. But there are two execution stages — caching is turned off for the gateway and on for the backend in one small `exports` block — and a cache sits between them, keyed per user, invalidated by the write path, and serving stale during background refreshes. The cache stage isn't something you bolted on. It's a layer of the program, written in code.

The patterns this composes into are open-ended. The same shape works for:

- **Caching a Durable Object.**Wrap the Durable Object behind an entrypoint, set- `Cache-Control`on the response, and reads stop touching the Durable Object on a hit. Writes go to the DO directly and purge the cache by tag. The DO stays unaware that caching is happening.
 
- **Normalizing **- **Accept-Encoding**
- ** before **- **Vary**
- **.**The outer entrypoint restores the original encoding from- `request.cf.clientAcceptEncoding`(Cloudflare's front line normalizes it for cache efficiency) and forwards to a cached entrypoint that varies on the real value. Hit ratios stay high; clients get the right encoding.
 
- **Stripping tracking parameters before caching.**The outer entrypoint canonicalizes the URL — or sets a- __custom cache key__with- `cf.cacheKey`on the- `ctx.exports`call — so the cached inner entrypoint sees only the canonical form, and- `?utm_source=anything`collapses to a single cache entry.
 

Stack them. A single Worker can have an outer entrypoint that authenticates and routes, a normalization entrypoint that strips tracking parameters and restores encoding headers, a cached entrypoint that fronts a Durable Object, and a separate cached entrypoint for an unauthenticated public API — each connected by a cache stage you didn't configure, just decided where to put. The __Examples page in the docs__ walks through several of these end-to-end.

We don't know of another platform where you can do this. CDN caches sit in front of an origin. Function platforms run functions. We don't know of another platform that gives you a cache that sits inside a single deployable unit, between the parts of your application, with each cache stage configured by the code on either side of it. That's what Workers Cache is. And because it composes with everything else the platform already gives you — Smart Placement, Durable Objects, service bindings, `ctx.props`, `ctx.exports` — the patterns you can build are open-ended. We've barely scratched the surface in this post.

    
## First-class support in your framework

      
        
      
     
    If you're building with Astro, the Cloudflare adapter wires up Workers Cache for you. Just add the __cacheCloudflare provider__ to your configuration:

            ```
// astro.config.mjs
import { defineConfig } from "astro/config";
import cloudflare from "@astrojs/cloudflare";
import { cacheCloudflare } from "@astrojs/cloudflare/cache";
export default defineConfig({
  adapter: cloudflare(),
  output: "server",
  experimental: {
    cache: { provider: cacheCloudflare() },
    routeRules: {
      "/products/*": { maxAge: 300, swr: 3600, tags: ["products"] },
      "/blog/*":     { maxAge: 60,  swr: 86400, tags: ["blog"] },
    },
  },
});
```

            The adapter enables the cache, sets the right headers on the responses Astro generates, attaches `Cache-Tag` values for invalidation, and gives you a `cache.invalidate()` helper for purging tags when content changes. Astro pages that opt into server rendering automatically get the "render once, cache, refresh in the background" flow described above — no per-route configuration required, no framework-specific runtime layer to learn.

We're working with the maintainers of other frameworks to ship the same integration. If you build a framework adapter for Cloudflare, the __Workers Cache APIs__ are exactly what you'd want them to be — header-driven configuration, programmatic purges, no platform-specific concepts to model.

    
## See your cache on the same dashboard as your Worker

      
        
      
     
    Caching is only useful if you can see what it's doing. The __Workers Observability dashboard__ now surfaces cache hit information per invocation:

          You can see, per Worker:

- **Cache hit ratio**over time. The number you want trending up after you enable caching.
 
- **Hits, misses, updates, bypasses**broken down. If your hit ratio is low, this is where you find out why — too many- `BYPASS`responses (because something is setting a cookie?), too many- `MISS`responses (because the cache key is partitioning more than you thought?), too many- `UPDATING`responses (because- `max-age`is shorter than your traffic interval?).
 

Because all of this lives on the same dashboard as your Worker's other observability — logs, exceptions, CPU time, request counts — you don't have to context-switch between looking at your zone and your Worker to understand what's happening.

    
    Cache hits don't run your Worker, and they don't bill CPU time. They do count as a request at the standard __Workers request rate__, the same as any other invocation. Cache misses and bypasses bill normally — request + CPU time, exactly as they would without caching.

| **Outcome**
 | **Request charge**
 | **CPU time charge**
 | 
| Cache `HIT`(Worker does not run) | Standard rate | Not billed | 
| Cache `MISS`(Worker runs) | Standard rate | Billed | 
| Cache `BYPASS`(Worker runs) | Standard rate | Billed | 
| Static asset request | Standard rate | Not billed | 
| Worker-to-worker invocation | Standard rate | Billed if the Worker runs | 

There's no separate Workers Cache SKU and no per-GB cache storage fee. Tiered caching, purges, `stale-while-revalidate`, and the analytics described above are all included.  If a request would have run your Worker and Workers Cache serves it as a hit instead, you still pay the standard request rate, but you pay no CPU time for that request. Because of this, that cache hit costs less than rendering the same response in your Worker.

One thing to watch: when caching is enabled, requests that are normally free — __static asset requests__ and __worker-to-worker invocations__ through service bindings or `ctx.exports` — are billed at the standard request rate, because each one now consults the cache in front of your Worker.

    
    Things we know we want to do next:

- **Smarter co-location with Smart Placement.**Today, Cloudflare chooses the upper-tier cache and Smart Placement target separately. On a full miss, the request may travel between Cloudflare locations twice: once to check the upper tier, and again to run your Worker near its data. We're working to coordinate those choices, so a miss only makes that long-distance trip once.
 
- **Larger response size limits.**At launch, all responses follow the- __Free plan’s cacheable size limit__(512 MB), regardless of your account. That’s temporary — the standard per-plan cache limits will apply once we finish a few rollout steps.
 
- **More framework integrations.**Astro has- __built-in integration with Workers Cache__. We’re working with maintainers to add similar integrations to other frameworks, including- __TanStack Start__and Next.js via- __Vinext__.
 
- **An API to mark cached responses stale. **- `ctx.cache.purge()`removes matching responses from cache. We’re looking at a- `ctx.cache.invalidate()`API that makes matching responses behave as expired, so the next request can still get a fast stale response with stale-while-revalidate while your Worker refreshes the cache in the background.
 

Workers Cache is available today to every Worker on any plan.

To get started, add `"cache": { "enabled": true }` to your `wrangler.jsonc`, redeploy, and start setting `Cache-Control` headers. The __Workers Cache documentation__ walks through the full feature surface — including the __quickstart__, __cache keys__, __purging__, __composition patterns and examples__, and __debugging__.

Workers used to run in front of the cache. Now they can also run behind it. Use whichever side you need — or, with service bindings, both at once.

We can't wait to see what you build.