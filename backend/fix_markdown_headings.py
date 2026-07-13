"""
Fix: trafilatura sometimes outputs markdown headings with leading whitespace,
e.g. "      ### Root Cause" instead of "### Root Cause". Strict markdown parsers
(including LlamaIndex's MarkdownNodeParser) require headings to start at column 0,
so indented headings are silently ignored -- this is why every document was
coming out as a single chunk.

This script rewrites every .md file in data/raw/, stripping leading whitespace
from any line that is actually a heading (starts with optional whitespace + #),
while leaving all other text untouched.

Run this ONCE, before re-running chunk_documents_llamaindex.py.
"""

import re
from pathlib import Path

RAW_DIR = Path("data/raw")

# Matches lines like "   ### Some Heading" -> captures the #'s and the heading text,
# discarding the leading whitespace
HEADING_PATTERN = re.compile(r"^[ \t]+(#{1,6}\s+.*)$", re.MULTILINE)


def clean_file(path: Path) -> int:
    """De-indents heading lines in a single file. Returns number of headings fixed."""
    text = path.read_text(encoding="utf-8")
    fixed_text, count = HEADING_PATTERN.subn(r"\1", text)

    if count > 0:
        path.write_text(fixed_text, encoding="utf-8")

    return count


def main():
    md_files = list(RAW_DIR.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {RAW_DIR}")
        return

    total_fixed = 0
    for md_path in md_files:
        fixed = clean_file(md_path)
        total_fixed += fixed
        print(f"  {md_path.name}: {fixed} headings de-indented")

    print(f"\nDone. {total_fixed} headings fixed across {len(md_files)} files.")
    print("You can now re-run chunk_documents_llamaindex.py")


if __name__ == "__main__":
    main()