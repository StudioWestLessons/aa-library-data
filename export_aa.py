"""
Exports Greg's Notion source for the Auditive Analysis Library to
aa-library.json, which studiowestlessons.com/aasoundlibrary fetches on
every page load (with the page's embedded copy as offline fallback).

SOURCE CHANGED 2026-08-26. This used to walk eight nested Notion PAGES and
infer each item's category from how deeply the block was indented. That was
fragile and it broke: an unrelated edit flattened the indentation on the
Sound Elements page, every sub-category lost its parent, and the export
published "Loose" where it meant "Closure — Loose", and merged
"Resonance — Medium" with "Energy — Medium". Nothing warned, because the
item count was still exactly 449.

The library now lives in a Notion DATABASE, where Area / Category /
Subcategory are dropdown columns. The structure is in the data, not in the
whitespace, so there is nothing left to flatten.

  database:   notion.so/5cfc4eade0e64ba185800a9e150a70b4
  collection: 9f2747e1-bdf8-42bd-a91f-a4806a47c40c

Read anonymously through the public notion.site API — the database inherits
public sharing from its parent page, so this needs no token and the workflow
needs no new secrets.

OUTPUT IS UNCHANGED: the same record shape the site has always consumed,
{area, category, voice, videoId, start, note, source, url}. `category` is
still "Parent — Child", composed here from the two columns.

Prints "CHANGED", "UNCHANGED" or "ERROR" as the first line of stdout, writes
the file when changed, and exits non-zero on ERROR so the workflow fails and
opens an alert issue.

Mirrored in studio-west-resources/aa-library/sync_check.py. Change both.
"""
import json
import os
import re
import subprocess
import sys

COLLECTION_ID = "9f2747e1-bdf8-42bd-a91f-a4806a47c40c"
DB_PAGE_ID = "5cfc4ead-e0e6-4ba1-8580-0a9e150a70b4"
NOTION_SITE = "https://climbing-van-64a.notion.site"

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aa-library.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# The 6 Areas order, as the chart and the site present it — NOT alphabetical.
AREA_ORDER = [
    "Registers", "Sound Elements", "Voice Qualities", "Vocal Overlays",
    "Distortions", "Special Techniques", "Transitions", "Extra",
]
VOICE_ORDER = ["Male", "Female"]

EXPECTED_MIN = 400          # refuse to publish a suspiciously short read


def post(endpoint, payload):
    cmd = [
        "curl", "-s", "-X", "POST", f"{NOTION_SITE}/api/v3/{endpoint}",
        "-H", "Content-Type: application/json", "-H", f"User-Agent: {UA}",
        "-d", json.dumps(payload),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60).stdout
    return json.loads(out)


def load_view_id():
    """The collection_view id, needed to query the collection."""
    data = post("loadPageChunk", {
        "pageId": DB_PAGE_ID, "limit": 50, "cursor": {"stack": []},
        "chunkNumber": 0, "verticalColumns": False,
    })
    views = data.get("recordMap", {}).get("collection_view", {})
    if not views:
        raise RuntimeError(
            "no collection_view on the database page — is it still shared publicly?")
    return next(iter(views))


def query_rows(view_id):
    data = post("queryCollection", {
        "collection": {"id": COLLECTION_ID},
        "collectionView": {"id": view_id},
        "loader": {
            "type": "reducer",
            "reducers": {"collection_group_results": {"type": "results", "limit": 5000}},
            "searchQuery": "", "userTimeZone": "America/Los_Angeles",
        },
    })
    rm = data.get("recordMap", {})
    collections = rm.get("collection", {})
    if not collections:
        raise RuntimeError("queryCollection returned no collection schema")
    schema = next(iter(collections.values()))["value"]["value"]["schema"]
    name_to_id = {v["name"]: k for k, v in schema.items()}

    rows = []
    for wrapper in rm.get("block", {}).values():
        b = wrapper.get("value", {}).get("value", {})
        if b.get("type") != "page":
            continue
        if b.get("parent_id") != COLLECTION_ID:
            continue                      # the database page itself, not a row
        if not b.get("alive", True):
            continue
        rows.append(b)
    return rows, name_to_id


def text_of(block, name_to_id, field):
    prop = (block.get("properties") or {}).get(name_to_id.get(field, ""))
    if not prop:
        return ""
    return "".join(seg[0] for seg in prop if seg and isinstance(seg[0], str)).strip()


