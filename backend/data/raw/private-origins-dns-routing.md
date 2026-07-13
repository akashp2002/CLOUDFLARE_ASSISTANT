---
title: Route public traffic to private applications with Cloudflare
url: https://blog.cloudflare.com/private-origins-dns-routing/
date: 2026-06-10
---

For most of the Internet’s history, public and private infrastructure operated as separate worlds. Public applications lived behind content delivery networks (CDNs) and web application firewalls (WAFs). Private applications lived behind virtual private networks (VPNs), firewalls, and separate operational stacks. We think that distinction is becoming obsolete.

Many of the applications organizations care about are not public websites. They are internal APIs, AI agent backends, MCP servers, operational tools, and services that were never designed to be exposed to the public Internet. Yet these applications still need modern security, performance, and programmability services. Security should be a property of the traffic reaching an application, not an accident of where the application happens to sit.

Until now, applying those services to private applications often required public IPs, firewall exceptions, connector software, or complex networking. As a result, many private applications missed out on capabilities such as WAF, bot management, rate limiting, caching, traffic acceleration, rewrites, and Workers, despite needing the same protections and controls as public-facing applications.

**Today, we're launching Application Services for Private Origins in closed beta for eligible Enterprise customers.** Customers can now securely route traffic to private origins without exposing those origins to the public Internet. This allows Cloudflare's security, performance, and programmability services to protect applications running on private networks, just as they do for public Internet applications.

WAF rules, bot management, rate limiting, caching, rewrites, and Workers can now sit in front of private origins without requiring public IP exposure, inbound firewall rules, or `cloudflared` running on the origin.

    
### Four use cases, one application layer

      
        
      
     
    This routing model builds on connectivity patterns Cloudflare already supports today through __Cloudflare Tunnel__, __Cloudflare One Client__, and private network integrations. For years, Cloudflare Tunnel has allowed customers to route public traffic to private applications through `cloudflared`. This new capability extends the same model to existing __Cloudflare WAN__ or __Cloudflare Mesh connectivity__ without requiring connector software running on the origin.

Much of that connectivity is orchestrated through __Cloudflare’s private networking__ routing layer that determines how traffic reaches private destinations across Cloudflare Tunnels, __Virtual Networks__, Cloudflare Mesh, and other connectivity models. Customers can define their routing behavior through APIs and the dashboard instead of managing separate networking stacks for each product.  

We have extended Cloudflare’s private networking layer directly into the application services stack, allowing security and performance proxy infrastructure to treat private IPs as valid origin targets for public hostnames. As a result, the same private IPs previously reachable only through Cloudflare Tunnel, Cloudflare One, Cloudflare Mesh, or Cloudflare WAN can now sit behind Cloudflare’s security, performance, and programmability services the same way public origins already do.

This also creates a more unified model across Cloudflare products. __Workers VPC__ bindings and __Spectrum__ private origin routing now rely on the same underlying private connectivity layer, giving customers a single source of truth for controlling how private traffic moves through their Cloudflare environment.

Application traffic now falls into four combinations based on where users come from and where applications live: 

          The combination on the upper right is what Cloudflare has always done: users on the Internet reach applications on the Internet, with Cloudflare in the middle. The bottom right is __Cloudflare One__: users on private networks reach public services securely. 

The upper left is what we are shipping today. The bottom left, private-to-private, is what we are building toward next.

    
    Until now, getting public traffic to a private origin often meant making tradeoffs. Customers could use __Cloudflare Tunnel__, which runs __cloudflared__, our connector software, on or near the origin, or __Cloudflare Load Balancing__ with private origin pools for health checks and failover. In many cases, organizations also maintained parallel infrastructure such as public-facing load balancers, reverse proxies, mTLS between hops, and TLS termination across multiple layers. As a result, applying Cloudflare's full Application Services stack to private applications often required additional complexity, operational overhead, or separate products. Application Services for Private Origins removes those tradeoffs.

What was missing was a path for customers who already operate Cloudflare WAN (__IPsec tunnels__, __GRE tunnels__, __CNI links__) or __Cloudflare Mesh__. They had built private connectivity into Cloudflare for site-to-site networking and __Zero Trust__, and they wanted to use that same connectivity for public traffic to private origins. That is what Application Services for Private Origins delivers.

