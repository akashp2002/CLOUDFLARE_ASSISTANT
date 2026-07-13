---
title: Scaling Security Insights: how we achieved a 10x increase in global scanning capacity
url: https://blog.cloudflare.com/scaling-security-scans/
date: 2026-06-12
---

__Security Insights__ provides actionable security recommendations for every Cloudflare account. To find these insights, we perform regular scans for all accounts, zones, and DNS records, looking for potential security risks and misconfigurations.

However, two key issues emerged. First, our scans were too infrequent. Scans were only being performed every week or two, and therefore newly introduced security risks could remain undetected for up to two weeks. Second, automatic scanning was opt-in for many free plan accounts – meaning lots of accounts weren’t being scanned at all.

The risks of infrequent or nonexistent scans are rising: as automated attacks accelerate, the window for detecting security misconfigurations is shrinking. Making sure that we’re finding these issues for *all* of our customers is crucial to our aim of building a better Internet for everyone.

We calculated that to increase our scanning frequencies and enable automatic scanning for all accounts, we would need to increase our scanning throughput by around 10x on average – from 10 scans per second to 100 per second. But our system was already struggling with its load: millions of events were filling up our backlog waiting to be processed; our API was frequently timing out; our processes were crashing. We needed to fix our system, and we needed to make it *scale*.

This is the story of how we increased scanning throughput for Security Insights by more than 10x, enabled security insights for millions of customers, and doubled our scanning frequency for all customers. Read on to find out how we achieved these improvements.

    
## How we scan for security insights

      
        
      
     
    At a high level, our automatic security scans are triggered by a scheduler. When an account or zone is due for a scan, the scheduler publishes a message (or messages) to __Apache Kafka__, an open-source distributed event streaming platform. These messages fan out to a number of checkers: specialized Go microservices that scan specific assets or configurations.

For every message, each checker sends its results (the security insights that it found) to our internal API, which then persists these in a Postgres database.

          
    
    
    
    Apache Kafka is not strictly a *queue*: it is a partitioned event stream (though recently gained __queue semantics__). Within a partition, messages must be consumed and *processed* in order. This differs from typical queues where messages may be consumed in order but are processed out-of-order. As a result, we can only have one active consumer per partition within a *consumer group*.

This has two consequences for us:

- Messages that are slow to process block the consumer from progressing to the next message 
- For each checker, we can only have as many consumers as there are partitions (each checker has its own consumer group) 

We could have tried to scale by adding more partitions. However, this would have increased resource usage for the Kafka broker itself, which is shared by many other services. We reserved this as a last resort, aiming to improve our code and architecture first.

    
### Introducing parallel processing

      
        
      
     
    Although we can only consume messages in order, there is nothing stopping us from consuming multiple messages at once.

We changed our checkers to consume messages in *batches*, processing each message in a separate goroutine. The trade-offs are that we’d have more work to re-do if our process crashed midway through a batch, and our memory usage would be slightly increased. In our case, these were both acceptable.

    
### Avoiding head-of-line blocking

      
        
      
     
    Some messages processed by a few of our checkers take much longer to process than others. For example, one account/zone may have far more assets than another. In the worst case, these messages can take minutes or hours to process compared to the average case of seconds or milliseconds.

We opted for a very simple approach: splitting our consumer groups and checkers in two – the ‘slow lane’ and the ‘fast lane’. We could determine quickly whether a message would be slow or fast to process. If the ‘fast lane’ checker encounters a slow message, it skips it.

          This solved the problem: slow messages had the dedicated resources and time to be processed with minimal delay, and fast messages were able to proceed at their regular fast pace.

    
## Optimizing our database queries

      
        
      
     
    Every insight we find gets written to our Postgres database. This is handled by a single API endpoint that our checkers invoke with a list of insights. The implementation looked like this:

            ```
for _, issue := range issues {
	_, err = tx.Exec(ctx, `INSERT INTO table ... VALUES ($1, $2, ...) ON CONFLICT DO UPDATE ...`, ...)
	if err != nil {
		return err
	}
}
```

            The astute reader will notice that for large sets of insights, this code makes a round trip to the database per insight. With a maximum observed size of 500,000, this was half a million round trips, queries, and transactions in a single API call.

We initially tried the gold standard for bulk inserts in Postgres: COPY into a temporary table. However, we found that this approach led to bloat in the Postgres system tables.

We settled on a hybrid approach:

This provided the best of both worlds: reasonably fast inserts for huge sets of insights (seconds), and even faster inserts (milliseconds) for small sets of insights.

    
## Investigating our API timeouts

      
        
      
     
    We noticed several strange behaviours in our internal API as we tried to scale:

- A large number of requests were triggering client-side timeouts 
- Many checkers were spending 20-90% of their processing time on a single API call 
- When triggering a large volume of scans, our throughput would start high and deteriorate 

All of these problems had the same root cause: **latency**.

Our primary database is located in Portland, Oregon. Our API, however, was running active-active in both Portland and Amsterdam. Even at the speed of light, the round-trip latency between Portland and Amsterdam would be 50 milliseconds.

As a result of this latency, database queries from the Amsterdam API instance took much longer, holding connections from our client-side connection pool open. With the large volume of requests that we were making to the API, the connection pool was quickly becoming exhausted, leading to timeouts waiting for a free connection. Our average API call completed in 10 ms in Portland, but almost 3 seconds in Amsterdam!

