#!/usr/bin/env python3
"""Regenerate the PR log in docs/dashboard/multi-agent-build-log.html.

The dashboard page lists every merged pull request. That list sits between
the `prs:start` / `prs:end` markers in the page and is rewritten from GitHub,
so nobody edits it by hand and a PR no longer has to add itself. Korean
titles live in the page's PR_KO map; a PR without one shows its English title
in both languages.

    python scripts/update_build_log.py                  # reads GitHub (GITHUB_REPOSITORY, GITHUB_TOKEN)
    python scripts/update_build_log.py --from-json f    # reads [{number,title,merged_at}, ...] from a file
    python scripts/update_build_log.py --check          # exit 1 if the page is out of date, write nothing

Only the standard library is used, so the GitHub workflow can run it as is.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "docs" / "dashboard" / "multi-agent-build-log.html"
BLOCK = re.compile(r"(/\* prs:start[^*]*\*/\n)(.*?)(\n\s*/\* prs:end \*/)", re.S)


def fetch_merged_prs(repo: str, token: str | None, base: str = "main") -> list[dict]:
    """All PRs merged into `base`, oldest first."""
    prs, page = [], 1
    while True:
        url = (f"https://api.github.com/repos/{repo}/pulls?state=closed&base={base}"
               f"&sort=created&direction=asc&per_page=100&page={page}")
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.load(resp)
        prs += [p for p in batch if p.get("merged_at")]
        if len(batch) < 100:
            return prs
        page += 1


def render_block(prs: list[dict]) -> str:
    rows = [
        "    {n:%d, title:%s, date:%s}"
        % (p["number"], json.dumps(p["title"], ensure_ascii=False), json.dumps(p["merged_at"][:10]))
        for p in sorted(prs, key=lambda p: p["number"])
    ]
    return "  var PRS = [\n" + ",\n".join(rows) + "\n  ];"


def update(html: str, prs: list[dict]) -> str:
    if not BLOCK.search(html):
        sys.exit("prs:start / prs:end markers not found in " + str(PAGE))
    return BLOCK.sub(lambda m: m.group(1) + render_block(prs) + m.group(3), html, count=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-json", help="read PRs from this JSON file instead of GitHub")
    ap.add_argument("--check", action="store_true", help="do not write; exit 1 if the page would change")
    ap.add_argument("--page", type=Path, default=PAGE)
    args = ap.parse_args()

    if args.from_json:
        prs = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        repo = os.environ.get("GITHUB_REPOSITORY", "jhleeooo/AI-Agent-Engineering")
        prs = fetch_merged_prs(repo, os.environ.get("GITHUB_TOKEN"))

    old = args.page.read_text(encoding="utf-8")
    new = update(old, prs)
    if new == old:
        print(f"up to date ({len(prs)} PRs)")
        return 0
    if args.check:
        print("out of date")
        return 1
    args.page.write_text(new, encoding="utf-8")
    print(f"updated: {len(prs)} PRs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
