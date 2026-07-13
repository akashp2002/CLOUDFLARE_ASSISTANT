---
title: Cable cuts, storms, and DNS: a look at Internet disruptions in Q4 2025
url: https://blog.cloudflare.com/q4-2025-internet-disruption-summary/
date: 2026-01-26
---

In 2025, we __observed over 180 Internet disruptions__ spurred by a variety of causes – some were brief and partial, while others were complete outages lasting for days. In the fourth quarter, we tracked only a single __government-directed__ Internet shutdown, but multiple __cable cuts__ wreaked havoc on connectivity in several countries. __Power outages__ and __extreme weather__ disrupted Internet services in multiple places, and the ongoing __conflict__ in Ukraine impacted connectivity there as well. As always, a number of the disruptions we observed were due to __technical problems__ – with some acknowledged by the relevant providers, while others had unknown causes. In addition, incidents at several hyperscaler __cloud platforms__ and __Cloudflare__ impacted the availability of websites and applications.  

This post is intended as a summary overview of observed and confirmed disruptions and is not an exhaustive or complete list of issues that have occurred during the quarter. These anomalies are detected through significant deviations from expected traffic patterns observed across our network. Check out the __Cloudflare Radar Outage Center__ for a full list of verified anomalies and confirmed outages. 

    
    
    
    __The Internet was shut down in Tanzania__ on October 29 as __violent protests__ took place during the country’s presidential election. Traffic initially fell around 12:30 local time (09:30 UTC), dropping more than 90% lower than the previous week. The disruption lasted approximately 26 hours, with __traffic beginning to return__ around 14:30 local time (11:30 UTC) on October 30. However, that restoration __proved to be quite brief__, with a significant decrease in traffic occurring around 16:15 local time (13:15 UTC), approximately two hours after it returned. This second near-complete outage lasted until November 3, __when traffic aggressively returned__ after 17:00 local time (14:00 UTC). Nominal drops in __announced IPv4 and IPv6 address space__ were also observed during the shutdown, but there was never a complete loss of announcements, which would have signified a total disconnection of the country from the Internet. (__Autonomous systems__ announce IP address space to other Internet providers, letting them know what blocks of IP addresses they are responsible for.)

Tanzania’s president later __expressed sympathy__ for the members of the diplomatic community and foreigners residing in the country regarding the impact of the Internet shutdown. Internet and social media services were also __restricted in 2020__ ahead of the country’s general elections.

    
    
    
    Digicel Haiti is unfortunately no stranger to Internet disruptions caused by cable cuts, and the network experienced two more such incidents during the fourth quarter. On October 16, traffic from __Digicel Haiti (AS27653)__ began to fall at 14:30 local time (18:30 UTC), reaching near zero at 16:00 local time (20:00 UTC). A translated __X post from the company’s Director General__ noted: “*We advise our clientele that @DigicelHT is experiencing 2 cuts on its international fiber optic infrastructure.*” Traffic began to recover after 17:00 local time (21:00 UTC), and reached expected levels within the following hour. At 17:33 local time (21:34 UTC), the Director General __posted__ that “*the first fiber on the international infrastructure has been repaired” *and service had been restored. 

On November 25, another translated __X post from the provider’s Director General__ stated that its “*international optical fiber infrastructure on National Road 1*” had been cut. We observed traffic dropping on Digicel’s network approximately an hour earlier, with a complete outage observed between 02:00 - 08:00 local time (07:00 - 13:00 UTC). A __follow-on X post__ at 08:22 local time (13:22 UTC) stated that all services had been restored.

    
### Cybernet/StormFiber (Pakistan)

      
        
      
     
    At 17:30 local time (12:30 UTC) on October 20, Internet traffic for __Cybernet/StormFiber (AS9541)__ dropped sharply, falling to a level approximately 50% the same time a week prior. At the same time, the network’s announced IPv4 address space dropped by over a third. The cause of these shifts was damage to the __PEACE__ submarine cable, which suffered a cut in the Red Sea near Sudan. 

PEACE is one of several submarine cable systems (including __IMEWE__ and __SEA-ME-WE-4__) that carry international Internet traffic for Pakistani providers. The provider __pledged to fully restore service__ by October 27, but traffic and announced IPv4 address space had recovered to near expected levels by around 02:00 local time on October 21 (21:00 UTC on October 20).

    

