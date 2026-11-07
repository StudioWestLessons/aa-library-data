# aa-library-data

Public data feeds for the self-updating resource pages on
studiowestlessons.com. Despite the repo name — which predates the second
feed — this now hosts **two**:

| Feed | Page | Source | Exported by |
|---|---|---|---|
| `aa-library.json` | [Auditive Analysis Sound Library](https://studiowestlessons.com/aasoundlibrary) | Greg's Notion library | [export.yml](.github/workflows/export.yml), daily 13:07 UTC |
| `exercise-library.json` | [Exercise Library](https://studiowestlessons.com/exerciselibrary) | Greg's "Exercise Library" Google Doc | [export-exercises.yml](.github/workflows/export-exercises.yml), daily 13:23 UTC |

Each site page fetches its JSON (via `raw.githubusercontent.com`) on every
load, so a source edit reaches the site within a day with no manual step.
Each page also keeps an embedded copy of its data as fallback, so it still
works if the fetch ever fails.

This repo is public because the pages' visitors fetch the JSON directly —
the content is exactly what's already publicly visible on the site.

## Adding a row in Notion (what the export expects)

Greg types a Link, an Area, a Category, a Subcategory (when the category has them), a
Voice and an optional Note. The export works out the rest: the website (YouTube,
Instagram or TikTok) and the video id and start time from the Link. His Area is used
as typed; if it contradicts the Category's usual Area the publish stops with a message,
and a blank Area falls back to the Category's usual one. The row's title ("Label (optional)") is free text and nothing reads it. A
row with no Link is treated as unfinished: it is left out and mentioned, it does not
stop the export. The database has a "Check" column that says OK or what to fix, and
an "Add here (newest first)" view; both are for Greg's eyes, the export ignores them.
The export reads the Default view by id (`VIEW_ID` in `export_aa.py`), so adding or
filtering other views changes nothing. Do not delete that view.

## What stops a publish

The site keeps its last good data and an alert issue opens with the reason in it:

1. A row that cannot be published as written (the message names the row).
2. A subcategory under the wrong category, for example Husky under Call. The table is
   `SUB_PARENT` in `export_aa.py`; if a parent is renamed on purpose, update it.
3. Ten or more existing rows changed within two minutes (a Notion fill-down), or more
   than two examples gone since the last export (deleted, or their Link cleared). If that is intended, run the workflow by hand and tick
   "accept bulk changes".

Background: on 2026-11-07 a fill-down set 50 rows to Category "Call", 34 of them
Breathy, Closed, Dopey, Flowy and Lamented examples, and the old checks only counted rows.

## Things that will bite you

- **The exercise doc must stay shared "Anyone with the link can view."** If
  that's revoked, Google serves a sign-in page instead of HTML; the export
  detects this and fails loudly rather than publishing an empty library.
- **Both parsers are duplicated** in the private `studio-west-resources`
  repo, whose weekly/monthly sync checks guard these pipelines by diffing
  each source against the published JSON. The Notion parser pairs with
  `export_aa.py` (the block between the SHARED markers is a verbatim copy in
  `aa-library/sync_check.py`; the guards below it are not mirrored); the doc parser
  pairs with `parse_exercises.py`. **Change both sides together.**
- **Never hand-edit the JSON files** — the next export overwrites them.
  Edit the source (Notion, or the doc).
- Both exports commit a dated `.heartbeat` if the repo goes 45+ days with no
  commits, because GitHub disables scheduled workflows in public repos after
  60 days of inactivity and its warning email never arrives.
- Alert issues @mention and assign the repo owner because that's what
  triggers GitHub Mobile push; email delivery to the account is broken.

Everything here is generated/maintained by Claude sessions.
