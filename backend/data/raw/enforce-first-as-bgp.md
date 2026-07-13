---
title: Enforcing the First AS in BGP AS PATHs
url: https://blog.cloudflare.com/enforce-first-as-bgp/
date: 2026-06-03
---

Some recent __route hijacks reported by Spamhaus__ captured our attention. In many of these hijack attempts, an apparent bad actor took advantage of unused __autonomous system numbers__, or ASNs. Notably in these hijacks, the actor appears to be creating fake AS_PATHs toward destinations, misdirecting traffic down an unexpected path. 

By creating forged AS_PATHs, the hijacker is attempting to lead traffic somewhere it isn’t normally meant to go while also trying to conceal their identity. A hijacker could strip enough information away from a network path that they could pretend to be the origin of a __Border Gateway Protocol__ (BGP) prefix themselves. Attackers can use this hijacked route to intercept traffic and for other nefarious purposes.

There is a simple solution for these cases: basic verification that a BGP peer autonomous system (AS) always includes their network as the “First AS” in an advertised route. To get a sense of how well these safeguards are implemented, we stress-tested several major networks and researched their BGP implementations. Read on to see what we learned.

    
## Examining route hijacks involving forged paths

      
        
      
     
    The idea that an actor is creating fake AS_PATHs is supported when we take a closer look at implausible __AS relationships__ in the path. For example, let’s examine one of the hijacks reported by Spamhaus, involving a prefix belonging to Orange S.A., the French telecom company. Using the __monocle__ tool, we can __easily find__ a __BGP UPDATE message__ related to the hijack:

            ```
➜  ~ monocle search --start-ts 2026-04-13T00:20:00Z --end-ts 2026-04-13T00:23:59Z --prefix 90.98.0.0/15 --collector rrc26 --json
{
  "aggr_asn": null,
  "aggr_ip": null,
  "as_path": "48237 1299 199524 270118 17072 41128",
  "atomic": false,
  "collector": "rrc26",
  "communities": null,
  "local_pref": 0,
  "med": 0,
  "next_hop": "185.1.8.3",
  "origin": "IGP",
  "peer_asn": 48237,
  "peer_ip": "185.1.8.3",
  "prefix": "90.98.0.0/15",
  "timestamp": 1776039612.0,
  "type": "ANNOUNCE"
}
```

            We know AS1299 (__Arelion__) is a __Tier 1 network__, meaning every AS on the right-hand side in the path is describing an upstream (customer-to-provider) relationship. This implies that AS17072 is a transit provider for AS41128, AS270118 for AS17072, and AS199524 for AS270118. If we take a closer look at these networks:

- AS41128 is an unused ASN belonging to Orange France 
- AS17072 is an ISP primarily based in Mexico 
- AS270118 is a hosting provider based in Mexico 
- AS199524 is - __Gcore__, a provider with a- __global peering presence__
 

The order of the ASes in the message above would suggest that an unused Orange France AS is buying transit from Mexican ISPs, which is then upstreamed to Gcore and Tier 1 providers – which would be quite odd.

In another instance, a reported hijack for prefixes 47.1.0.0/16 and 47.2.0.0/16 from origin AS36429 even included Cloudflare’s main ASN, 13335, in the AS_PATH, “199524 270118 17072 13335 36429”. We can view examples of these BGP UPDATEs in the __MRT Explorer__ from Cloudflare Radar:

          We can authoritatively confirm that we (Cloudflare, AS13335) have **no** __adjacency__ with the now-unused AS36429 owned by Charter. This means this was a forged path by the hijacker that included Cloudflare’s ASN as one of the fake upstream networks in advertisements propagated toward Gcore (AS199524). Further, Spamhaus correctly pointed out that all the hijack routes __led to a network__ behind Gcore peering in Chicago, never actually traversing the Mexican ISPs or Cloudflare’s network in the forwarding path.

Because of this, we can reasonably conclude these paths are forged up until the *leftmost* common AS, which in this case is AS199524, as the rest of the path seems implausible. We believe what is happening here is the result of a specific strategy by the hijacker, involving the following steps:

- Originate BGP announcements for “parked” prefixes 
- Forge the AS_PATH completely, - **without including the hijacker’s own local ASN**
 
- Advertise these routes to Gcore, AS199524 

In these hijacks it appears Gcore (AS199524) skips the verification and enforcement of the First AS matching the expected customer’s ASN. (We’ll look at why it might skip those steps later in this post.) As a result, the forged path is accepted and the hijacked prefixes are propagated to upstream providers and peers.

While Autonomous System Provider Authorization (__ASPA__) will help invalidate these forged paths, attackers may bypass it by only including an __RPKI-ROV__-valid origin AS, or a legitimate ASPA upstream AS. To stop these specific hijacks, we must rely on a different protection mechanism already built into BGP: **First AS checking and enforcement**.

    
## The importance of First AS checking

      
        
      
     
    Routing traffic across the Internet is a bit like shipping a package. When the package is shipped, a log is kept of every courier that handles it. In BGP, this is called the __AS_PATH__ (Autonomous System Path) and it tracks each network in the path of that route.

