"""
Exports Greg's Notion source for the Auditive Analysis Library to
aa-library.json, which studiowestlessons.com/aasoundlibrary fetches on
every page load (with the page's embedded copy as offline fallback).

The library lives in a Notion DATABASE (one row per example). Read anonymously
through the public notion.site API: the database inherits public sharing from
its parent page, so this needs no token and the workflow needs no secrets.

  database:   notion.so/5cfc4eade0e64ba185800a9e150a70b4
  collection: 9f2747e1-bdf8-42bd-a91f-a4806a47c40c

OUTPUT SHAPE IS UNCHANGED: {area, category, voice, videoId, start, note,
source, url}. `category` is "Category - Subcategory" composed here.

WHAT GREG TYPES IN A NEW ROW (2026-11-07): Link, Area, Category, Subcategory (when
the category has them), Voice, and an optional Note. Everything else is worked out
here: the website (Source) and the video id and start time from the Link. Area is
Greg's to pick, and an Area that contradicts the Category's usual one stops the
publish; a blank Area falls back to the Category's usual one. The row's title is a
free label that nothing reads.
A row with no Link is treated as unfinished: it is left out and mentioned, it does
not stop the export.

THREE THINGS CAN STOP A PUBLISH (the site then keeps its last good data and an
alert issue opens with the reason in it):
  1. A row that cannot be published as written (bad Link, no Category, an Area
     that contradicts the Category). The message names the row.
  2. A subcategory filed under the wrong category (e.g. Husky under Call).
  3. A bulk edit: many existing rows changed inside two minutes. On 2026-11-07 a
     fill-down in the Notion table set 50 rows to "Call" and 34 of them were
     Breathy, Closed, Dopey, Flowy and Lamented examples; the old checks only
     counted rows, so nothing noticed. If a block edit is intended, run the
     workflow by hand and tick "accept bulk changes".

Prints "CHANGED", "UNCHANGED" or "ERROR" as the first line of stdout, then
detail lines. Writes the file when changed and exits non-zero on ERROR.

The row-reading section between the SHARED markers is mirrored in
studio-west-resources/aa-library/sync_check.py. Change both together.
"""
import collections
import json
import os
import re
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse

COLLECTION_ID = "9f2747e1-bdf8-42bd-a91f-a4806a47c40c"
# The "Default view" of the database. Pinned on purpose: views added later (for
# example a filtered "Needs fixing" tab) must never change which rows are read.
VIEW_ID = "aee2d120-89b7-47d7-9aa8-1a0e6429c047"
NOTION_SITE = "https://climbing-van-64a.notion.site"

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aa-library.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# The 6 Areas order, as the chart and the site present it, NOT alphabetical.
AREA_ORDER = [
    "Registers", "Sound Elements", "Voice Qualities", "Vocal Overlays",
    "Distortions", "Special Techniques", "Transitions", "Extra",
]
VOICE_ORDER = ["Male", "Female"]

EXPECTED_MIN = 400          # refuse to publish a suspiciously short read

DASH = " — "           # the separator the page splits "Category - Subcategory" on


# ===================== BEGIN SHARED WITH sync_check.py =====================

def post(endpoint, payload):
    cmd = [
        "curl", "-s", "-X", "POST", f"{NOTION_SITE}/api/v3/{endpoint}",
        "-H", "Content-Type: application/json", "-H", f"User-Agent: {UA}",
        "-d", json.dumps(payload),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60).stdout
    return json.loads(out)


def query_rows():
    data = post("queryCollection", {
        "collection": {"id": COLLECTION_ID},
        "collectionView": {"id": VIEW_ID},
        "loader": {
            "type": "reducer",
            "reducers": {"collection_group_results": {"type": "results", "limit": 5000}},
            "searchQuery": "", "userTimeZone": "America/Los_Angeles",
        },
    })
    # queryCollection returns everything under `limit`, but check rather than
    # trust: a silently truncated read would publish a partial library.
    result = data.get("result") or {}
    if result.get("hasMore"):
        raise RuntimeError(
            "queryCollection reported hasMore: the library has outgrown the "
            "single-request limit and this would publish a partial feed")

    rm = data.get("recordMap", {})
    collections = rm.get("collection", {})
    if not collections:
        raise RuntimeError(
            "queryCollection returned no collection schema (is the Default view "
            "still there, and the database still shared publicly?)")
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


class RowProblem(Exception):
    """A row that cannot be published as written. The message is for Greg."""


def _host(url):
    return (urlparse(url).netloc or "").lower()


def _is_youtube(host):
    return (host == "youtu.be" or host.endswith(".youtu.be")
            or host == "youtube.com" or host.endswith(".youtube.com")
            or host == "youtube-nocookie.com" or host.endswith(".youtube-nocookie.com"))


