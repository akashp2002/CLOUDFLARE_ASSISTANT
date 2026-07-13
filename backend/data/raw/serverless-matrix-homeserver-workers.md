---
title: Building a serverless, post-quantum Matrix homeserver
url: https://blog.cloudflare.com/serverless-matrix-homeserver-workers/
date: 2026-01-27
---

** This post was updated at 11:45 a.m. Pacific time to clarify that the use case described here is a proof of concept and a personal project. Some sections have been updated for clarity.*

Matrix is the gold standard for decentralized, end-to-end encrypted communication. It powers government messaging systems, open-source communities, and privacy-focused organizations worldwide. 

For the individual developer, however, the appeal is often closer to home: bridging fragmented chat networks (like Discord and Slack) into a single inbox, or simply ensuring your conversation history lives on infrastructure you control. Functionally, Matrix operates as a decentralized, eventually consistent state machine. Instead of a central server pushing updates, homeservers exchange signed JSON events over HTTP, using a conflict resolution algorithm to merge these streams into a unified view of the room's history.

**But there is a "tax" to running it. **Traditionally, operating a Matrix __homeserver__ has meant accepting a heavy operational burden. You have to provision virtual private servers (VPS), tune PostgreSQL for heavy write loads, manage Redis for caching, configure __reverse proxies__, and handle rotation for TLS certificates. It’s a stateful, heavy beast that demands to be fed time and money, whether you’re using it a lot or a little.

We wanted to see if we could eliminate that tax entirely.

**Spoiler: We could.** In this post, we’ll explain how we ported a Matrix homeserver to __Cloudflare Workers__. The resulting proof of concept is a serverless architecture where operations disappear, costs scale to zero when idle, and every connection is protected by __post-quantum cryptography__ by default. You can view the source code and __deploy your own instance directly from Github__.

    
    Our starting point was __Synapse__, the Python-based reference Matrix homeserver designed for traditional deployments. PostgreSQL for persistence, Redis for caching, filesystem for media.

Porting it to Workers meant questioning every storage assumption we’d taken for granted.

The challenge was storage. Traditional homeservers assume strong consistency via a central SQL database. Cloudflare __Durable Objects__ offers a powerful alternative. This primitive gives us the strong consistency and atomicity required for Matrix state resolution, while still allowing the application to run at the edge.

We ported the core Matrix protocol logic — event authorization, room state resolution, cryptographic verification — in TypeScript using the Hono framework. D1 replaces PostgreSQL, KV replaces Redis, R2 replaces the filesystem, and Durable Objects handle real-time coordination.

Here’s how the mapping worked out:

          
    
## From monolith to serverless

      
        
      
     
    Moving to Cloudflare Workers brings several advantages for a developer: simple deployment, lower costs, low latency, and built-in security.

**Easy deployment: **A traditional Matrix deployment requires server provisioning, PostgreSQL administration, Redis cluster management, TLS certificate renewal, load balancer configuration, monitoring infrastructure, and on-call rotations.

With Workers, deployment is simply: wrangler deploy. Workers handles TLS, load balancing, DDoS protection, and global distribution. 

**Usage-based costs: **Traditional homeservers cost money whether anyone is using them or not. Workers pricing is request-based, so you pay when you’re using it, but costs drop to near zero when everyone’s asleep. 

**Lower latency globally:** A traditional Matrix homeserver in us-east-1 adds 200ms+ latency for users in Asia or Europe. Workers, meanwhile, run in 300+ locations worldwide. When a user in Tokyo sends a message, the Worker executes in Tokyo. 

**Built-in security: **Matrix homeservers can be high-value targets: They handle encrypted communications, store message history, and authenticate users. Traditional deployments require careful hardening: firewall configuration, rate limiting, DDoS mitigation, WAF rules, IP reputation filtering.

Workers provide all of this by default. 

    
    Cloudflare deployed post-quantum hybrid key agreement across all __TLS 1.3__ connections in __October 2022__. Every connection to our Worker automatically negotiates X25519MLKEM768 — a hybrid combining classical X25519 with ML-KEM, the post-quantum algorithm standardized by NIST.