### Camtel, MTN Cameroon, Orange Cameroun

      
        
      
     
    Unusual traffic patterns observed across multiple Internet providers in Cameroon on October 23 were reportedly caused by problems on the __WACS (West Africa Cable System)__ submarine cable, which connects countries along the west coast of Africa to Portugal. 

A (translated) __published report__ stated that MTN informed subscribers that “*following an incident on the WACS fiber optic cable, Internet service is temporarily disrupted*” and Orange Cameroun informed subscribers that “*due to an incident on the international access fiber, Internet service is disrupted.*” An __X post from Camtel__ stated “*Cameroon Telecommunications (CAMTEL) wishes to inform the public that a technical incident involving WACS cable equipment in Batoke (LIMBE) occurred in the early hours of 23 October 2025, causing Internet connectivity disruptions throughout the country.*” 

Traffic across the impacted providers originally fell just at around  05:00 local time (04:00 UTC) before recovering to expected levels around 22:00 local time (21:00 UTC). Traffic across these networks was quite volatile during the day, dropping 90-99% at times. It isn’t clear what caused the visible spikiness in the traffic pattern—possibly attempts to shift Internet traffic to __other submarine cable systems that connect to Cameroon__. Announced IP address space from __MTN Cameroon__ and __Orange Cameroon__ dropped during this period as well, although __Camtel’s__ announced IP address space did not change.

Connectivity in the __Central African Republic__ and __Republic of Congo__ was also reportedly impacted by the WACS issues.

    
    On December 9, we saw traffic from __Claro Dominicana (AS6400)__, an Internet provider in the Dominican Republic, drop sharply around 12:15 local time (16:15 UTC). Traffic levels fell again around 14:15 local time (18:15 UTC), bottoming out 77% lower than the previous week before quickly returning to expected levels. The connectivity disruption was likely caused by two fiber optic outages, as an __X post from the provider__ during the outage noted that they were “causing intermittency and slowness in some services.” A __subsequent post on X__ from Claro stated that technicians had restored Internet services nationwide by repairing the severed fiber optic cables.

    
    
    
    According to a (translated) __X post from the Empresa de Transmisión Eléctrica Dominicana__ (ETED), a transmission line outage caused an interruption in electrical service in the __Dominican Republic__ on November 11. This power outage impacted Internet traffic from the country, resulting in a __nearly 50% drop in traffic__ compared to the prior week, starting at 13:15 local time (17:15 UTC). Traffic levels remained lower until approximately 02:00 local time (06:00 UTC) on December 12, with a later __(translated) X post from ETED__ noting “*At 2:20 a.m. we have completed the recovery of the national electrical system, supplying 96% of the demand…*”

A subsequent __technical report found__ that “*the blackout began at the 138 kV San Pedro de Macorís I substation, where a live line was manually disconnected, triggering a high-intensity short circuit. Protection systems responded immediately, but the fault caused several nearby lines to disconnect, separating 575 MW of generation in the eastern region from the rest of the grid. The imbalance caused major power plants to trip automatically as part of their built-in safety mechanisms.*”

    
    On December 9, a __major power outage__ impacted multiple regions across __Kenya__. Kenya Power explained that the outage “*was triggered by an incident on the regional Kenya-Uganda interconnected power network, which caused a disturbance on the Kenyan side of the system*” and claimed that “*[p]ower was restored to most of the affected areas within approximately 30 minutes.*” However, impacts to Internet connectivity lasted for nearly four hours, between 19:15 - 23:00 local time (16:15 - 20:00 UTC). The power outage caused traffic to drop as much as 18% at a national level, with the traffic shifts most visible in __Nakuru County__ and __Kaimbu County__.

    
    
    
    __Russian drone strikes__ on the __Odesa region__ in __Ukraine__ on December 12 damaged warehouses and energy infrastructure, with the latter causing power outages in parts of the region. Those outages disrupted Internet connectivity, resulting in __traffic dropping by as much as 57%__ as compared to the prior week. After the initial drop at midnight on December 13 (22:00 UTC on December 12), traffic gradually recovered over the following several days, returning to expected levels around 14:30 local time (12:30 UTC) on December 16.

    
    
    
    __Hurricane Melissa__ made landfall on __Jamaica__ on October 28 and left a trail of damage and destruction in its path. Associated __power outages__ and infrastructure damage impacted Internet connectivity, causing traffic to initially __drop by approximately half__, __starting__ around 06:15 local time (11:15 UTC), ultimately reaching as much as __70% lower__ than the previous week. Internet traffic from Jamaica remained well below pre-hurricane levels for several days, and ultimately started to make greater progress towards expected levels __during the morning of November 4__. It can often take weeks or months for Internet traffic from a country to return to “normal” levels following storms that cause massive and widespread damage – while power may be largely restored within several days, damage to physical infrastructure takes significantly longer to address.

    
    On November 26, __Cyclone Senyar__ caused catastrophic floods and landslides in __Sri Lanka__ and __Indonesia__, killing over 1,000 people and damaging telecommunications and power infrastructure across these countries. The infrastructure damage resulted in __disruptions to Internet connectivity__, and resultant lower traffic levels, across multiple regions.

