"""
Exports Greg's Notion source for the Auditive Analysis Library to
aa-library.json, which studiowestlessons.com/aasoundlibrary fetches on
every page load (with the page's embedded copy as offline fallback).

The Notion-parsing logic here is a copy of
studio-west-resources/aa-library/sync_check.py (the private automation
repo) — that script now guards this pipeline by diffing Notion against
the published JSON on a schedule. If you change the parsing on one side,
change it on both.

Prints "CHANGED", "UNCHANGED", or "ERROR" as the first line of stdout
(comparing against the existing aa-library.json on disk), writes the new
file when changed, and exits non-zero on ERROR so the workflow fails and
opens an alert issue.

Record order is Notion traversal order — the page groups items in array
order, so order is meaningful; do not sort.
"""
import json
import os
import re
import subprocess
import sys

AREAS = {
    "Registers": "2e681b129c488134be6fd0b79ec03286",
    "Sound Elements": "2e681b129c4881518229ccf22326d587",
    "Voice Qualities": "2e681b129c4881d781a9f7c8d5396c94",
    "Vocal Overlays": "2e681b129c4881c8b44bf9c3bc455c8f",
    "Distortions": "2e681b129c48811aa9badbab5c644b30",
    "Special Techniques": "2e681b129c4881839ef5d3f43d747dc0",
    "Transitions": "2e681b129c48818789b6f043475ff4b4",
    "Extra": "2e681b129c4881598169ef3f4c0f6847",
}

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aa-library.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SUBLABEL_RE_1 = re.compile(r"^[a-zA-Z]\.$")
SUBLABEL_RE_2 = re.compile(r"^[ivxIVX]{1,4}\.$")
TYPELABEL_RE = re.compile(r"^Type \d+$")


def dashed(pid):
    return f"{pid[0:8]}-{pid[8:12]}-{pid[12:16]}-{pid[16:20]}-{pid[20:32]}"


def fetch_chunk(page_id_dashed, chunk_number=0, cursor=None):
    if cursor is None:
        cursor = {"stack": []}
    body = json.dumps({
        "pageId": page_id_dashed, "limit": 200, "cursor": cursor,
        "chunkNumber": chunk_number, "verticalColumns": False,
    })
    cmd = [
        "curl", "-s", "-X", "POST",
        "https://climbing-van-64a.notion.site/api/v3/loadPageChunk",
        "-H", "Content-Type: application/json", "-H", f"User-Agent: {UA}",
        "-d", body,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30).stdout
    return json.loads(out)


def title_text(b):
    props = b.get("properties", {})
    title = props.get("title")
    if not title:
        return ""
    return "".join(t[0] for t in title if t and isinstance(t[0], str))


def caption_text(b):
    props = b.get("properties", {})
    cap = props.get("caption")
    if not cap:
        return ""
    return "".join(t[0] for t in cap if t and isinstance(t[0], str)).strip()


def extract_video_id(display_source):
    m = re.search(r"/embed/([A-Za-z0-9_-]{6,})", display_source or "")
    return m.group(1) if m else None


def extract_start(display_source):
    m = re.search(r"[?&]start=(\d+)", display_source or "")
    return int(m.group(1)) if m else 0


def parse_youtube_raw(url):
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{6,})", url)
    if not m:
        m = re.search(r"[?&]v=([A-Za-z0-9_-]{6,})", url)
    if not m:
        m = re.search(r"/shorts/([A-Za-z0-9_-]{6,})", url)
    vid = m.group(1) if m else None
    t = re.search(r"[?&]t=(\d+)s?\b", url)
    start = int(t.group(1)) if t else 0
    return vid, start


def ensure_page_loaded(blocks, page_id_dashed, fetched_pages):
    if page_id_dashed in fetched_pages:
        return
    fetched_pages.add(page_id_dashed)
    data = fetch_chunk(page_id_dashed)
    blocks.update(data["recordMap"]["block"])
    cursor = data.get("cursor", {})
    chunk_number = 0
    while cursor and cursor.get("stack"):
        chunk_number += 1
        more = fetch_chunk(page_id_dashed, chunk_number, cursor)
        blocks.update(more["recordMap"]["block"])
        cursor = more.get("cursor", {})
        if chunk_number > 20:
            break


