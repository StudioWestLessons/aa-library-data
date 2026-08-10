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

## Things that will bite you

- **The exercise doc must stay shared "Anyone with the link can view."** If
  that's revoked, Google serves a sign-in page instead of HTML; the export
  detects this and fails loudly rather than publishing an empty library.
- **Both parsers are duplicated** in the private `studio-west-resources`
  repo, whose weekly/monthly sync checks guard these pipelines by diffing
  each source against the published JSON. The Notion parser pairs with
  `export_aa.py`; the doc parser pairs with `parse_exercises.py`. **Change
  both sides together.**
- **Never hand-edit the JSON files** — the next export overwrites them.
  Edit the source (Notion, or the doc).
- Both exports commit a dated `.heartbeat` if the repo goes 45+ days with no
  commits, because GitHub disables scheduled workflows in public repos after
  60 days of inactivity and its warning email never arrives.
- Alert issues @mention and assign the repo owner because that's what
  triggers GitHub Mobile push; email delivery to the account is broken.

Everything here is generated/maintained by Claude sessions.