def normalise_link(raw):
    """The address as typed, minus stray end spaces, with https:// added if he
    left it off. Text after the address (a note pasted into the Link cell) is a
    problem, not something to guess around."""
    url = (raw or "").strip()
    if not url:
        return ""
    if re.search(r"\s", url):
        raise RowProblem("the Link has extra text after the web address; keep the "
                         "address alone in Link and put words in Note")
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", url):
        url = "https://" + url
    return url


def detect_source(url):
    host = _host(url)
    if _is_youtube(host):
        return "youtube"
    if host.endswith("instagram.com"):
        return "instagram"
    if host.endswith("tiktok.com"):
        return "tiktok"
    raise RowProblem("the Link is not a YouTube, Instagram or TikTok address")


def parse_seconds(token):
    """66, 66s or 66.5 -> 66. Anything else is not understood (None)."""
    m = re.fullmatch(r"(\d+)(?:\.\d+)?s?", token.strip().lower())
    return int(m.group(1)) if m else None


def parse_youtube(url):
    """(video id, start seconds) from a YouTube address."""
    u = urlparse(url)
    host = u.netloc.lower()
    q = {k.lower(): v for k, v in parse_qs(u.query).items()}
    vid = None
    if host.endswith("youtu.be"):
        seg = [p for p in u.path.split("/") if p]
        vid = seg[0] if seg else None
    elif u.path.rstrip("/") == "/watch":
        vid = (q.get("v") or [None])[0]
    else:
        m = re.match(r"^/(?:shorts|live|embed|v)/([^/?#]+)", u.path)
        vid = m.group(1) if m else None
    if not vid or not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
        raise RowProblem("that YouTube address has no 11-character video id "
                         "(a playlist or channel address will not do)")
    raw_t = None
    for key in ("t", "start"):
        if key in q:
            raw_t = q[key][0]
            break
    if raw_t is None:
        m = re.search(r"(?:^|[&])t=([^&]*)", u.fragment)
        raw_t = m.group(1) if m else None
    if raw_t is None:
        return vid, 0
    start = parse_seconds(raw_t)
    if start is None:
        raise RowProblem(f"the time in the Link ({raw_t!r}) is not plain seconds; "
                         "use the address from YouTube's 'Copy video URL at current "
                         "time', which ends in t=66")
    return vid, start


def row_label(b, n2i):
    title = text_of(b, n2i, "Label (optional)") or text_of(b, n2i, "Example")
    rid = b["id"].replace("-", "")
    return f"'{title or 'untitled row'}' (notion.so/{rid})"


def build_records(rows, n2i):
    """Rows -> (records, meta, problems, skipped).

    records  the feed records, sorted
    meta     one dict per record: page id, label, created/edited time (for guards)
    problems fatal, plain-English, each naming its row
    skipped  labels of unfinished rows (no Link) left out
    """
    # Which Area each Category belongs to, from the rows that state it.
    area_votes = collections.defaultdict(collections.Counter)
    for b in rows:
        a, c = text_of(b, n2i, "Area"), text_of(b, n2i, "Category")
        if a and c:
            area_votes[c][a] += 1

    built, problems, skipped = [], [], []
    for b in rows:
        label = row_label(b, n2i)
        raw_link = text_of(b, n2i, "Link")
        if not raw_link.strip():
            skipped.append(label)
            continue
        try:
            cat = text_of(b, n2i, "Category")
            sub = text_of(b, n2i, "Subcategory")
            if not cat:
                raise RowProblem("it has no Category")
            link = normalise_link(raw_link)
            source = detect_source(link)
            vid, start = parse_youtube(link) if source == "youtube" else (None, 0)

            area = text_of(b, n2i, "Area")
            votes = area_votes.get(cat)
            usual = votes.most_common(1)[0][0] if votes else None
            if not area:
                if not usual:
                    raise RowProblem(f"{cat!r} is a new Category, so set this row's Area "
                                     f"(one of: {', '.join(AREA_ORDER)})")
                area = usual
            elif area not in AREA_ORDER:
                raise RowProblem(f"the Area {area!r} is not one of the 8 Areas")
            elif usual and area != usual and votes[usual] >= 2:
                raise RowProblem(f"{cat!r} is normally under {usual}, but this row says {area}")

            built.append(({
                "area": area,
                "category": f"{cat}{DASH}{sub}" if sub else cat,
                "voice": text_of(b, n2i, "Voice"),
                "videoId": vid,
                "start": start,
                "note": text_of(b, n2i, "Note"),
                "source": source,
                "url": link,
            }, {
                "id": b["id"], "label": label,
                "created": b.get("created_time") or 0,
                "edited": b.get("last_edited_time") or 0,
            }))
        except RowProblem as e:
            problems.append(f"{label}: {e}")

    def key(rm):
        r = rm[0]
        area_rank = AREA_ORDER.index(r["area"]) if r["area"] in AREA_ORDER else len(AREA_ORDER)
        voice_rank = VOICE_ORDER.index(r["voice"]) if r["voice"] in VOICE_ORDER else len(VOICE_ORDER)
        return (area_rank, r["category"], voice_rank, r["videoId"] or "", r["start"])

    built.sort(key=key)
    return [r for r, _ in built], [m for _, m in built], problems, skipped