def walk(blocks, block_id, area, depth, stack, vstate, sublabel, typelabel, records, missing, fetched_pages, root_id):
    entry = blocks.get(block_id)
    if not entry:
        missing.append(block_id)
        return
    b = entry["value"]["value"]
    if not b.get("alive", True):
        return
    t = b.get("type")

    def push_category(title, d):
        while stack and stack[-1][0] >= d:
            stack.pop()
        stack.append((d, title))
        sublabel[0] = None
        typelabel[0] = None

    def current_category():
        if not stack:
            base = ""
        elif len(stack) == 1:
            base = stack[-1][1]
        else:
            base = f"{stack[-2][1]} — {stack[-1][1]}"
        if typelabel[0]:
            base = f"{base} — {typelabel[0]}" if base else typelabel[0]
        if sublabel[0]:
            return f"{base} ({sublabel[0]})" if base else sublabel[0]
        return base

    if t == "page" and block_id != root_id:
        title = title_text(b).strip()
        if title:
            push_category(title, depth)
        vstate["voice"] = ""
        ensure_page_loaded(blocks, block_id, fetched_pages)
        entry = blocks.get(block_id)
        b = entry["value"]["value"]
    elif t == "text":
        title = title_text(b).strip()
        low = title.lower()
        if low in ("male", "female"):
            vstate["voice"] = title.capitalize()
        elif title.startswith("http://") or title.startswith("https://"):
            vid, start = parse_youtube_raw(title)
            src_type = ("youtube" if vid else
                        "instagram" if "instagram.com" in title else
                        "tiktok" if "tiktok.com" in title else "embed-other")
            records.append({
                "area": area, "category": current_category(),
                "voice": vstate.get("voice", ""), "videoId": vid, "start": start,
                "note": "", "source": src_type, "url": title,
            })
        elif SUBLABEL_RE_1.match(title) or SUBLABEL_RE_2.match(title):
            sublabel[0] = title.rstrip(".")
        elif TYPELABEL_RE.match(title):
            typelabel[0] = title
            sublabel[0] = None
        elif title:
            push_category(title, depth)
    elif t == "video":
        props = b.get("properties", {})
        source = props.get("source", [[""]])[0][0] if props.get("source") else ""
        fmt = b.get("format", {})
        display_source = fmt.get("display_source", "")
        vid = extract_video_id(display_source)
        start = extract_start(display_source)
        if not vid:
            vid, start = parse_youtube_raw(source)
        records.append({
            "area": area, "category": current_category(),
            "voice": vstate.get("voice", ""), "videoId": vid, "start": start,
            "note": caption_text(b), "source": "youtube", "url": source,
        })
    elif t == "embed":
        props = b.get("properties", {})
        source = props.get("source", [[""]])[0][0] if props.get("source") else ""
        note = caption_text(b)
        if "instagram.com" in source:
            src_type = "instagram"
        elif "youtube.com" in source or "youtu.be" in source:
            src_type = "youtube"
        elif "tiktok.com" in source:
            src_type = "tiktok"
        else:
            src_type = "embed-other"
        vid, start = (parse_youtube_raw(source) if src_type == "youtube" else (None, 0))
        records.append({
            "area": area, "category": current_category(),
            "voice": vstate.get("voice", ""), "videoId": vid, "start": start,
            "note": note, "source": src_type, "url": source,
        })

    for cid in b.get("content", []):
        walk(blocks, cid, area, depth + 1, stack, vstate, sublabel, typelabel, records, missing, fetched_pages, root_id)


def process_area(area, page_id_hex):
    page_id = dashed(page_id_hex)
    blocks = {}
    fetched_pages = set()
    ensure_page_loaded(blocks, page_id, fetched_pages)
    root = blocks[page_id]["value"]["value"]
    records = []
    missing = []
    stack = []
    vstate = {"voice": ""}
    sublabel = [None]
    typelabel = [None]
    for cid in root.get("content", []):
        walk(blocks, cid, area, 0, stack, vstate, sublabel, typelabel, records, missing, fetched_pages, page_id)
    return records, missing


def extract_notion():
    all_records = []
    total_missing = 0
    for area, pid in AREAS.items():
        records, missing = process_area(area, pid)
        all_records.extend(records)
        total_missing += len(missing)
    seen = set()
    deduped = []
    for r in all_records:
        key = (r["area"], r["category"], r["voice"], r["videoId"], r["start"], r["note"], r["source"], r["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped, total_missing


def main():
    try:
        records, missing_blocks = extract_notion()
    except Exception as e:
        print("ERROR")
        print(f"Notion extraction failed: {e}")
        sys.exit(1)

    if missing_blocks:
        print("ERROR")
        print(f"{missing_blocks} block(s) failed to resolve — Notion structure may have "
              f"changed in a way this script doesn't handle. Not safe to publish.")
        sys.exit(1)

    if len(records) < 50:
        print("ERROR")
        print(f"Only {len(records)} items extracted — far below normal (~450). Refusing "
              f"to publish what is probably a partial/broken read.")
        sys.exit(1)

    new_json = json.dumps(records, ensure_ascii=False, sort_keys=True, indent=0)

    old_json = None
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            old_json = f.read()

    if old_json == new_json:
        print("UNCHANGED")
        print(f"{len(records)} items, aa-library.json already current.")
        return

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(new_json)
    print("CHANGED")
    print(f"aa-library.json updated: {len(records)} items.")


if __name__ == "__main__":
    main()
