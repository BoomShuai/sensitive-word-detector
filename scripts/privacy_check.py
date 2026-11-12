#!/usr/bin/env python3
"""Scan tracked text and optionally all reachable Git history before publishing."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "local-home-path": re.compile(r"/(?:Users|home)/[^/\s\"']+/|[A-Za-z]:\\Users\\[^\\\s]+\\"),
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "api-token": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}"),
    "mobile-number": re.compile(r"(?<![\da-fA-F])1[3-9]\d{9}(?![\da-fA-F])"),
    "identity-number": re.compile(r"(?<![\da-fA-F])[1-9]\d{16}[\dXx](?![\da-fA-F])"),
    "email": re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}
BLOCKED_PARTS = {".venv", "node_modules", "private", "models", "__pycache__"}
BLOCKED_SUFFIXES = {".pdf", ".docx", ".xlsx", ".zip", ".bin", ".safetensors", ".pem", ".key", ".log"}


def git(*args, data=None):
    return subprocess.run(["git", "-C", str(ROOT), *args], input=data, stdout=subprocess.PIPE, check=True).stdout


def scan(text):
    found = []
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            if name == "email" and (match[0].endswith("@users.noreply.github.com") or match[0] in {"noreply@github.com"}):
                continue
            found.append((name, text.count("\n", 0, match.start()) + 1))
    return found


def inspect(path, content):
    p = Path(path)
    if set(p.parts) & BLOCKED_PARTS or p.suffix.lower() in BLOCKED_SUFFIXES or p.name.startswith(".env"):
        return [("blocked-file", 0)]
    if len(content) > 2 * 1024 * 1024 or b"\0" in content:
        return [("binary-or-oversized-file", 0)]
    try:
        return scan(content.decode("utf-8"))
    except UnicodeDecodeError:
        return [("non-utf8-file", 0)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    errors = []
    names = [p for p in git("ls-files", "-z").decode().split("\0") if p]
    for name in names:
        if (ROOT / name).is_symlink():
            errors.append((name, "symlink", 0)); continue
        for pattern, line in inspect(name, (ROOT / name).read_bytes()):
            errors.append((name, pattern, line))
    count = 0
    if args.history:
        objects = git("rev-list", "--objects", "--all").decode().splitlines()
        for item in objects:
            parts = item.split(" ", 1)
            if len(parts) != 2:
                continue
            oid, name = parts
            if git("cat-file", "-t", oid).strip() != b"blob":
                continue
            count += 1
            for pattern, line in inspect(name, git("cat-file", "blob", oid)):
                errors.append(("history:" + name, pattern, line))
        metadata = git("log", "--all", "--format=%an%n%ae%n%cn%n%ce%n%B").decode()
        metadata += git("for-each-ref", "--format=%(taggername)%0a%(taggeremail)%0a%(contents)", "refs/tags").decode()
        for pattern, line in scan(metadata):
            errors.append(("commit-metadata", pattern, line))
    for name, pattern, line in errors:
        print("FAIL %s:%s [%s]" % (name, line, pattern), file=sys.stderr)
    if errors:
        return 1
    print("PASS: %d tracked files and %d historical blobs checked; no configured privacy patterns found." % (len(names), count))
    print("Pattern scanning supplements manual review; it cannot establish complete anonymity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