def parse_link(url):
    """Video id and start-seconds out of the link. The link is the single
    source of truth for the timestamp — there is no separate start field."""
    vid = None
    for pat in (r"youtu\.be/([A-Za-z0-9_-]{6,})",
                r"[?&]v=([A-Za-z0-9_-]{6,})",
                r"/shorts/([A-Za-z0-9_-]{6,})",
                r"/embed/([A-Za-z0-9_-]{6,})"):
        m = re.search(pat, url)
        if m:
            vid = m.group(1)
            break
    m = re.search(r"[?&](?:t|start)=(\d+)s?\b", url)
    start = int(m.group(1)) if m else 0
    return vid, start


def build_records():
    rows, n2i = query_rows(load_view_id())
    records = []
    for b in rows:
        cat = text_of(b, n2i, "Category")
        sub = text_of(b, n2i, "Subcategory")
        link = text_of(b, n2i, "Link")
        source = text_of(b, n2i, "Source") or "youtube"
        vid, start = parse_link(link)
        records.append({
            "area": text_of(b, n2i, "Area"),
            "category": f"{cat} — {sub}" if sub else cat,
            "voice": text_of(b, n2i, "Voice"),
            "videoId": vid if source == "youtube" else None,
            "start": start,
            "note": text_of(b, n2i, "Note"),
            "source": source,
            "url": link,
        })

    # A database has no inherent running order and the view came back
    # scrambled, so impose one: 6 Areas order, then category, then Male
    # before Female. Deterministic run to run, which matters because the
    # workflow only commits when the JSON actually differs.
    def key(r):
        area_rank = AREA_ORDER.index(r["area"]) if r["area"] in AREA_ORDER else len(AREA_ORDER)
        voice_rank = VOICE_ORDER.index(r["voice"]) if r["voice"] in VOICE_ORDER else len(VOICE_ORDER)
        return (area_rank, r["category"], voice_rank, r["videoId"] or "", r["start"])

    records.sort(key=key)
    return records


def validate(records):
    """Returns (fatal, warnings). The old exporter checked only the record
    count, which is precisely why the flattening got through: the count stayed
    at exactly 449 while half the categories lost their parent.

    Fatal = structural, the thing that broke before. Warnings = real gaps in
    the library worth surfacing but not worth withholding the whole feed for.
    """
    fatal = []
    warnings = []

    if len(records) < EXPECTED_MIN:
        fatal.append(f"only {len(records)} items — far below the expected ~449")

    for field, label in (("area", "area"), ("category", "category"), ("url", "link")):
        missing = [r for r in records if not r[field]]
        if missing:
            fatal.append(f"{len(missing)} record(s) with no {label}")

    bad_area = sorted({r["area"] for r in records if r["area"] and r["area"] not in AREA_ORDER})
    if bad_area:
        fatal.append(f"unrecognised area(s): {bad_area}")

    yt_no_id = [r for r in records if r["source"] == "youtube" and not r["videoId"]]
    if yt_no_id:
        fatal.append(f"{len(yt_no_id)} youtube record(s) whose link yielded no video id")

    # Long-standing gap: two "Acoustic Register induced 'vocal breaks'" items
    # have never had a voice set, in the old pages or any published feed.
    # Worth seeing, not worth blocking on.
    no_voice = [r for r in records if not r["voice"]]
    if no_voice:
        where = ", ".join(sorted({f"{r['area']}/{r['category']}" for r in no_voice}))
        warnings.append(f"{len(no_voice)} record(s) with no voice ({where})")

    # A category that exists in only one area but with no sub-category, where
    # sibling categories all have one, is the shape the flattening produced.
    bare = sorted({r["category"] for r in records if " — " not in r["category"]})
    warnings.append(f"{len(bare)} categories carry no sub-category (expected ~30)")

    return fatal, warnings


def main():
    try:
        records = build_records()
    except Exception as e:
        print("ERROR")
        print(f"Notion extraction failed: {e}")
        sys.exit(1)

    fatal, warnings = validate(records)
    if fatal:
        print("ERROR")
        print("Refusing to publish. " + "; ".join(fatal))
        sys.exit(1)

    new_json = json.dumps(records, ensure_ascii=False, sort_keys=True, indent=0)

    old_json = None
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            old_json = f.read()

    note = ("  [" + "; ".join(warnings) + "]") if warnings else ""

    if old_json == new_json:
        print("UNCHANGED")
        print(f"{len(records)} items, aa-library.json already current.{note}")
        return

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(new_json)
    print("CHANGED")
    print(f"aa-library.json updated: {len(records)} items.{note}")


if __name__ == "__main__":
    main()
