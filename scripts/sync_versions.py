#!/usr/bin/env python3
# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Deep-link the code version and the guidelines-book version into README.md.

Single sources of truth:
  * code version -> src/police_thief/shared/version.py  (CODE_VERSION)
  * book version -> ../book-guidelines/orchestration/status/version.json (version)

Refreshes the marked spans in README.md and bundles the latest book PDF into
docs/. Run by the pre-commit hook; safe to run anytime (no-op if unchanged and
graceful if the sibling book repo is absent, e.g. on a fresh clone).
"""
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent            # repo root
README = ROOT / "README.md"
VERSION_PY = ROOT / "src" / "police_thief" / "shared" / "version.py"
BOOK_DIR = ROOT.parent / "book-guidelines"
BOOK_JSON = BOOK_DIR / "orchestration" / "status" / "version.json"
BOOK_PDF = BOOK_DIR / "police_thief_p2p.pdf"
DOCS_PDF = ROOT / "docs" / "police_thief_p2p.pdf"


def code_version() -> str:
    text = VERSION_PY.read_text(encoding="utf-8")
    match = re.search(r'CODE_VERSION\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else "unknown"


def book_version() -> str | None:
    try:
        return json.loads(BOOK_JSON.read_text(encoding="utf-8")).get("version")
    except OSError:
        return None


def _swap(text: str, tag: str, inner: str) -> str:
    pattern = f"(<!--{tag}_START-->).*?(<!--{tag}_END-->)"
    return re.sub(pattern, lambda m: m.group(1) + inner + m.group(2), text, flags=re.S)


def main() -> None:
    text = README.read_text(encoding="utf-8")
    code = code_version()
    text = _swap(text, "CODE_VERSION", f"**Code `v{code}`**")
    book = book_version()
    if book:
        text = _swap(text, "BOOK_VERSION", f"based on the **guidelines book `v{book}`**")
    README.write_text(text, encoding="utf-8")

    bundled = "missing"
    if BOOK_PDF.exists():
        DOCS_PDF.parent.mkdir(exist_ok=True)
        if not DOCS_PDF.exists() or DOCS_PDF.read_bytes() != BOOK_PDF.read_bytes():
            shutil.copy2(BOOK_PDF, DOCS_PDF)
            bundled = "updated"
        else:
            bundled = "up-to-date"
    print(f"sync_versions: code=v{code} book=v{book or '?'} pdf={bundled}")


if __name__ == "__main__":
    main()
