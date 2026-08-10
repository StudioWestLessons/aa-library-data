"""
Exports Greg's "Exercise Library" Google Doc to exercise-library.json, which
studiowestlessons.com/exerciselibrary fetches on every page load (with the
page's embedded copy as offline fallback).

Same shape as export_aa.py alongside it, which does this for the Auditive
Analysis library from Notion — this repo hosts a published feed per source
page, not just the AA one. The doc parser lives in parse_exercises.py,
copied from studio-west-resources/exercise-library/parse.py (the private
automation repo) — that repo's sync_check.py guards this pipeline by diffing
the doc against the published JSON on a schedule. If you change the parsing
on one side, change it on both.

The doc must stay shared "Anyone with the link can view" for the headless
fetch to work; if that's revoked, Google serves a sign-in page instead of
HTML and this script errors rather than publishing an empty library.

Prints "CHANGED", "UNCHANGED", or "ERROR" as the first line of stdout
(comparing against the existing exercise-library.json on disk), writes the
new file when changed, and exits non-zero on ERROR so the workflow fails and
opens an alert issue.
"""
import json
import os
import subprocess
import sys

from parse_exercises import SECTION_ORDER, parse_doc_html, canonical_items

DOC_ID = "1_raReMGaNc7UIos6AGHWMvn3k4gHQgdDybGLR5vEu7M"
DOC_EXPORT_URL = f"https://docs.google.com/document/d/{DOC_ID}/export?format=html"

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "exercise-library.json")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# The doc had 104 items across 4 sections when this pipeline was built
# (2026-08-10). A sane floor guards against publishing a half-read or
# permission-denied response as if it were a real, much smaller library.
MIN_ITEMS = 40


def fetch(url):
    cmd = ["curl", "-s", "-L", "--compressed", "-H", f"User-Agent: {UA}", url]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed for {url}: {result.stderr.strip()}")
    return result.stdout


def extract_doc():
    html = fetch(DOC_EXPORT_URL)
    if "accounts.google.com" in html or "<html" not in html.lower():
        raise RuntimeError(
            "doc export did not return HTML — the doc's sharing setting may "
            "no longer be \"Anyone with the link can view\""
        )
    return parse_doc_html(html)


def main():
    try:
        sections = extract_doc()
    except Exception as e:
        print("ERROR")
        print(f"Doc extraction failed: {e}")
        sys.exit(1)

    total = sum(len(v) for v in canonical_items(sections).values())
    if total < MIN_ITEMS:
        print("ERROR")
        print(f"Only {total} items extracted — far below normal (~104). Refusing "
              f"to publish what is probably a partial/broken read.")
        sys.exit(1)

    new_json = json.dumps(sections, ensure_ascii=False, sort_keys=True, indent=0)

    old_json = None
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            old_json = f.read()

    if old_json == new_json:
        print("UNCHANGED")
        print(f"{total} items across {len(SECTION_ORDER)} sections, "
              f"exercise-library.json already current.")
        return

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(new_json)
    print("CHANGED")
    print(f"exercise-library.json updated: {total} items across "
          f"{len(SECTION_ORDER)} sections.")


if __name__ == "__main__":
    main()
