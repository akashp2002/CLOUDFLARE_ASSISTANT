---
title: When DNSSEC goes wrong: how we responded to the .de TLD outage
url: https://blog.cloudflare.com/de-tld-outage-dnssec/
date: 2026-05-06
---

On May 5, 2026, at roughly 19:30 UTC, DENIC, the registry operator for the `.de` country-code top-level domain (TLD), started publishing incorrect DNSSEC signatures for the `.de` zone. Any validating DNS resolver receiving these signatures was required by the DNSSEC specification to reject them and return SERVFAIL to clients, including __1.1.1.1__, the public DNS resolver operated by Cloudflare. 

The country-code top-level domain for Germany, `.de`, is one of the largest on the Internet. On __Cloudflare Radar__, it consistently ranks among the most broadly queried TLDs globally. An outage at this level of the DNS hierarchy has the potential to make millions of domains unreachable.

In this post, we’ll walk through what we saw, the impact of these events, and how we applied temporary mitigations while DENIC resolved the issue.

          
    
    __DNSSEC__ (Domain Name System Security Extensions) adds cryptographic authentication to DNS. When a zone is signed with DNSSEC, each set of records is accompanied by a digital signature known as an RRSIG record that lets a resolver verify the records haven’t been tampered with. Unlike encrypted DNS protocols, such as DNS over TLS (DoT) and DNS over HTTPs (DoH), DNSSEC is about integrity, not privacy. The records are visible, but their authenticity can be proven.

What makes DNSSEC unique is that the signatures travel together with the records they protect. This means integrity can be verified regardless of how many caches or hops a response has passed through. A cached record is just as verifiable as a fresh one.

DNSSEC is built on a chain of trust. Starting at the root zone, whose trust anchor is hard-coded into the resolvers, each zone delegates trust to child zones via Delegation Signer (DS) records. A DS record in the parent zone contains a cryptographic hash of a public key in the child zone. When a resolver validates `example.de` it verifies the chain: root trusts `.de`, `.de` trusts `example.de`. A break anywhere in that chain causes validation to fail for everything below it, which is why a misconfiguration at a TLD like `.de` affects every domain under it.

Zones typically use two types of keys: a Zone Signing Key (ZSK), used to sign the zone’s records, and a Key Signing Key (KSK), used to sign the ZSK itself. The KSK’s public key is what the parent zone’s DS record points to, anchoring the chain of trust. Rotating a ZSK is relatively straightforward: generate a new key, re-sign the zone’s records, and wait for caches to expire. Rotating a KSK is more involved, because the parent’s DS record must also be updated, often requiring coordination with a registrar or registry.

          During a key rotation, there is a critical window where the old key is being phased out and the new one phased in. If the signatures published in the zone are made with a key that resolvers cannot verify against the zone’s published DNSKEY records, whether because the signing step failed, the timing was wrong, or the new key wasn’t fully distributed yet, resolvers have no choice but to reject the responses and return SERVFAIL.

    
    On May 5, 2026, at roughly 19:30 UTC, DENIC, the operator for the `.de` TLD, started publishing incorrect DNSSEC signatures for the `.de` zone. Any validating resolver receiving these records was required by the DNSSEC specification to reject them and return SERVFAIL. 1.1.1.1 was no exception.

The graph below shows the response codes 1.1.1.1 returned for `.de` queries during the incident.

          After the immediate spike in SERVFAILs at 19:30 UTC, it climbed steadily over the following three hours as cached records slowly started expiring. As each domain's cached records expired and resolvers went back to DENIC for fresh copies, they got back broken signatures and started failing.

Also visible is a large increase in query volume. This is typical during DNS incidents, as clients retry failed queries, often three or more times, inflating the raw numbers. The SERVFAIL rate looks more alarming than the actual user impact, as many of those queries represent the same user retrying the same domain.

          What might be surprising is that the NOERROR rate stayed relatively stable throughout the incident. That's “serve stale” at work, which we'll cover in the next section.

    
    Recursive resolvers cache the records they receive from authoritative nameservers for the duration of each record's TTL (Time-to-Live). While a record is cached, the resolver serves it directly without going back to the authoritative nameserver. When the TTL expires, the resolver fetches a fresh copy and re-caches it.

During the outage, freshly requested records ended up resolving to SERVFAIL. The DNSSEC signatures were broken and the resolver correctly rejected them. But many `.de` records were still sitting in cache from before the incident began. Rather than immediately discarding those and returning SERVFAIL to users, 1.1.1.1 continued serving them past their TTL. This is called “serving stale.”

1.1.1.1 implements __RFC 8767__, which formalizes this behavior. When upstream resolution fails, a resolver may continue serving expired cached records rather than returning an error. This significantly cushions the impact of an upstream outage, buying time for operators to respond.

The result is visible in the graph below, which shows response codes for `.de` queries during the incident excluding the stale-served responses. Without stale-served responses, the NOERROR rate drops steadily from 19:30 onward. These represent queries that users received good answers for only because their record was still in cache.

          
    
    While the issue was largely out of our own control, and serve stale was doing its job, there was still a legitimate impact for a lot of users. Luckily, there were some actions we were able to take to improve the situation.

    
    __RFC 7646__ defines the concept of a Negative Trust Anchor (NTA). In normal DNSSEC operation, a validating resolver maintains a set of trust anchors: public keys at the root of the chain of trust. Each DNS zone signed with DNSSEC has a trust anchor, and every child zone builds its own trust anchor upon it. When the cryptographic signatures linking the chain together are broken, responses will be rejected and result in SERVFAIL. An NTA is an explicit exception. It tells the resolver to treat a specific zone as if it were unsigned, bypassing validation for names under that zone.

          NTAs exist precisely for these types of incidents. When a TLD operator publishes broken signatures, every DNSSEC-validating resolver is forced to return SERVFAIL for every domain under that TLD. Not because of anything wrong with those domains themselves, but because their parent zone is misconfigured. Continuing to return SERVFAIL in that situation provides no security value: the failure is already known, public, and being fixed. RFC 7646 explicitly names TLD misconfiguration as the primary use case for NTAs.

    