Classical cryptography relies on mathematical problems that are hard for traditional computers but trivial for quantum computers running Shor’s algorithm. ML-KEM is based on lattice problems that remain hard even for quantum computers. The hybrid approach means both algorithms must fail for the connection to be compromised.

    
### Following a message through the system

      
        
      
     
    Understanding where encryption happens matters for security architecture. When someone sends a message through our homeserver, here’s the actual path:

The sender’s client takes the plaintext message and encrypts it with Megolm — Matrix’s end-to-end encryption. This encrypted payload then gets wrapped in TLS for transport. On Cloudflare, that TLS connection uses X25519MLKEM768, making it quantum-resistant.

          The Worker terminates TLS, but what it receives is still encrypted — the Megolm ciphertext. We store that ciphertext in D1, index it by room and timestamp, and deliver it to recipients. But we never see the plaintext. The message “Hello, world” exists only on the sender’s device and the recipient’s device.

When the recipient syncs, the process reverses. They receive the encrypted payload over another quantum-resistant TLS connection, then decrypt locally with their Megolm session keys.

    
### Two layers, independent protection

      
        
      
     
    This protects via two encryption layers that operate independently:

The __transport layer (TLS)__ protects data in transit. It’s encrypted at the client and decrypted at the Cloudflare edge. With X25519MLKEM768, this layer is now post-quantum.

The __application layer__ (Megolm E2EE) protects message content. It’s encrypted on the sender’s device and decrypted only on recipient devices. This uses classical Curve25519 cryptography.

    
    Any Matrix homeserver operator — whether running Synapse on a VPS or this implementation on Workers — can see metadata: which rooms exist, who’s in them, when messages were sent. But no one in the infrastructure chain can see the message content, because the E2EE payload is encrypted on sender devices before it ever hits the network. Cloudflare terminates TLS and passes requests to your Worker, but both see only Megolm ciphertext. Media in encrypted rooms is encrypted client-side before upload, and private keys never leave user devices.

    
### What traditional deployments would need

      
        
      
     
    Achieving post-quantum TLS on a traditional Matrix deployment would require upgrading OpenSSL or BoringSSL to a version supporting ML-KEM, configuring cipher suite preferences correctly, testing client compatibility across all Matrix apps, monitoring for TLS negotiation failures, staying current as PQC standards evolve, and handling clients that don’t support PQC gracefully.

With Workers, it’s automatic. Chrome, Firefox, and Edge all support X25519MLKEM768. Mobile apps using platform TLS stacks inherit this support. The security posture improves as Cloudflare’s __PQC__ deployment expands — no action required on our part.

    
## The storage architecture that made it work

      
        
      
     
    The key insight from porting Tuwunel was that different data needs different consistency guarantees. We use each Cloudflare primitive for what it does best.

    
    D1 stores everything that needs to survive restarts and support queries: users, rooms, events, device keys. Over 25 tables covering the full Matrix data model. 

            ```
CREATE TABLE events (
	event_id TEXT PRIMARY KEY,
	room_id TEXT NOT NULL,
	sender TEXT NOT NULL,
	event_type TEXT NOT NULL,
	state_key TEXT,
	content TEXT NOT NULL,
	origin_server_ts INTEGER NOT NULL,
	depth INTEGER NOT NULL
);
```

            D1’s SQLite foundation meant we could port Tuwunel’s queries with minimal changes. Joins, indexes, and aggregations work as expected.

We learned one hard lesson: D1’s eventual consistency breaks foreign key constraints. A write to rooms might not be visible when a subsequent write to events checks the foreign key. We removed all foreign keys and enforce referential integrity in application code.

    
    OAuth authorization codes live for 10 minutes, while refresh tokens last for a session.

            ```
// Store OAuth code with 10-minute TTL
kv.put(&format!("oauth_code:{}", code), &token_data)?
	.expiration_ttl(600)
	.execute()
	.await?;
```

            KV’s global distribution means OAuth flows work fast regardless of where users are located.

    
    Matrix media maps directly to R2, so you can upload an image, get back a content-addressed URL – and egress is free.

    
