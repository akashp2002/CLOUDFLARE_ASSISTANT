import trafilatura
import json
import time
import re
from pathlib import Path

urls = [
    "https://blog.cloudflare.com/incident-report-on-memory-leak-caused-by-cloudflare-parser-bug/",
    "https://blog.cloudflare.com/code-orange-fail-small-complete/",
    "https://blog.cloudflare.com/route-leak-incident-january-22-2026/",
    "https://blog.cloudflare.com/rearchitecting-workers-kv-for-redundancy/",
    "https://blog.cloudflare.com/serverless-matrix-homeserver-workers/",
    "https://blog.cloudflare.com/workers-cache/",
    "https://blog.cloudflare.com/hyper-bug/",
    "https://blog.cloudflare.com/rollbacks-for-workflows/",
    "https://blog.cloudflare.com/build-your-own-vulnerability-harness/",
    "https://blog.cloudflare.com/scaling-security-scans/",
    "https://blog.cloudflare.com/copy-fail-linux-vulnerability-mitigation/",
    "https://blog.cloudflare.com/cloudflare-outage-february-20-2026/",
    "https://blog.cloudflare.com/de-tld-outage-dnssec/",
    "https://blog.cloudflare.com/q1-2026-internet-disruption-summary/",
    "https://blog.cloudflare.com/q4-2025-internet-disruption-summary/",
    "https://blog.cloudflare.com/enforce-first-as-bgp/",
    "https://blog.cloudflare.com/de-tld-outage-dnssec/",
    "https://blog.cloudflare.com/private-origins-dns-routing/",
    "https://blog.cloudflare.com/500-tbps-of-capacity/",
    "https://blog.cloudflare.com/agentic-internet-bot-report/"
]

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def slugify(url: str) -> str:
    """Turn the URL path into a readable filename."""
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"[^a-zA-Z0-9\-]", "", slug)
    return slug[:80]  # keep filenames sane

manifest = []  # tracks metadata for every doc -> used later for chunk metadata

for url in urls:
    slug = slugify(url)
    print(f"Fetching: {url}")

    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            print(f"  FAILED to download: {url}")
            continue

        # extract_metadata gives title/author/date; extract() gives the body text
        metadata = trafilatura.extract_metadata(downloaded)
        text = trafilatura.extract(downloaded, include_formatting=True, include_links=False)

        if not text:
            print(f"  FAILED to extract text: {url}")
            continue

        md_path = OUTPUT_DIR / f"{slug}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            # Front-matter style header — useful for your chunker to pick up metadata
            f.write(f"---\n")
            f.write(f"title: {metadata.title if metadata else ''}\n")
            f.write(f"url: {url}\n")
            f.write(f"date: {metadata.date if metadata else ''}\n")
            f.write(f"---\n\n")
            f.write(text)

        manifest.append({
            "slug": slug,
            "url": url,
            "title": metadata.title if metadata else None,
            "date": metadata.date if metadata else None,
            "file": str(md_path),
        })

        print(f"  Saved: {md_path}")

    except Exception as e:
        print(f"  ERROR on {url}: {e}")

    time.sleep(1)  # be polite to the server

# Save manifest — your Phase 2/3 ingestion + chunking code can read this
with open(OUTPUT_DIR / "manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"\nDone. {len(manifest)}/{len(urls)} docs saved to {OUTPUT_DIR}/")