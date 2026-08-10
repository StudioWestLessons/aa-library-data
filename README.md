# aa-library-data

Public data feed for the [Auditive Analysis Sound Library](https://studiowestlessons.com/aasoundlibrary)
page on studiowestlessons.com.

`aa-library.json` is exported daily from Greg's Notion library by
[export.yml](.github/workflows/export.yml). The site page fetches it (via
`raw.githubusercontent.com`) on every load, so Notion edits reach the site
within a day with no manual step. The page keeps an embedded copy of the data
as fallback, so it still works if this fetch ever fails.

This repo is public because the page's visitors fetch the JSON directly —
the content is exactly what's already publicly visible on the site.

Guarded by the weekly `aa-library` sync check in the private
`studio-west-resources` repo, which diffs Notion against this JSON and pages
Greg on persistent drift. The Notion parser is duplicated between that check
and `export_aa.py` here — **change both together**.

Everything here is generated/maintained by Claude sessions; hand-edits to
`aa-library.json` will be overwritten by the next export.
