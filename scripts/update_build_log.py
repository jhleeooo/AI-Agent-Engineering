#!/usr/bin/env python3
"""Regenerate the PR log in docs/dashboard/multi-agent-build-log.html.

The dashboard page lists every merged pull request, in English and Korean.
Both lists sit between marker comments in the page and are rewritten from
GitHub, so nobody edits them by hand and a PR no longer has to add itself:

  prs:start    ... prs:end      the merged PRs (number, title, merge date)
  prs-ko:start ... prs-ko:end   the Korean titles, from pr-titles-ko.json

A PR's Korean title is decided once and then kept in pr-titles-ko.json, so it
never changes on later runs. The first source that has one wins:

  1. the JSON file (a title already stored, or one edited by hand);
  2. a line in the PR description: `Korean title: ...` or `한글 제목: ...`;
  3. a translation by Claude, when ANTHROPIC_API_KEY is set and the
     `anthropic` package is installed;
  4. none: the page shows the English title in both languages, and the next
     run tries again.

    python scripts/update_build_log.py                  # reads GitHub (GITHUB_REPOSITORY, GITHUB_TOKEN)
    python scripts/update_build_log.py --from-json f    # reads [{number,title,merged_at,body}, ...] from a file
    python scripts/update_build_log.py --check          # exit 1 if a file would change, write nothing

GitHub is read with the standard library only; `anthropic` is imported only
when a translation is needed.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Optional

DASHBOARD = Path(__file__).resolve().parent.parent / "docs" / "dashboard"
PAGE = DASHBOARD / "multi-agent-build-log.html"
KO_FILE = DASHBOARD / "pr-titles-ko.json"

PRS_BLOCK = re.compile(r"(/\* prs:start[^*]*\*/\n)(.*?)(\n\s*/\* prs:end \*/)", re.S)
KO_BLOCK = re.compile(r"(/\* prs-ko:start[^*]*\*/\n)(.*?)(\n\s*/\* prs-ko:end \*/)", re.S)
KO_LINE = re.compile(r"^[ \t]*(?:Korean title|한글 제목)[ \t]*[:：][ \t]*(\S.*?)[ \t]*$", re.I | re.M)

TRANSLATE_MODEL = "claude-opus-5-5"
TRANSLATE_PROMPT = (
    "Translate this GitHub pull request title into Korean for a project dashboard. "
    "Keep code identifiers, file names, PR numbers such as #12, and product names "
    "(Grafana, Prometheus, Temporal, Gemini, ...) in their original form. "
    "Reply with the Korean title only, on one line, with no quotes or explanation.\n\n"
    "Title: {title}"
)


def fetch_merged_prs(repo: str, token: Optional[str], base: str = "main") -> list[dict]:
    """All PRs merged into `base`, oldest first (each keeps its `body`)."""
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


def korean_title_from_body(body: Optional[str]) -> Optional[str]:
    """The `Korean title: ...` / `한글 제목: ...` line of a PR description."""
    m = KO_LINE.search(body or "")
    return m.group(1) if m else None


def translate_title(title: str) -> Optional[str]:
    """Ask Claude for a Korean title; None when it is unavailable or fails."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        print("anthropic is not installed; skipping translation", file=sys.stderr)
        return None
    try:
        response = anthropic.Anthropic().messages.create(
            model=TRANSLATE_MODEL,
            max_tokens=2000,  # thinking is always on for this model and counts against the limit
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": TRANSLATE_PROMPT.format(title=title)}],
        )
    except anthropic.APIError as e:
        print(f"translation failed for {title!r}: {e}", file=sys.stderr)
        return None
    if response.stop_reason == "refusal":
        print(f"translation refused for {title!r}", file=sys.stderr)
        return None
    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    if not text:
        return None
    return text.splitlines()[0].strip().strip("\"'“”‘’").strip() or None


def resolve_korean_titles(
    prs: list[dict],
    known: dict[str, str],
    translate: Callable[[str], Optional[str]] = translate_title,
) -> dict[str, str]:
    """`known` plus a Korean title for every PR that lacks one and can get one."""
    titles = dict(known)
    for pr in sorted(prs, key=lambda p: p["number"]):
        key = str(pr["number"])
        if key in titles:
            continue
        ko = korean_title_from_body(pr.get("body")) or translate(pr["title"])
        if ko:
            titles[key] = ko
            print(f"#{key}: Korean title added")
    return titles


def render_prs(prs: list[dict]) -> str:
    rows = [
        "    {n:%d, title:%s, date:%s}"
        % (p["number"], json.dumps(p["title"], ensure_ascii=False), json.dumps(p["merged_at"][:10]))
        for p in sorted(prs, key=lambda p: p["number"])
    ]
    return "  var PRS = [\n" + ",\n".join(rows) + "\n  ];"


def render_ko(titles: dict[str, str]) -> str:
    rows = [
        "    %s:%s" % (k, json.dumps(v, ensure_ascii=False))
        for k, v in sorted(titles.items(), key=lambda kv: int(kv[0]))
    ]
    return "  var PR_KO = {\n" + ",\n".join(rows) + "\n  };"


def render_ko_file(titles: dict[str, str]) -> str:
    ordered = dict(sorted(titles.items(), key=lambda kv: int(kv[0])))
    return json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"


def update_page(html: str, prs: list[dict], titles: dict[str, str]) -> str:
    for name, block in (("prs", PRS_BLOCK), ("prs-ko", KO_BLOCK)):
        if not block.search(html):
            sys.exit(f"{name}:start / {name}:end markers not found in the page")
    html = PRS_BLOCK.sub(lambda m: m.group(1) + render_prs(prs) + m.group(3), html, count=1)
    return KO_BLOCK.sub(lambda m: m.group(1) + render_ko(titles) + m.group(3), html, count=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-json", help="read PRs from this JSON file instead of GitHub")
    ap.add_argument("--check", action="store_true", help="do not write; exit 1 if a file would change")
    ap.add_argument("--page", type=Path, default=PAGE)
    ap.add_argument("--ko-file", type=Path, default=KO_FILE)
    args = ap.parse_args()

    if args.from_json:
        prs = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        repo = os.environ.get("GITHUB_REPOSITORY", "jhleeooo/AI-Agent-Engineering")
        prs = fetch_merged_prs(repo, os.environ.get("GITHUB_TOKEN"))

    known = json.loads(args.ko_file.read_text(encoding="utf-8")) if args.ko_file.exists() else {}
    titles = resolve_korean_titles(prs, known)

    old_page = args.page.read_text(encoding="utf-8")
    new_page = update_page(old_page, prs, titles)
    new_ko = render_ko_file(titles)
    old_ko = args.ko_file.read_text(encoding="utf-8") if args.ko_file.exists() else ""

    if new_page == old_page and new_ko == old_ko:
        print(f"up to date ({len(prs)} PRs)")
        return 0
    if args.check:
        print("out of date")
        return 1
    args.page.write_text(new_page, encoding="utf-8")
    args.ko_file.write_text(new_ko, encoding="utf-8")
    print(f"updated: {len(prs)} PRs, {len(titles)} Korean titles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
