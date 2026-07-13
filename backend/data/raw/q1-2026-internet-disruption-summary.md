---
title: Shutdowns, power outages, and conflict: a review of Q1 2026 Internet disruptions
url: https://blog.cloudflare.com/q1-2026-internet-disruption-summary/
date: 2026-04-28
---

In the first quarter of 2026, __government-directed shutdowns__ figured prominently, with prolonged Internet blackouts in both Uganda and Iran, a stark contrast to the lack of observed government-directed shutdowns in the same quarter a year prior. This quarter, we also observed a number of Internet disruptions caused by __power outages__, including three separate collapses of Cuba's national electrical grid. __Military action__ continued to disrupt connectivity in Ukraine and also impacted hyperscaler cloud infrastructure in the Middle East. __Severe weather__ knocked out Internet connectivity in Portugal, while __cable damage__ disrupted connectivity in the Republic of Congo. A __technical problem__ hit Verizon Wireless in the United States, and __unknown issues__ briefly disrupted connectivity for customers of providers in Guinea and the United Kingdom.

This post is intended as a summary overview of observed and confirmed disruptions and is not an exhaustive or complete list of issues that have occurred during the quarter. A larger list of detected traffic anomalies is available in the __Cloudflare Radar Outage Center__. Note that both bytes-based and request-based traffic graphs are used within this post to illustrate the impact of the observed disruptions, with the choice of metric generally made based on which better illustrates the impact of the disruption.

    
## Government-directed shutdowns

      
        
      
     
    
    
    In advance of the January 15 presidential election, __Ugandan__ authorities ordered a nationwide Internet shutdown. The Uganda Communications Commission (UCC) __instructed mobile network operators__ to suspend public Internet access, effective 18:00 local time (15:00 UTC) on January 13. The UCC __reportedly__ defended the shutdown as necessary to "curb misinformation, disinformation, electoral fraud and related risks." Domestic traffic at the Uganda Internet Exchange Point (UIXP) __dropped from approximately 72 Gbps to 1 Gbps__ as a result of the action taken.

Similarly, Cloudflare data shows a near-complete loss of traffic from __Uganda__ coincident with the start of the shutdown, with traffic remaining effectively at zero through 23:00 local time (20:00 UTC) on January 17, when Internet connectivity __was partially restored__ after incumbent President Yoweri Museveni was declared winner of his seventh term. 

Full Internet restoration was __announced by the UCC on January 26__, with mobile network operators __MTN Uganda__ and __Airtel Uganda__ both confirming on social media that restrictions had been lifted. The shutdown prompted __lawsuits against UCC and the telecoms companies__ and drew criticism from digital rights organizations including __CIPESA__.

Uganda also __blocked Internet access__ during its 2021 election. Authorities had repeatedly promised this time would be different, __stating__ as recently as January 5 that "claims suggesting otherwise are false, misleading."

    
    Iranian citizens spent a large part of Q1 2026 offline, or with severely limited connectivity, due to two nationwide Internet shutdowns. The first began around 20:00 local time (16:30 UTC) on January 8, and we explored the impact seen over the first few days in our __What we know about Iran’s Internet shutdown__

A near-complete loss of announced IPv6 address space started several hours before the drop in traffic took place on January 8. __Asiatech (AS43754)__ was by far the single largest contributor, losing 4.46 million /48-equivalents, accounting for ~9.4% of Iran's entire IPv6 space loss on its own. __RASANA (AS31549)__ was the second-largest, losing 4.19 million /48-equivalents (~8.8% of the country total). As would be expected, this resulted in the share of IPv6 traffic in Iran going to zero. Given the gap in timing between this change and the loss of traffic across the country, this may have been a leading indicator of what was about to happen, but likely not a direct cause of it. Some nominal shifts in announced IPv4 address space are visible during the shutdown, but levels remained fairly consistent during the shutdown period. These observations suggest that the shutdown was implemented by other means, such as filtering.

 Cloudflare Radar social media posts (__X__, __Bluesky__, __Mastodon__) throughout January and into early February documented our observations about the state of connectivity in Iran over the course of that month.

On February 28, as military strikes on Iran escalated, a second nationwide Internet shutdown began. __Cloudflare Radar observed__ a sharp drop in traffic from __Iran__ beginning around 10:30 local time (07:00 UTC). Traffic levels fell to well under 1% of previous levels, with only __small amounts of Web and DNS traffic__ egressing the country.

