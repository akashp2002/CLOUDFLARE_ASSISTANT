"""
Phase 3: Recursive chunking with metadata (LlamaIndex version)
-----------------------------------------------------------------
Reads the .md files from data/raw/ (produced in Phase 2), loads each one as a
LlamaIndex Document (carrying source metadata), and splits them into chunks
("Nodes" in LlamaIndex terminology) using MarkdownNodeParser, which splits
along markdown heading structure -- the same "recursive by structure" idea
as before, just using the framework's built-in parser instead of custom code.

Output: data/chunks/nodes.json -> a flat list of node dicts, ready for Phase 4 (embeddings)

Install first:
    pip install llama-index-core
"""

import json
import re
from pathlib import Path

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser

RAW_DIR = Path("data/raw")
CHUNKS_DIR = Path("data/chunks")
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# Matches the first markdown heading line in a chunk, e.g. "### Root Cause" -> "Root Cause"
HEADING_LINE_PATTERN = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

# If a heading-split chunk is longer than this (in characters), split it further.
# ~1800 chars is roughly 400-450 tokens -- comfortably below BGE-M3's context limit,
# while still being long enough to keep most normal prose sections in one piece.
MAX_CHUNK_CHARS = 1800
SUB_CHUNK_OVERLAP = 150  # characters of overlap between sub-chunks, so context isn't lost at the cut


def extract_section_heading(chunk_text: str) -> str:
    """
    MarkdownNodeParser's own header_path metadata isn't reliably populated in
    some versions, so instead we pull the heading directly out of the chunk's
    own text -- every chunk that starts a new section begins with its heading
    line (e.g. "### Root Cause"). Chunks with no heading (e.g. the intro text
    before the first heading) return an empty string.
    """
    match = HEADING_LINE_PATTERN.search(chunk_text)
    return match.group(1).strip() if match else ""


def split_oversized_chunk(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = SUB_CHUNK_OVERLAP) -> list[str]:
    """
    Splits a single chunk that's too long into smaller pieces, preferring to cut
    at paragraph breaks ("\\n\\n") so code blocks and prose stay intact where possible.
    If a single paragraph is itself longer than max_chars (e.g. a giant log dump),
    it gets hard-cut as a last resort.

    Each returned piece includes a small overlap of trailing text from the previous
    piece, so a fact split near a boundary still has context in the next chunk.
    """
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    pieces = []
    current = ""

    for para in paragraphs:
        # If adding this paragraph would overflow, close off the current piece first
        if current and len(current) + len(para) + 2 > max_chars:
            pieces.append(current)
            # start the next piece with a small overlap tail from the previous piece
            current = current[-overlap:] + "\n\n" + para
        else:
            current = f"{current}\n\n{para}" if current else para

        # Last-resort hard cut if a single paragraph alone exceeds max_chars (e.g. a log dump)
        while len(current) > max_chars:
            pieces.append(current[:max_chars])
            current = current[max_chars - overlap:]

    if current:
        pieces.append(current)

    return pieces


def parse_front_matter(raw_text: str):
    """
    Splits the YAML-style front matter (between the --- markers) from the body text.
    Returns (metadata_dict, body_text).
    """
    import re
    match = re.match(r"^---\n(.*?)\n---\n\n(.*)$", raw_text, re.DOTALL)
    if not match:
        return {}, raw_text

    front_matter_raw, body = match.groups()
    metadata = {}
    for line in front_matter_raw.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip()
    return metadata, body


def load_documents(manifest: list[dict]) -> list[Document]:
    """
    Turns each raw .md file into a LlamaIndex Document object.
    Metadata attached here (title, url, date, doc_id) automatically flows down
    to every chunk/node created from this document later.
    """
    documents = []

    for entry in manifest:
        md_path = Path(entry["file"])
        if not md_path.exists():
            print(f"  Skipping missing file: {md_path}")
            continue

        with open(md_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        front_matter, body = parse_front_matter(raw_text)

        doc = Document(
            text=body,
            metadata={
                "doc_id": entry["slug"],
                "source_url": entry.get("url", ""),
                "title": front_matter.get("title") or entry.get("title") or "",
                "date": front_matter.get("date") or entry.get("date") or "",
            },
            # keep these metadata fields out of what gets embedded/sent to the LLM as raw text --
            # they're for citation/filtering, not semantic content
            excluded_embed_metadata_keys=["source_url", "date", "doc_id"],
            excluded_llm_metadata_keys=["source_url", "date", "doc_id"],
        )
        documents.append(doc)

    return documents


def main():
    manifest_path = RAW_DIR / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Expected manifest at {manifest_path} -- run Phase 2 first.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    documents = load_documents(manifest)
    print(f"Loaded {len(documents)} documents.")

    # MarkdownNodeParser splits on heading structure (#, ##, ###), attaching the
    # relevant heading path to each node's metadata automatically.
    parser = MarkdownNodeParser()
    nodes = parser.get_nodes_from_documents(documents)

    print(f"Created {len(nodes)} chunks (nodes).")

    # Convert nodes to plain dicts for saving as JSON (nodes aren't directly JSON-serializable).
    # Any chunk longer than MAX_CHUNK_CHARS gets further split here -- this is the second
    # "recursive" pass: heading-level split first (done above by MarkdownNodeParser),
    # then paragraph-level split for any section still too large (e.g. sections padded
    # with big code blocks or log dumps).
    node_dicts = []
    chunk_counter = 0
    oversized_count = 0

    for node in nodes:
        content = node.get_content()
        section_heading = extract_section_heading(content)

        sub_pieces = split_oversized_chunk(content)
        if len(sub_pieces) > 1:
            oversized_count += 1

        for part_num, piece in enumerate(sub_pieces):
            metadata = dict(node.metadata)
            metadata["section_heading"] = section_heading
            metadata["part"] = f"{part_num + 1}/{len(sub_pieces)}"  # e.g. "2/3", helps trace split-up sections

            node_dicts.append({
                "node_id": f"{node.node_id}_{part_num}" if len(sub_pieces) > 1 else node.node_id,
                "chunk_index": chunk_counter,
                "text": piece,
                "metadata": metadata,
            })
            chunk_counter += 1

    print(f"  {oversized_count} oversized section(s) were further split.")

    out_path = CHUNKS_DIR / "nodes.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(node_dicts, f, indent=2)

    print(f"\nDone. {len(node_dicts)} chunks saved to {out_path}")


if __name__ == "__main__":
    main()