The AS_PATH attribute in BGP is used for __path selection__. This selection algorithm determines which route to a destination traverses the best list of hops, where “best” is defined by multiple variables. It is also used for loop prevention, where networks can decide not to accept paths that have already traversed their own network. Aside from keeping a record of the networks a BGP UPDATE, and therefore route, will traverse, the AS_PATH can also be examined by operator-configured routing policies to __route around__ or purposely through a given AS – for example to avoid __BGP anomalies__ having unexpected impact.

BGP was built on trust, and the AS_PATH can be easily manipulated – whether for seemingly legitimate reasons such as __AS prepending__ to move traffic around, or nefarious reasons such as shortening it to artificially attract traffic or perform origin attacks.

Let’s look at how these two types of malicious BGP manipulations are carried out. 

    
      **Example 1: **Forged origin attacks

      
        
      
     
    - AS64506 cryptographically signs their routes with an RPKI ROA (Route Origin Authorization) record, to prevent route origin hijacks. 
- AS64506 also creates an ASPA object, specifying - **only**AS64503 as a valid provider
 
- AS64505 manipulates their AS_PATH to strip AS64505 and originate with AS64506 
- AS64502 does not enforce the First AS 

The route appears RPKI-ROV valid and is the shortest path, effectively hijacking traffic with the route. AS64506 has done everything correctly by specifying a valid ROA for a prefix advertisement, and has even configured an ASPA object consisting of their sole provider AS64503.

Unfortunately, the hijacker running AS64505 is still able to attract traffic meant for AS64506. Even if AS64501, the customer, and AS64502, their provider, run __ASPA validation__, they will not find an invalid path, because there is no valley in the path “64502 64506”. In other words, AS64505 by way of not even including their own ASN in the AS_PATH is able to pretend they are AS64506 with no intermediate AS hop.

The correct way of preventing this hijack with existing tools is to enforce the First AS in the AS_PATH. Once enforcing this rule, AS64502 would properly drop the route from AS64505.

    
      **Example 2:** Shortening the AS_PATH to attract traffic

      
        
      
     
    - AS64506 has two transit providers: AS64503 and AS64505. 
- AS64505 bills their customer AS64506 based on traffic usage ratios. 
- AS64505 strips itself from the path, and their peer AS64504 does not enforce the First AS. 

The BGP path selection algorithm now chooses the route via AS64504 as the best path from AS64501. AS64506 pays both of their providers, AS64503 and AS64505, to deliver traffic from the Internet. However, now AS64505 provides a shorter BGP path from far-end sources, meaning AS64505 will process all the traffic toward AS64506 and be paid for doing so, and AS64503 will not be paid at all.

These BGP vulnerabilities can be solved very simply by **enforcing the First AS** to match the **peer AS **in a received AS_PATH.

When an operator configures a BGP neighbor, they must set the remote AS of the network they are interconnecting with. If the First AS in the AS_PATH does not match this value, then the path has been manipulated. The First AS enforcement procedure is outlined in __Section 6.3__ of RFC 4271 very clearly as:

“If the UPDATE message is received from an external peer, the local

system MAY check whether the leftmost (with respect to the position

of octets in the protocol message) AS in the AS_PATH attribute is

equal to the autonomous system number of the peer that sent the

message. If the check determines this is not the case, the Error

Subcode MUST be set to Malformed AS_PATH.”


__RFC 7606__ later revises how error-handling should be implemented by vendors, suggesting that routes containing malformed AS_PATHs should be dropped via *treat-as-withdraw* method. This allows routers to drop specific prefixes with malformed attributes without disrupting the entire BGP session.

The current ASPA draft __clearly calls out__ the importance of First AS enforcement, stating that ASPA **cannot** handle paths where sufficient AS_PATH information is lacking due to malformed announcements. Enforcing First AS in AS_PATHs is a **must** for Internet routing security.

    
## Measurement by breaking the First AS rule on purpose

      
        
      
     
    Instead of sticking to theoretical failure cases and past public incidents about violations of the First AS rule, we wanted to measure for ourselves how widely these AS_PATH violations could be accepted on the Internet. To do so, we set up BGP announcements to neighbors where we purposely **violated** the rule ourselves. Here is what we did:

- Allocated two IP prefixes, one for IPv4 and one for IPv6, to advertise to Tier 1 External BGP (EBGP) neighbors  
- Purposely prepended the test prefix advertisements to Tier 1 neighbors with a Cloudflare-owned, non-13335 ASN (AS402542) in front of 13335 

For example, we advertised the prefixes to AS1299 from our normal BGP session in Geneva. Our local AS is AS13335, but we include AS402542 clearly as the First AS in the AS_PATH.

            ```
[email protected]> show configuration policy-options policy-statement 4-TELIA-ACCEPT-EXPORT term ADV-FIRST-AS-PROBE-CR-1695522
from {
    community ANYCAST-ROUTE;
    prefix-list fl_first_as_prober;
    route-type internal;
}
then {
    origin igp;
    as-path-prepend 402542;
    next-hop self;
    accept;
}
[email protected]> show route advertising-protocol bgp <redacted_1299_ip> 162.159.82.0/24 detail | grep "AS path: "
     AS path: 402542 [13335] I
```

            With this configuration, our expectation is that: 

