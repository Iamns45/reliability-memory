#!/usr/bin/env python3
"""Validate documentation structure, ownership metadata, and local links."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REQUIRED_DOCUMENTS = (
    DOCS / "README.md",
    DOCS / "product" / "PRODUCT_REQUIREMENTS.md",
    DOCS / "product" / "GLOSSARY.md",
    DOCS / "architecture" / "SYSTEM_DESIGN.md",
    DOCS / "architecture" / "API_CONTRACT.md",
    DOCS / "architecture" / "DATA_MODEL.md",
    DOCS / "development" / "LOCAL_DEVELOPMENT.md",
    DOCS / "development" / "TESTING_STRATEGY.md",
    DOCS / "development" / "CODE_WALKTHROUGH.md",
    DOCS / "operations" / "AWS_DEPLOYMENT.md",
    DOCS / "operations" / "RUNBOOK.md",
    DOCS / "security" / "THREAT_MODEL.md",
    DOCS / "submission" / "DEMO_SCRIPT.md",
    DOCS / "submission" / "DEVPOST_SUBMISSION.md",
)
REQUIRED_METADATA = ("Status", "Audience", "Owner", "Last reviewed")
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")


def main() -> int:
    errors: list[str] = []
    for document in REQUIRED_DOCUMENTS:
        if not document.is_file():
            errors.append(f"missing required document: {document.relative_to(ROOT)}")

    markdown_files = sorted({ROOT / "README.md", ROOT / "CONTRIBUTING.md", *DOCS.rglob("*.md")})
    for document in markdown_files:
        if not document.is_file():
            continue
        text = document.read_text(encoding="utf-8")
        if document.is_relative_to(DOCS) and "decisions" not in document.parts:
            for field in REQUIRED_METADATA:
                if not re.search(rf"^> {re.escape(field)}:", text, flags=re.MULTILINE):
                    errors.append(f"{document.relative_to(ROOT)}: missing '{field}' metadata")
        errors.extend(validate_links(document, text))

    if errors:
        for error in errors:
            print(f"docs: {error}", file=sys.stderr)
        return 1
    print(f"docs: validated {len(markdown_files)} Markdown files")
    return 0


def validate_links(document: Path, text: str) -> list[str]:
    errors: list[str] = []
    for raw_target in MARKDOWN_LINK.findall(text):
        target = raw_target.strip().strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        path_text = unquote(target.split("#", maxsplit=1)[0])
        resolved = (document.parent / path_text).resolve()
        if not resolved.exists():
            errors.append(f"{document.relative_to(ROOT)}: broken local link '{raw_target}'")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
