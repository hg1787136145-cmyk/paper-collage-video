#!/usr/bin/env python3
"""Scan this repository for obvious secrets without printing secret values."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import sys


DEFAULT_IGNORE_DIRS = {
    ".git",
    "__pycache__",
}

DEFAULT_IGNORE_SUFFIXES = {
    ".gif",
    ".png",
    ".jpg",
    ".jpeg",
    ".mp4",
    ".mov",
    ".webm",
    ".zip",
    ".pyc",
}

PLACEHOLDER_WORDS = {
    "your",
    "example",
    "placeholder",
    "dummy",
    "sample",
}

PATTERNS = [
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_-]{20,}")),
    ("aws_like_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "jwt",
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    (
        "presigned_url_signature",
        re.compile(r"(?i)(x-tos-signature|x-amz-signature|signature)=([^\s&]{10,})"),
    ),
    (
        "credential_assignment",
        re.compile(
            r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?key|token|password)"
            r"\s*=\s*[\"']?([A-Za-z0-9_./+=:-]{16,})"
        ),
    ),
]


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    return -sum((value.count(char) / len(value)) * math.log2(value.count(char) / len(value)) for char in set(value))


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in PLACEHOLDER_WORDS) or "<" in value or "${" in value


def is_private_env_path(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    name = path.name
    return name.startswith(".env") and name != ".env.example" or "/.env" in rel and not rel.endswith("/.env.example")


def scan_file(path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings

    for line_number, line in enumerate(text.splitlines(), 1):
        for name, pattern in PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            value = match.group(match.lastindex or 0)
            if is_placeholder(value):
                continue
            findings.append((line_number, name))

        for token in re.findall(r"[A-Za-z0-9_+/=-]{32,}", line):
            if is_placeholder(token):
                continue
            if shannon_entropy(token) >= 4.5:
                findings.append((line_number, "high_entropy_token"))
                break

    return findings


def scan(root: Path) -> list[tuple[str, int, str]]:
    all_findings: list[tuple[str, int, str]] = []
    for path in root.rglob("*"):
        if any(part in DEFAULT_IGNORE_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() in DEFAULT_IGNORE_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if is_private_env_path(path, root):
            all_findings.append((rel, 0, "private_env_file"))
            continue
        for line_number, finding in scan_file(path):
            all_findings.append((rel, line_number, finding))
    return all_findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="Repository path to scan")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    findings = scan(root)
    if not findings:
        print("No obvious secrets found")
        return 0

    print("Potential secrets found:")
    for rel, line_number, finding in findings:
        print(f"{rel}:{line_number}:{finding}")
    print("Values are intentionally omitted from this report.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