- Networks that - **do **enforce-first-as will quietly drop the route via RFC 7606 withdrawal method
 
- Networks that - **do not **enforce-first-as will- *accept*the route and install it for forwarding toward our test prefixes
 

Either result will be visible in BGP public route views. It was initially our goal to implement a continuous announcement of prefixes toward **all **peers that would purposely violate the First AS rule in announcements, and __give everyone a tool__ to check which ISPs validate First AS and those which do not. However, we found there are still networks that have not implemented the guidance published in RFC 7606 when receiving malformed BGP AS_PATHs, and would reset BGP sessions instead of a *treat-as-withdraw* behavior. This meant we could not safely implement a continuous set of announcements that violate the First AS rule without impacting real traffic to Cloudflare, which we obviously can’t do.

But we can take a closer look at the networks whose policies make the biggest impact: Tier 1 networks. These networks make up the backbone of the Internet and have the largest AS __customer cones__ of anyone, meaning hijacks or malformed paths by these peers have the broadest significance. Let’s start by examining the *normal *propagation of an anycast prefix, __1.1.1.0/24__, across the Tier 1 networks.

          The propagation of 1.1.1.0/24 looks how you would expect – it is directly reachable by every Tier 1 network that Cloudflare has a direct adjacency with currently.

Now, let’s compare that with our purposely malformed announcement of the prefix 162.159.82.0/24: 

          *Note: AS5511 (Orange S.A.) is not pictured above due to its limited presence in public route views, but it was a part of our testing and measurements.*

The prefix is propagated very differently from 1.1.1.0/24 – far fewer Tier 1 networks are accepting the announcement directly from Cloudflare (in this case from AS13335 with AS402542 prepended). Based on the criteria of our test mentioned earlier, these are the results we found.

Tier 1 networks **that are** enforcing First AS rule (by dropping the invalid announcements): 

- AS174 (Cogent) 
- AS1299 (Arelion) 
- AS3257 (GTT) 
- AS3491 (PCCW) 
- AS5511 (Orange S.A.) 
- AS6453 (Tata) 
- AS7018 (AT&T) 

Tier 1 networks that **are** **not** enforcing the First AS rule (by accepting and installing the prefixes): 

With our testing, we uncovered a troubling reality: **Half of the Tier 1 networks are vulnerable to hijacks that violate the First AS rule.**

While we only tested Tier 1 networks in this measurement study, there’s no doubt there are many non-Tier 1 networks that also break the First AS rule.

We noted that the majority of the Tier 1 networks failing the First AS violation test are running Juniper Networks routers, identified by the peers’ MAC addresses.

This highlights that the default behavior of vendors defines how secure a network is “out of the box” against First AS violation-based attacks. Let’s go over some of the BGP implementations and their defaults to have a better understanding of who is protected by default, and who isn’t.

    
## BGP implementations and default behaviors

      
        
      
     
    The chart below lists major routing/networking vendors and their BGP policies. Here, “Yes” means the BGP implementation by default enforces First AS, which is good. “No” means the BGP implementation is vulnerable by default. 

The lack of default enforcement from some vendors may stem from the only valid use case where the First AS should not be enforced on External BGP (EBGP) sessions: *Internet Exchange (IX) route servers*.

A route server is responsible for transparently (without appending its AS to the AS_PATH) distributing routes between peers on the fabric. This ensures peers do not have to configure new BGP sessions every time a network joins the fabric – instead they can peer with just the route server.

In reality, most production networks have far more sessions with neighbors who **are not **transparent IX route servers than neighbors who **are**. It makes much more sense to configure “no enforce-first-as” on a handful of route-server sessions than to manually enable “enforce-first-as” on every single peer in your network.

While a “safe by default” approach is best for protecting against First AS violations, it is generally a __steep hill to climb__ trying to convince vendors to change longstanding defaults. Vendors would also need to introduce a method of doing this gracefully, so as to not impact the IX route server BGP sessions that require “no enforce-first-as” settings to successfully receive routes.

    
## Safer Internet routing with your help: enforce the First AS

      
        
      
     
    Attackers will purposely malform AS_PATHs to slide around BGP security mechanisms. Even RPKI-based ASPA path validation will not be able to protect us from forged-origin hijacks where the path has been totally stripped of everything but the origin AS, leaving nothing for ASPA to invalidate. 

The good news is we *already* have a mitigation for these cases: we can verify the First AS matches BGP peer AS and always enforce it. Refer to the corresponding “Documentation” column in the above table we have provided. It should be safe to enforce First AS on any External BGP (EBGP) session besides those facing an IX route server neighbor.

**If you are a network operator, please enforce First AS on your routers today to protect your network and the wider Internet.**

If your router vendor or choice of BGP implementation has a default of enforcing First AS, you’re already safe and should be rejecting any First AS violations.

By working together, we can make the Internet safer from these kinds of hijacks.