When you toggle **Use private network routing** on a proxied A or AAAA record, Cloudflare's WAF, rate limiting, caching, bot management, and transform rules all run as normal on Cloudflare’s network. The only difference is the final hop: instead of reaching the origin over the public Internet, Cloudflare routes the connection through your existing private network connectivity.

The toggle is enabled automatically for RFC 1918 private IPv4 ranges (10.x.x.x, 172.16.x.x–172.31.x.x, and 192.168.x.x), RFC 6598 CGNAT ranges (100.64.x.x–100.127.x.x), and RFC 4193 Unique Local IPv6 Addresses (FC00::/7), since these addresses are only reachable within private networks. For public IP addresses that are reachable only through your private network or tunnel, you can enable the toggle manually. 

          
    
    For customers automating deployments through the API, private routing is simply an additional attribute on a standard DNS record.

            ```
POST /zones/{zone_id}/dns_records
{
 "type": "A",
 "name": "app.example.com",
 "content": "10.0.0.50",
 "ttl": 300,
 "proxied": true,
 "use_private_routing": true
}
```

            Behind the scenes, Cloudflare's proxy platform determines where to send traffic for `app.example.com` by querying Cloudflare's Origin API. The response includes metadata indicating that the destination should be reached through a private network path:

            ```
{
 "zone_name": "example.com",
 "ipv4_addresses": ["10.0.0.50"],
 "use_private_routing": true
}
```

            The `use_private_routing` flag is the key signal. When our proxy sees it, instead of attempting to connect directly to the private IP address over the public Internet, it hands the request to our private networking layer, which then routes the connection across the customer's existing private network connectivity, whether that's IPsec, GRE, Cloudflare Tunnel, CNI, or Cloudflare Mesh.

    
### Beyond HTTP: Spectrum and Workers VPC

      
        
      
     
    The same routing model now extends beyond HTTP applications. The origin does not have to be a web server. It can be a TCP database, a UDP logging endpoint, or a private API that Workers call directly. The common thread is that Cloudflare sits between your traffic and your private network, applying the same security, performance, and routing layer regardless of protocol or where the request originated.

__Spectrum__`virtual_network_id` directly on the origin configuration. When you create a Spectrum application, you can include the virtual network ID alongside your private origin IP:

            ```
{
 "protocol": "tcp/22",
 "dns": {
   "type": "CNAME",
   "name": "ssh.example.com"
 },
 "origin_direct": ["tcp://10.0.0.50:22"],
 "virtual_network_id": "fab9ac85-491b-44c8-b7ae-dd44d4f4672e"
}
```

            When you create or update a Spectrum application with a private origin and virtual network, Cloudflare verifies that the IP address matches a route in your Cloudflare Tunnel before the configuration is saved. If no matching route exists, the API rejects the request and the application is not created. Once saved, Spectrum hands the connection to your __virtual network__, which routes it through the associated tunnel, via the same path that HTTP traffic uses when you enable private network routing on a DNS record. In this initial release, Spectrum private origins are supported through Cloudflare Tunnel. Support for additional private network connectivity options will follow in future releases.

This means you can now put Spectrum in front of any TCP/UDP service running on a private IP. The service stays private. No public IP, connector software, or load balancer required.

__Workers VPC__

    
    Public-to-private routing is in closed beta today, and we are targeting GA (General Availability) in Q4 2026.

Beyond GA, we are building toward private-to-private traffic flows: users, services, and AI agents on private networks securely reaching applications on other private networks, with Cloudflare’s application services sitting in the middle.

We are moving toward a model where the same Cloudflare infrastructure can secure traffic regardless of whether the user or the origin is public.

The end state is a world where an employee on Cloudflare One Client accessing `wiki.company.internal` gets the same WAF, rate limiting, and bot management protections as a customer accessing a public API. An AI agent consuming a proprietary internal API runs through the same security stack as a browser. Service-to-service traffic across clouds and data centers gets the same controls as Internet traffic, even when neither the user nor the server sits on the public Internet.

    
    Routing to private origins is available today in closed beta for eligible Enterprise customers. Reach out to your Cloudflare account team to request access. Once enabled, follow our __developer documentation__, which walks through the full setup. You will need __Cloudflare One connectivity__ (IPsec, GRE, CNI, or Cloudflare Mesh) and a return route for Cloudflare’s source IP range `100.64.0.0/12` in your private network.

Questions or feedback? Join the conversation in our __community forums__ or reach out to your account team.