# ====================== END SHARED WITH sync_check.py ======================


# Subcategories that belong to exactly one category in the 6 Areas chart. Shared
# ones (Medium, Balanced, Smooth, Abrupt...) are left out on purpose, and a
# subcategory Greg invents is unconstrained. If he renames one of these PARENTS
# on purpose, the export stops with a message saying so: update this table (or run
# the workflow by hand with "accept bulk changes" ticked) and it carries on.
SUB_PARENT = {
    "Airy": {"Breathy"}, "Husky": {"Breathy"},
    "Complain": {"Lamented"}, "Cry": {"Lamented"}, "Sob": {"Lamented"}, "Wail": {"Lamented"},
    "Fry Scream": {"Scream"}, "Hybrid Scream": {"Scream"},
    "Hammer": {"Vibrato"}, "Laryngeal": {"Vibrato"}, "Supported": {"Vibrato"},
    "Yodel-brato": {"Vibrato"},
    "T1 (Kermit)": {"Tongue Techniques"}, "T2 (Stitch)": {"Tongue Techniques"},
    "T3 (Yarl)": {"Tongue Techniques"},
    "Type 1": {"Riffs and Runs"}, "Type 2": {"Riffs and Runs"}, "Type 3 (a)": {"Riffs and Runs"},
    "Type 3 (b)": {"Riffs and Runs"}, "Type 4": {"Riffs and Runs"}, "Type 5": {"Riffs and Runs"},
    "Reinforced Falsetto": {"Falsetto"}, "Falsetto Mix": {"Mix"}, "Modal Mix": {"Mix"},
    "Spacious": {"Call", "Whoop"}, "Twanged": {"Call", "Whoop"},
}
# Per the chart these Voice Quality families exist only as their subtypes.
NEEDS_SUBTYPE = {("Voice Qualities", "Call"), ("Voice Qualities", "Whoop")}

BULK_EDIT_MIN = 10              # this many existing rows changed...
BULK_EDIT_WINDOW_MS = 120_000   # ...within this long, of each other
SHRINK_LIMIT = 2                # or more than this many rows gone since the last export (deleted, or Link cleared)

ACCEPT_WORDS = ("1", "true", "yes")


def accepting():
    return os.environ.get("AA_ACCEPT_BULK_CHANGES", "").strip().lower() in ACCEPT_WORDS


def check_taxonomy(records):
    problems = collections.Counter()
    for r in records:
        cat, _, sub = r["category"].partition(DASH)
        if sub in SUB_PARENT and cat not in SUB_PARENT[sub]:
            problems[f"{r['area']}: {sub!r} is filed under {cat!r} (it belongs under "
                     f"{' or '.join(sorted(SUB_PARENT[sub]))})"] += 1
        if (r["area"], cat) in NEEDS_SUBTYPE and not sub:
            problems[f"{r['area']}: {cat!r} needs a Subcategory (Spacious or Twanged)"] += 1
    if not problems:
        return None
    shown = "; ".join(f"{n} row(s): {p}" for p, n in problems.most_common(5))
    return (f"{sum(problems.values())} example(s) look filed in the wrong place. {shown}. "
            "If a category was renamed on purpose, the SUB_PARENT table in export_aa.py "
            "needs the new name")


def _record_key(r):
    return json.dumps(r, sort_keys=True, ensure_ascii=False)