In Sri Lanka, regions outside the main Western Province were the most affected, and several provinces saw traffic drop __between 80% and 95%__ as compared to the prior week, including __North Western__, __Southern__, __Uva__, __Eastern__, __Northern__, __North Central__, and __Sabaragamuwa__.

In __Indonesia__, __Aceh__ and the Sumatra regions saw the biggest Internet disruptions. In Aceh, traffic initially dropped over 75% as compared to the previous week. In Sumatra, __North Sumatra__ was the most affected, with an early 30% drop as compared to the previous week, before starting to recover more actively the following week.

    
## Known or unspecified technical problems

      
        
      
     
    
    
    On October 3, subscribers to Indonesian Internet provider __Smartfren (AS18004__) experienced a service disruption. The issues were __acknowledged by the provider in an X post__, which stated (in translation), “*Currently, telephone, SMS and data services are experiencing problems in several areas.*” Traffic from the provider fell as much as 84%, starting around 09:00 local time (02:00 UTC). The disruption lasted for approximately eight hours, as traffic returned to expected levels around 17:00 local time (10:00 UTC). Smartfren did not provide any additional information on what caused the service problems.

    
    Major British Internet provider Vodafone UK (__AS5378__ & __AS25135__) experienced a brief service outage on October 23. At 15:00 local time (14:00 UTC), traffic on both Vodafone __ASNs__ dropped to zero. Announced IPv4 address space from __AS5378__ fell by 75%, while announced IPv4 address space from __AS25135__ disappeared entirely. Both Internet traffic and address space recovered two hours later, returning to expected levels around 17:00 local time (16:00 UTC). Vodafone did not provide any information on their social media channels about the cause of the outage, and their __network status checker page__ was also unavailable during the outage.

    
    According to a __published report__, a DNS resolution issue disrupted Internet services for customers of Italian provider __Fastweb (AS12874)__ on October 22, causing observed traffic volumes to drop by over 75%. Fastweb __acknowledged the issue__, which impacted wired Internet customers between 09:30 - 13:00 local time (08:30 - 12:00 UTC).

Although not an Internet outage caused by connectivity failure, the impact of DNS resolution issues on Internet traffic is very similar. When a provider’s __DNS resolver__ is experiencing problems, switching to a service like Cloudflare’s __1.1.1.1 public DNS resolver__ will often restore connectivity.

    
### SBIN, MTN Benin, Etisalat Benin

      
        
      
     
    On December 7, a concurrent drop in traffic was observed across __SBIN (AS28683)__, __MTN Benin (AS37424)__, and __Etisalat Benin (AS37136)__. Between 18:30 - 19:30 local time (17:30 - 18:30 UTC), traffic dropped as much as 80% as compared to the prior week at a country level, nearly 100% at Etisalat and MTN, and over 80% at SBIN.

While an __attempted coup__ had taken place earlier in the day, it is unclear whether the observed Internet disruption was related in any way. From a routing perspective, all three impacted networks share __Cogent (AS174)__ as an upstream provider, so a localized issue at Cogent may have contributed to the brief outage.  

    
    According to a __reported announcement__ from Israeli provider __Cellcom (AS1680)__, on December 18, there was “*a malfunction affecting Internet connectivity that is impacting some of our customers.*” This malfunction dropped traffic nearly 70% as compared to the prior week, and occurred between 09:30 - 11:00 local time (07:30 - 09:00 UTC). The “malfunction” may have been a DNS failure, according to a __published report__.

    