But why the drop in message throughput? Each checker process gets assigned a set of partitions of the Kafka stream to consume. Our API is load-balanced. Since we hold the connection open throughout the life of the process, some processes had a connection to the Amsterdam API, and others had a connection to the Portland API. The partitions linked to Portland were processed quickly, but the ones consumed by the Amsterdam-bound processes were lagging behind:

          *Kafka lag (number of messages waiting to be processed within a single consumer group) by partition for one of our checkers. Note that we have 30 partitions in this case. Exactly 15 partitions can be seen lagging behind (the lines that reach or approach zero later than around 03/10 03:00). This is because the load balancer splits traffic evenly between our API endpoints.*

This was a simple fix: we switched our API to __active-passive__, ensuring the active API followed our primary database. Our latency problems disappeared overnight.

    
    We’d scaled Kafka. We’d optimised our database queries. We’d fixed our API. However, we still had a problem: we needed to be sure our scans would be roughly uniformly distributed in time. It wasn’t feasible to queue all of our scans at the same time, as our Kafka topic uses a time-based retention policy: the scans would pile up in Kafka, and eventually be deleted before they could be processed.

Our scheduler was not good at uniformly distributing our scans. The number of scans that would be triggered at a given time was spiky and unpredictable. At certain points throughout the week, hundreds of thousands of scans would be triggered within minutes of each other. What was going on?

The scheduler triggers scans on fixed recurring periods. In pseudocode, the scheduler looked like this:

            ```
Loop forever:
    Find accounts where last_scheduled_at + scanning frequency <= now
    For each account:
        Trigger scan for account
        Trigger scan for all zones in the account
        Update last_scheduled_at = now
```

            We quickly noticed that last_scheduled_at was similar for a large number of accounts in our database, which was responsible for some of this unevenness.

However, even with perfectly even distribution, increasing our scanning frequency would have compounded this problem. For example, changing the scanning frequency from every 15 days to every seven days would mean 53% of accounts would suddenly be due for a scan.

There was a further problem with this logic. Some accounts have a very large number of zones. When these accounts were scheduled, there was a cascade of scans for all of their zones. This was saturating our Kafka partitions and leading to delays for scans of much smaller accounts.

To fix these problems, we made three key changes:

- Schedule zones independently of accounts: each zone gets its own last_scheduled_at field. 
- Randomize the last_scheduled_at time for existing accounts and zones. 
- Introduce adaptive rate limiting for scan scheduling. 

Scheduling zones independently was an obvious way to solve the problem of large accounts. Randomizing the last_scheduled_at time (and ensuring that no scans were delayed during this process) allowed us to fix the existing unevenness in our database.

Adaptive rate limiting is slightly more interesting. Rate limiting would allow us to solve the problem of a spike in scans when we change scanning frequencies. For example, if we wanted to increase our scanning frequency to every 7 days, and we had 50 million accounts, then a rate limit of ~83 scans/second would ensure that they were spread out evenly across 7 days.

But what if we added 10 million more accounts? Then, this rate limit would force us to take *8 days *to scan all of these accounts. This is where the *adaptive* part comes in: the rate limit is asynchronously recalculated every half-hour based on the total number of accounts and zones we have, and our scanning frequencies. This ensures we continue scanning on time even if we onboard thousands or millions more accounts and zones.

            ```
func computeRate(free, pro, biz, ent int64) rate.Limit {
   r := float64(free)/freeScanInterval.Seconds() +
      float64(pro)/proScanInterval.Seconds() +
      float64(biz)/bizScanInterval.Seconds() +
      float64(ent)/entScanInterval.Seconds()
   // Guard against zero counts. We always want to schedule at least one scan per second.
   if r < 1 {
      r = 1
   }
   // Increase rate limit beyond the 'perfect' value, to have a buffer in case of any downtime
   // or spikes in load.
   r *= rateLimitBufferFactor
   return rate.Limit(r)
}
```

            
    
    
          *With these fixes, our 7-day moving average throughput per checker over time rose by more than 10x.*

Before these improvements, we were executing around 10 scans per second. The gap between this and our target throughput of 100 scans per second seemed vast. We discussed throwing more resources at the problem, throwing more partitions at our Kafka topic – even throwing out our entire architecture.

But our fixes made all the difference. Today, Security Insights sustains over 120 scans per second during peak scheduling, exceeding our 10x improvement goal. Our internal API is no longer timing out, and our Kafka lag metrics look much healthier. These scalability improvements have allowed us to turn on automatic scanning for *all* free accounts and zones and increase the scanning frequency for all customers:

The improved system stability has given us confidence to build new features that we were previously constrained from creating. We’ve added the ability to perform granular on-demand scans. You can now manually re-scan a Cloudflare account, zone, insight, or insight type.

          *Starting a granular on-demand scan from the *__Security Overview page__* in the Cloudflare dashboard*

The lesson we learned is that it’s crucial to deeply understand the existing system before throwing anything away. By looking closely at our code, SQL queries, logs, and metrics (*especially *metrics!), we were able to increase our capacity without simply adding more pods or partitions. By questioning our assumptions, digging into weird-looking metrics, and refusing to take the easy shortcuts (such as increasing API client-side timeouts), we built a more stable and resilient system.

Throwing more resources at the problem might *sometimes* be the answer, but at Cloudflare, we believe in engineering our way out of problems.

Security Insights scans are enabled by default on all Cloudflare plans. Log in to the __Cloudflare dashboard__ today to review and manage your security insights.