### What we actually deployed

      
        
      
     
    For 1.1.1.1 we have our own resolver referred to as __Big Pineapple__, which also powers 1.1.1.1 for Families, Gateway DNS, DNS Firewall, and more. At this time, we have not implemented a native NTA mechanism. Instead, we used an existing override rule mechanism to mark `.de` as an insecure zone, which causes all `.de` queries to be resolved as if they don’t have DNSSEC enabled. This is functionality equivalent to an NTA, though it is not formally defined in any RFC.

The decision to bypass DNSSEC is a deliberate tradeoff. Without DNSSEC validation, `.de` domains become vulnerable to __genuine attacks__ for the duration of the incident. During incidents like this, we weighed this as acceptable because the signing failure was widespread, publicly confirmed, and affected every validating resolver on the Internet equally. As it was put in our internal incident room: “*There is no user of 1.1.1.1 resolving a .de name right now who would prefer a SERVFAIL over an unvalidated response*.”

We rolled out our mitigation at 22:17 UTC, which marked the end of impact for 1.1.1.1. We communicated this with fellow DNS operators in the __DNS-OARC Mattermost__.

    
### Origin resolution mitigations

      
        
      
     
    While all Internet users can access our 1.1.1.1 resolver, we have a particular responsibility to customers using our CDN platform services. Those with `.de` origin names were also affected by this outage.

Cloudflare operates a separate internal resolver for origin resolution, distinct from our publicly available 1.1.1.1 service. To mitigate impact we applied a similar NTA for `.de` on the internal resolver service, restoring origin connectivity for affected customers.

    
    Before our mitigation, queries that couldn't be served from cache received a SERVFAIL response from 1.1.1.1. Each SERVFAIL included an Extended DNS Error (EDE) code, defined in __RFC 8914__, which gives clients more detail about what went wrong. 

Some resolvers returned EDE 6 (DNSSEC Bogus) with a descriptive message pointing directly at the broken signature. This is the correct behavior:

            ```
EDE: 6 (DNSSEC Bogus): RRSIG with malformed signature found for example.de/nsec3 (keytag=33834)
```

            1.1.1.1, on the other hand, returned EDE 22 (No Reachable Authority), which on the surface suggests a connectivity problem with the upstream nameservers rather than a DNSSEC validation failure.  

The cause is a bug in how we propagate DNSSEC EDE codes up from our trust chain verifier. When the verifier detects a bogus signature it creates the DNSSEC Bogus EDE code, but this is never inserted into the response. Instead, the outer layer of the resolver sees a problem with recursive resolution with no error code and falls back to reporting “No Reachable Authority.” This obscures the underlying DNSSEC cause.

We're aware that this isn't helpful for 1.1.1.1 users and will be fixing our responses to surface the DNSSEC errors.

    
## Is this a failure of DNSSEC as a technology?

      
        
      
     
    DNS is a critical part of the request chain for most Internet communication. It would be easy to come to the conclusion that this outage and the mitigations applied means DNSSEC has failed as a technology. However, any technology that is misconfigured will risk breaking for users that rely on it. Leaving critical fiber cables exposed on the seabed for sharks to chew on does not invalidate the important role underwater cables pose in today's Internet communications. It only highlights that we’ve sometimes failed to accurately protect it. The same applies here. DNSSEC serves a critical role in ensuring that we can rely on the DNS answers without tampering by malicious actors.

    
    No one likes to have serious incidents. These things, unfortunately, happen to everyone who operates critical infrastructure at scale. When they do, the DNS community tends to show up for each other.

Incidents like this also highlight why relationships between operators matter. DNS is a decentralized system, no single organization controls all of it, and keeping it running reliably depends on mutual trust and open lines of communication between registries, resolver operators, and the broader community. Forums like DNS-OARC provide exactly this: shared mailing lists and chat rooms where operators can coordinate quickly across organizational boundaries when something goes wrong.

DENIC has published __a short blog post about the incident__ where they state: “The outage is linked to a routine, scheduled key rollover. During this process, non-validatable signatures were generated and distributed. As a precautionary measure, future rollovers have been suspended until the exact technical causes have been identified.”

 We're sure we’ll hear more when their own analysis is ready. 

    
## Takeaways from this incident

      
        
      
     
    This incident highlights a structural reality of the DNS hierarchy: when a registry at the TLD level fails, every domain under that TLD is affected simultaneously, regardless of where it's hosted or which resolver is used. This isn't unique to DNSSEC; the same is true if a TLD’s nameservers become unreachable. The hierarchy that makes the global DNS work is also what makes failures at the top propagate downward.

There is no simple fix for this. What the industry can do is respond quickly and consistently when it happens. In this incident, resolver operators across the Internet independently applied Negative Trust Anchors within an hour, restoring resolution while DENIC worked to fix the zone. Operational practices, industry communication channels like DNS-OARC, and features like serve stale all reduce the impact, even if they can’t eliminate the underlying dependency.

We also came away with some points to improve for ourselves. We will be working on our EDE errors to better surface DNSSEC errors.

We look forward to DENIC’s post-incident report and appreciate the transparency they showed throughout.

If you want to learn more about how DNSSEC works, visit our page __How does DNSSEC work?__ And you can always follow real-time DNS trends and TLD data on __Cloudflare Radar__.