### Partner Communications (Israel)

      
        
      
     
    Closing out 2025, on December 30, a major technical failure at Israeli provider __Partner Communications (AS12400)__ __disrupted__ mobile, TV, and Internet services across the country. Internet traffic from Partner fell by two-thirds as compared to the previous week between 14:00 - 15:00 local time (12:00 - 13:00 UTC). During the outage, queries to Cloudflare’s 1.1.1.1 public DNS resolver spiked, suggesting that the problem may have been related to Partner’s DNS infrastructure. However, the provider did not publicly confirm what caused the outage.

    
    During the fourth quarter, we launched a new __Cloud Observatory__ page on Radar that tracks availability and performance issues at a region level across hyperscaler cloud platforms, including __Amazon Web Services__, __Microsoft Azure__, __Google Cloud Platform__, and __Oracle Cloud Infrastructure__.

    
    On October 20, the Amazon Web Services us-east-1 region in Northern Virginia experienced “__increased error rates and latencies__” that affected multiple services within the region. The issues impacted not only customers with public-facing Web sites and applications that rely on infrastructure within the region, but also Cloudflare customers that have origin resources hosted in us-east-1.

We began to see the impact of the problems around 06:30 UTC, as the share of __error__ (__5xx-class__) responses began to climb, reaching as high as 17% around 08:00 UTC. The number of __failures encountered when attempting to connect to origins__ in us-east-1 climbed as well, peaking around 12:00 UTC.

The impact could also be clearly seen in key network performance metrics, which remained elevated throughout the incident, returning to normal levels just before the end of the incident, around 23:00 UTC. Both __TCP__ and __TLS__ handshake durations got progressively worse throughout the incident—these metrics measure the amount of time needed for Cloudflare to establish TCP and TLS connections respectively with customer origin servers in us-east-1. In addition, the amount of time elapsed before Cloudflare __received response headers__ from the origin increased significantly during the first several hours of the incident, before gradually returning to expected levels.  

    
    On October 29, Microsoft Azure experienced an __incident__ impacting __Azure Front Door__, its content delivery network service. According to __Azure's report on the incident__, “*A specific sequence of customer configuration changes, performed across two different control plane build versions, resulted in incompatible customer configuration metadata being generated. These customer configuration changes themselves were valid and non-malicious – however they produced metadata that, when deployed to edge site servers, exposed a latent bug in the data plane. This incompatibility triggered a crash during asynchronous processing within the data plane service.*”

The incident report marked the start time at 15:41 UTC, although we observed the volume of __failed connection attempts__ to Azure-hosted origins begin to climb about 45 minutes prior. The TCP and TLS handshake metrics also became more volatile during the incident period, with __TCP handshakes__ taking over 50% longer at times, and __TLS handshakes__ taking nearly 200% longer at peak. The impacted metrics began to improve after 20:00 UTC, and according to Microsoft, the incident ended at 00:05 UTC on October 30.

    
    In addition to the outages discussed above, Cloudflare also experienced two disruptions during the fourth quarter. While these were not Internet outages in the classic sense, they did prevent users from accessing Web sites and applications delivered and protected by Cloudflare when they occurred.

The first incident took place on November 18, and was caused by a software failure triggered by a change to one of our database systems' permissions, which caused the database to output multiple entries into a “feature file” used by our Bot Management system. Additional details, including a root cause analysis and timeline, can be found in the associated __blog post__.

The second incident occurred on December 5, and impacted a subset of customers, accounting for approximately 28% of all HTTP traffic served by Cloudflare. It was triggered by changes being made to our request body parsing logic while attempting to detect and mitigate a newly disclosed industry-wide React Server Components vulnerability. A post-mortem __blog post__ contains additional details, including a root cause analysis and timeline.

For more information about the work underway at Cloudflare to prevent outages like these from happening again, check out our __blog post__ detailing “Code Orange: Fail Small.”

    
    The disruptions observed in the fourth quarter underscore the importance of real-time data in maintaining global connectivity. Whether it’s a government-ordered shutdown or a minor technical issue, transparency allows the technical community to respond faster and more effectively. We will continue to track these shifts on Cloudflare Radar, providing the insights needed to navigate the complexities of modern networking. We share our observations on the __Cloudflare Radar Outage Center__, via social media, and in posts on __blog.cloudflare.com__. Follow us on social media at __@CloudflareRadar__ (X), __noc.social/@cloudflareradar__ (Mastodon), and __radar.cloudflare.com__ (Bluesky), or contact us via __email__.

As a reminder, while these blog posts feature graphs from __Radar__ and the __Radar Data Explorer__, the underlying data is available from our __API__. You can use the API to retrieve data to do your own local monitoring or analysis, or you can use the __Radar MCP server__ to incorporate Radar data into your AI tools.