No significant shifts in announced IP address space were observed around the onset of this shutdown. IPv4 space remained fairly consistent, and IPv6 space remained consistently volatile, suggesting that route withdrawals were not the cause of this second shutdown.

The continued announcement of IP address space, and the presence of traffic from the country, even if just a small amount, supports reports that the shutdown was effectively achieved through aggressive filtering, with so-called __“whitelists” and “white SIM cards”__ restricting access to only approved Internet sites by selected users.

Iran remained effectively offline through the end of the quarter. As of late April, this shutdown remains largely in place, making it one of the longest sustained Internet disruptions observed in recent years.

    
    On March 15, as the __Republic of Congo__ held a presidential election __expected to extend President Denis Sassou Nguesso's 42-year rule__, a __near-complete shutdown of Internet connectivity__ was observed in the country. Traffic from the country dropped precipitously around 06:30 local time (05:30 UTC), falling to near zero for approximately 60 hours through the election period and its immediate aftermath. Traffic began recovering around March 17 at 18:20 local time (17:20 UTC), rapidly returning to pre-shutdown levels. While Congolese authorities provided no official explanation for the drop in traffic, __similar shutdowns were put into place__ during the 2021 and 2016 elections.

    
    
    
    On January 7-8, __Russian attacks on energy infrastructure__ in __Ukraine__ caused power outages that disrupted Internet connectivity in __Dnipropetrovsk__ and surrounding regions. __Cloudflare Radar observed__ a significant drop in traffic from the region, reaching nearly 50% below the prior week’s levels, starting around 22:45 local time (20:45 UTC) on January 7. Recovery began approximately 06:00 local time (04:00 UTC) on January 8.

    
    On January 26, Russia launched a drone and missile attack __targeting energy infrastructure__ in __Kharkiv__. __Cloudflare Radar observed__ an approximately 50% drop in traffic from the region beginning around 19:15 local time (17:15 UTC). Recovery progressed through January 27 as power was gradually restored.

    
### Amazon Web Services Middle East (United Arab Emirates and Bahrain)

      
        
      
     
    One of the most unusual disruptions of the quarter was the physical damage inflicted on __Amazon Web Services__ data centers in the Middle East by drone strikes tied to the ongoing regional conflict. On the morning of March 1 (UTC), Amazon __reported__ a fire started after objects hit a UAE data center. The following day, the company __confirmed__ that two of its facilities in the United Arab Emirates (__me-central-1__ region) were "directly struck" by drones and that a facility in Bahrain (__me-south-1__ region) was also taken offline after being damaged by a nearby strike.

Cloudflare's __Cloud Observatory__ data showed elevated connection failure rates for the __me-central-1__ and __me-south-1__ regions beginning March 1-2 and remaining higher for multiple days. Connection failures occur when Cloudflare fails to successfully connect to an origin server when attempting to retrieve uncacheable content, or content not in/expired from cache. These graphs illustrate the increased rate of failures experienced when attempting to connect to servers in these impacted regions.

In a __status post__ on the AWS Health Dashboard, Amazon acknowledged: "These strikes have caused structural damage, disrupted power delivery to our infrastructure, and in some cases required fire suppression activities that resulted in additional water damage." The company warned that instability was likely to continue in the Middle East, making operations "unpredictable," and urged customers with workloads in the affected regions to back up their data or migrate to other AWS regions.