def last_publish_ms():
    """When aa-library.json last changed, from git, less an hour of margin (the
    commit lands a minute after Notion was read). Rows not edited since then
    cannot be what changed the feed, which is what keeps a harmless rename of a
    dropdown option from looking like a bulk edit. None if git cannot say: no git,
    or a shallow checkout, where `git log` would report the newest commit rather
    than the one that last touched the file."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=here,
                                 capture_output=True, text=True, timeout=20, check=True).stdout.strip()
        if shallow != "false":
            return None
        out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", "aa-library.json"], cwd=here,
                             capture_output=True, text=True, timeout=20, check=True).stdout.strip()
        return int(out) * 1000 - 3_600_000 if out else None
    except Exception:
        return None


def _link_key(r):
    return (r["videoId"] or r["url"], r["start"])


def check_bulk_edit(records, meta, old_records, since_ms=None):
    """Existing rows whose published content would change, many at once.
    Catches a fill-down on ANY column. Not counted: rows whose content is already
    published (the repair after a bad edit), brand-new rows (made within a day of
    the edit AND with a video and time never published before, so Greg typing a new
    row), and renames of a dropdown option (which do not touch a row's edit time).
    A row made a few hours ago whose video and time ARE already published is an
    existing row and is counted. Only rows edited since the feed last changed
    (`since_ms`) can have changed it; if git cannot say, the last 14 days."""
    if since_ms is None:
        since_ms = int(time.time() * 1000) - 14 * 86_400_000
    already = collections.Counter(_record_key(r) for r in old_records)
    published_links = {_link_key(r) for r in old_records}
    times = []
    for r, m in zip(records, meta):
        k = _record_key(r)
        if already[k] > 0:
            already[k] -= 1
            continue
        if m["edited"] <= since_ms:
            continue
        recent = m["created"] > m["edited"] - 86_400_000
        if recent and _link_key(r) not in published_links:
            continue
        times.append(m["edited"])
    times.sort()
    best, run = 0, 0
    for i, t in enumerate(times):
        run = run + 1 if i and t - times[i - 1] <= BULK_EDIT_WINDOW_MS else 1
        best = max(best, run)
    if best >= BULK_EDIT_MIN:
        return (f"{best} existing examples were changed inside two minutes. That is the "
                "shape of an accidental fill-down in the Notion table, so nothing was "
                "published. Look at the most recently edited rows in Notion. If the "
                "change is intended, run this workflow by hand and tick 'accept bulk changes'")
    return None


def fatal_problems(records, meta, old_records, problems, since_ms=None):
    fatal = []
    if problems:
        shown = problems[:8]
        more = f" (and {len(problems) - 8} more)" if len(problems) > 8 else ""
        fatal.append("Rows that cannot be published as written:\n  - " + "\n  - ".join(shown) + more)
    if len(records) < EXPECTED_MIN:
        fatal.append(f"only {len(records)} items, far below the expected ~449")
    if not accepting():
        msg = check_taxonomy(records)
        if msg:
            fatal.append(msg)
        if old_records:
            if len(records) < len(old_records) - SHRINK_LIMIT:
                fatal.append(f"{len(old_records) - len(records)} fewer examples than the "
                             "last export (rows deleted, or their Link cleared). If that is "
                             "on purpose, run this workflow by hand and tick 'accept bulk changes'")
            msg = check_bulk_edit(records, meta, old_records,
                                  since_ms if since_ms is not None else last_publish_ms())
            if msg:
                fatal.append(msg)
    return fatal


def warnings_for(records, skipped, old_records):
    warnings = []
    if skipped:
        shown = ", ".join(skipped[:4]) + (" ..." if len(skipped) > 4 else "")
        warnings.append(f"{len(skipped)} unfinished row(s) with no Link left out: {shown}")
    no_voice = [r for r in records if not r["voice"]]
    if no_voice:
        where = ", ".join(sorted({f"{r['area']}/{r['category']}" for r in no_voice}))
        warnings.append(f"{len(no_voice)} record(s) with no voice ({where})")
    dupes = [k for k, n in collections.Counter(
        (r["category"], r["voice"], r["videoId"] or r["url"], r["start"]) for r in records).items() if n > 1]
    if dupes:
        warnings.append(f"{len(dupes)} example(s) entered twice (same video, time, voice, category)")
    if not old_records:
        warnings.append("no previous feed to compare with, so the bulk-edit check was skipped")
    return warnings


def main():
    try:
        rows, n2i = query_rows()
        records, meta, problems, skipped = build_records(rows, n2i)
    except Exception as e:
        print("ERROR")
        print(f"Notion extraction failed: {e}")
        sys.exit(1)

    old_json, old_records = None, []
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            old_json = f.read()
        try:
            old_records = json.loads(old_json)
        except ValueError:
            old_records = []

    fatal = fatal_problems(records, meta, old_records, problems)
    if fatal:
        print("ERROR")
        print("Not published. The site keeps showing the last good data.")
        for line in fatal:
            print(line)
        sys.exit(1)

    new_json = json.dumps(records, ensure_ascii=False, sort_keys=True, indent=0)
    notes = warnings_for(records, skipped, old_records)
    note = ("  [" + "; ".join(notes) + "]") if notes else ""

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