### Durable Objects for atomicity

      
        
      
     
    Some operations can’t tolerate eventual consistency. When a client claims a one-time encryption key, that key must be atomically removed. If two clients claim the same key, encrypted session establishment fails.

Durable Objects provide single-threaded, strongly consistent storage:

            ```
#[durable_object]
pub struct UserKeysObject {
	state: State,
	env: Env,
}
impl UserKeysObject {
	async fn claim_otk(&self, algorithm: &str) -> Result<Option<Key>> {
    	// Atomic within single DO - no race conditions possible
    	let mut keys: Vec<Key> = self.state.storage()
        	.get("one_time_keys")
        	.await
        	.ok()
        	.flatten()
        	.unwrap_or_default();
    	if let Some(idx) = keys.iter().position(|k| k.algorithm == algorithm) {
        	let key = keys.remove(idx);
        	self.state.storage().put("one_time_keys", &keys).await?;
        	return Ok(Some(key));
    	}
    	Ok(None)
	}
}
```

            We use UserKeysObject for E2EE key management, RoomObject for real-time room events like typing indicators and read receipts, and UserSyncObject for to-device message queues. The rest flows through D1.

    
### Complete end-to-end encryption, complete OAuth

      
        
      
     
    Our implementation supports the full Matrix E2EE stack: device keys, cross-signing keys, one-time keys, fallback keys, key backup, and dehydrated devices.

Modern Matrix clients use OAuth 2.0/OIDC instead of legacy password flows. We implemented a complete OAuth provider, with dynamic client registration, PKCE authorization, RS256-signed JWT tokens, token refresh with rotation, and standard OIDC discovery endpoints.

            ```
curl https://matrix.example.com/.well-known/openid-configuration
{
  "issuer": "https://matrix.example.com",
  "authorization_endpoint": "https://matrix.example.com/oauth/authorize",
  "token_endpoint": "https://matrix.example.com/oauth/token",
  "jwks_uri": "https://matrix.example.com/.well-known/jwks.json"
}
```

            Point Element or any Matrix client at the domain, and it discovers everything automatically.

    
    Traditional Matrix sync transfers megabytes of data on initial connection,  draining mobile battery and data plans.

Sliding Sync lets clients request exactly what they need. Instead of downloading everything, clients get the 20 most recent rooms with minimal state. As users scroll, they request more ranges. The server tracks position and sends only deltas.

Combined with edge execution, mobile clients can connect and render their room list in under 500ms, even on slow networks.

    
    For a homeserver serving a small team:

|   | **Traditional (VPS)**
 | **Workers**
 | 
|---|
| Monthly cost (idle) | $20-50 | <$1 | 
| Monthly cost (active) | $20-50 | $3-10 | 
| Global latency | 100-300ms | 20-50ms | 
| Time to deploy | Hours | Seconds | 
| Maintenance | Weekly | None | 
| DDoS protection | Additional cost | Included | 
| Post-quantum TLS | Complex setup | Automatic | 

**Based on public rates and metrics published by DigitalOcean, AWS Lightsail, and Linode as of January 15, 2026.*

The economics improve further at scale. Traditional deployments require capacity planning and over-provisioning. Workers scale automatically.

    
## The future of decentralized protocols

      
        
      
     
    We started this as an experiment: could Matrix run on Workers? It can—and the approach can work for other stateful protocols, too.

By mapping traditional stateful components to Cloudflare’s primitives — Postgres to D1, Redis to KV, mutexes to Durable Objects — we can see  that complex applications don't need complex infrastructure. We stripped away the operating system, the database management, and the network configuration, leaving only the application logic and the data itself.

Workers offers the sovereignty of owning your data, without the burden of owning the infrastructure.

I have been experimenting with the implementation and am excited for any contributions from others interested in this kind of service. 

Ready to build powerful, real-time applications on Workers? Get started with __Cloudflare Workers__ and explore __Durable Objects__ for your own stateful edge applications. Join our __Discord community__ to connect with other developers building at the edge.