__The AWS me-south-1 region in Bahrain suffered an additional disruption__ on March 23, following further drone activity.

    
    
    
    On January 15, a __power outage struck Buenos Aires__ during a summer heat wave. The outage caused nominal disruptions in Internet connectivity for customers of multiple providers in the __Buenos Aires__ area, including __Telecom Argentina (AS7303)__, __Telecentro (AS27747)__, and __IPLAN (AS16814)__, with traffic from these networks dropping between 17:30 and 19:30 local time (20:30 - 22:30 UTC). Traffic returned to expected levels approximately two hours after the outage began.

    
    An emergency power cut on __Ukraine's__ electricity grid on January 31 caused widespread power outages affecting __Moldova__ and several Ukrainian regions including __Kyiv__ and __Kharkiv__. Moldova was __reportedly__ hit by widespread power cuts amid the Ukrainian grid problems, and the Ukrainian Energy Minister __explained__ the cross-border impact, noting “Today at 10:42 a.m. (08:42 GMT), a technical malfunction occurred, causing a simultaneous shutdown of the 400 kilovolt line between the power grids of Romania and Moldova and the 750 kilovolt line between western and central Ukraine.” Traffic from Moldova, Kyiv, and Kharkiv began falling around 10:42 local time (08:42 UTC), __reaching as much as 46% below the prior week__, with recovery occurring around 14:00 local time (12:00 UTC).

    
    On February 18, widespread power outages struck __Paraguay__ after key transmission lines went out of service. __The National Electricity Administration (ANDE)__ posted a series of updates on X documenting the incident and efforts to restore power. Internet traffic from __Paraguay__ __dropped as much as 72%__ compared to the prior week beginning around 15:15 local time (18:15 UTC), and the disruption lasted nearly three hours, with recovery occurring by approximately 18:30 local time (21:30 UTC).

    
    A __major failure in the Interconnected National Electric System (SENI)__ of the __Dominican Republic__ caused a widespread power outage on February 23. The state-owned electric company __Empresa de Transmisión Eléctrica Dominicana (ETED)__ posted updates on X documenting the failure and the recovery effort. Internet traffic from the country dropped sharply beginning around 10:50 local time (14:50 UTC), and recovered around midnight local time (04:00 UTC) on February 24, in line with a __confirmation__ posted by ETED that “The authorities of the electric sector reported that the Interconnected National Electric System (SENI) was fully restored to 100% at 11:53 p.m. on this Monday…”.

    
    __Cuba__ experienced three separate collapses of its __National Electric System (SEN)__ during March, each causing widespread Internet disruption, reflecting the severe deterioration of the country's electrical infrastructure. (Power outages also disrupted Internet connectivity in Cuba during __September__ and __March__ 2025, and __October__ 2024.) 

The first collapse occurred on March 4, when a disconnection of Cuba's National Electroenergy System cascaded from Camagüey to Pinar del Río, cutting power to the western half of the island, including Havana. __OSDE/UNE (Cuba's Electric Union)__ confirmed the failure on social media. Cloudflare Radar data showed __traffic from the island dropping by nearly half__ beginning around 12:15 local time (17:15 UTC), with __traffic recovering__ by approximately 05:01 local time (10:01 UTC) on March 5.

The __second collapse__ occurred on March 16, when Cuba's entire National Electric Power System was disconnected. __EnergíaMinas Cuba__ posted updates on the situation on X. Cloudflare Radar data again shows a significant loss of traffic from Cuba beginning around 13:35 local time (17:35 UTC) on March 16, __dropping approximately 65%__. Traffic returned to expected levels by approximately 20:00 local time on March 17 (00:00 UTC on March 18), with the disruption lasting over 30 hours.

The __third collapse__ (the second in just a week) happened just days later, on March 21-22. __EnergíaMinas Cuba__ and __OSDE/UNE__ again provided situation updates via X. Cloudflare Radar data shows another __significant loss of traffic from Cuba__ beginning around 18:30 local time (22:30 UTC) on March 21, falling as much as 77% compared to the previous week. Traffic recovered around 21:39 local time on March 22 (01:39 UTC on March 23).

    
    According to a __Facebook post__ from the Virgin Islands Water and Power Authority (WAPA) on March 24, a loss of generation at the Richmond Power Plant combined with damage to an underground cable caused a power outage affecting __St. Croix__ and __St. Thomas__ in the __U.S. Virgin Islands__. Cloudflare Radar data shows traffic from local provider __VI Powernet (AS14434)__, the primary ISP for the U.S. Virgin Islands, dropping to near zero beginning around 12:15 local time (16:15 UTC), with recovery occurring by approximately 14:45 local time (18:45 UTC). Although VI Powernet experienced a near-complete outage, traffic from St. Thomas only fell by around 60%, and approximately 40% from St. Croix due to the presence of other providers.

    
    
    
    Storm Kristin made landfall in Portugal on January 28, causing widespread damage and power outages across the country. Approximately 1,500 __incidents were registered__ by Civil Protection between midnight and 08:00 local time (00:00 - 08:00 UTC), with the hardest-hit areas being the districts of Leiria and Coimbra. Significant infrastructure damage was reported, and by 07:00 local time (07:00 UTC), over 850,000 E-Redes customers were without electricity.

The associated power outages disrupted Internet connectivity across Portugal, which __Cloudflare Radar observed__ primarily in the regions of __Leiria__, __Santarém__, and __Coimbra__ beginning around 04:10 local time (04:10 UTC) on January 28. Internet traffic dropped as much as 70% in Leiria, and 52% in Coimbra.

Recovery was slow: __over 290,000 customers__ remained without power as late as January 30, and Cloudflare continued tracking __gradual recovery of regional traffic__ over the following weeks. (Coimbra returned to expected levels within the first several days after the storm.) More than three weeks after the storm, over 6,000 customers in Leiria __reportedly__ remained without electricity.

    
    
    
    Just after the New Year, Internet connectivity in the __Republic of Congo__ was disrupted by an incident on the __WACS (West Africa Cable System)__ submarine cable. __Congo Telecom (AS37451)__ __posted on X__ announcing "an international incident on the WACS cable" was causing Internet disruptions, and stating that backup solutions had been activated. __Cloudflare Radar observed__ a significant drop in traffic from __Congo__ beginning around 00:00 local time on January 2 (23:00 UTC on January 1), falling to 82% below expected levels. A __follow-up post from Congo Telecom__ confirmed that repairs were ongoing, with users potentially experiencing slowdowns during peak hours. Traffic returned to expected levels by approximately 15:00 local time (14:00 UTC) on January 4.

    
    
    
### Verizon Wireless (United States)

      
        
      
     
    On January 14, a __software issue__ impacted voice and data services for customers of __Verizon Wireless (AS6167)__ across the __United States__. Verizon __published an official statement__ acknowledging that the outage began January 14 and that by 22:15 ET (03:15 UTC on January 15) the issue had been resolved. __Multiple updates on X from @VerizonNews__ kept subscribers informed throughout the evening. Cloudflare Radar data shows a minor drop in traffic beginning around 12:30 ET (17:30 UTC) on January 14, consistent with the reported onset of the outage.

    
    On February 9-10, customers of __Flow Grenada (AS46650)__ – the primary Internet provider serving __Grenada__ – experienced an island-wide service disruption lasting approximately 12 hours. The provider __posted on Facebook__ acknowledging a service disruption, though no details about the root cause were provided. Cloudflare Radar data shows traffic from the network initially dropping around 11:30 local time (15:30) UTC on February 9, disappearing completely around 20:00 local time (midnight UTC on February 10), and recovering by approximately 23:30 local time (03:30 UTC on February 10). Routing data shows a complete loss of announced IPv4 space at the same time traffic dropped to zero. __Major spikes in BGP announcements__ around the time the disruption initially started, and bookending the complete outage, suggest that the whole event may have been routing-related.

    
    
    
    Customers of __Orange Guinée (AS37461)__ in __Guinea__ were __unable to make phone calls or access the Internet__ starting around 10:45 local time (10:45 UTC) on January 6. Orange Guinée __subsequently confirmed__ an "exceptional breakdown" affecting mobile phone and Internet services due to a technical incident, with teams mobilized to restore service. Service was restored by approximately 14:00 local time (14:00 UTC) that same day. No further details on the root cause of the incident were publicly disclosed.

    
### TalkTalk (United Kingdom)

      
        
      
     
    On March 25, customers of UK broadband provider __TalkTalk (AS13285)__ __reported__ widespread service disruptions. __TalkTalk acknowledged the issues on X__ but did not publicly disclose a root cause. __Cloudflare Radar observed__ traffic from the provider drop nearly 50% as compared to the previous week beginning around 07:00 local time (07:00 UTC), with service restored by approximately 08:15 local time (08:15 UTC).

    
## A quarter marked by major disruptions

      
        
      
     
    The first quarter of 2026 was marked by an unusually high number of severe and prolonged Internet disruptions. The major government-directed shutdowns, particularly the extended blackouts in Uganda and Iran, underscore how Internet access continues to be weaponized as a tool of political control. Cuba's three separate national grid collapses in a single month paint a troubling picture of infrastructure fragility with direct consequences for connectivity. And the drone strikes on AWS data centers in the Middle East represent an unprecedented escalation as active military conflict directly and physically damaged major cloud infrastructure, with disastrous consequences for the websites and applications hosted there.

The Cloudflare Radar team is constantly monitoring for Internet disruptions, sharing our observations on the __Cloudflare Radar Outage Center__, via social media, and in posts on __blog.cloudflare.com__. Follow us on social media at __@CloudflareRadar__(X), __noc.social/@cloudflareradar__ (Mastodon), and __radar.cloudflare.com__ (Bluesky), or contact us via __email__.