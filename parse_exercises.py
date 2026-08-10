"""
Parses the "Exercise Library" Google Doc into a nested outline structure.

The doc (https://docs.google.com/document/d/1_raReMGaNc7UIos6AGHWMvn3k4gHQgdDybGLR5vEu7M)
is a plain nested bullet/numbered list under a handful of bold section headers
("Power:", "Source:", "Filter:", "Silent Practice Exercises:"). There is no
per-item metadata (no descriptions yet) -- just names and nesting.

Google's HTML export (?format=html) represents list nesting as a run of
sibling <li> elements inside a <ul>/<ol> whose class name embeds the level as
a "-N" suffix (e.g. "lst-kix_3f8g2h-1" = level 1). It does NOT nest <ul>
inside <li> the way hand-written HTML would, so nesting is read from that
class suffix rather than from DOM depth.

Each <li> also carries a "li-bullet-N" class, but N there is NOT the nesting
level (observed constant at 0 regardless of depth) -- it's some other
Google-internal counter. Nesting level comes only from the enclosing
<ul>/<ol>'s "lst-kix_..._-N" class.

Shared by:
- The one-off build that generated the page's initial embedded data.
- sync_check.py, which re-parses the doc every month and diffs the result
  against what's embedded in the live page.
"""
import re
from html.parser import HTMLParser

SECTION_ORDER = ["Power", "Source", "Filter", "Silent Practice Exercises"]

_LIST_LEVEL_RE = re.compile(r"lst-kix_[^-\s\"]+-(\d+)")


class _DocHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = {name: [] for name in SECTION_ORDER}
        self._stack = []          # list of (level, node)
        self._current_section = None
        self._in_li = False
        self._li_level = None
        self._li_text = []
        self._in_p = False
        self._p_text = []
        self.unresolved_levels = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "p":
            self._in_p = True
            self._p_text = []
        elif tag in ("ul", "ol"):
            cls = attrs.get("class", "")
            m = _LIST_LEVEL_RE.search(cls)
            if m:
                self._pending_level = int(m.group(1))
        elif tag == "li":
            self._in_li = True
            self._li_text = []
            self._li_level = getattr(self, "_pending_level", None)
            if self._li_level is None:
                self.unresolved_levels += 1
                self._li_level = 0

    def handle_endtag(self, tag):
        if tag == "p":
            self._in_p = False
            text = "".join(self._p_text).strip()
            clean = text.replace("*", "").strip()
            m = re.match(r"^([A-Za-z][A-Za-z ]*):$", clean)
            if m and m.group(1) in self.sections:
                self._current_section = m.group(1)
                self._stack = []
        elif tag == "li":
            self._in_li = False
            text = "".join(self._li_text).strip()
            if text and self._current_section:
                node = {"name": text, "children": []}
                level = self._li_level
                while self._stack and self._stack[-1][0] >= level:
                    self._stack.pop()
                if not self._stack:
                    self.sections[self._current_section].append(node)
                else:
                    self._stack[-1][1]["children"].append(node)
                self._stack.append((level, node))

    def handle_data(self, data):
        if self._in_li:
            self._li_text.append(data)
        elif self._in_p:
            self._p_text.append(data)


def parse_doc_html(html):
    """Parse a Google Docs HTML export into {section_name: [nested nodes]}.

    Raises ValueError if any list item's nesting level couldn't be determined
    (export format changed in a way this parser doesn't handle) or if none of
    the expected section headers were found -- callers should treat either as
    "not safe to compare" rather than silently producing a wrong tree.
    """
    parser = _DocHTMLParser()
    parser.feed(html)
    if parser.unresolved_levels:
        raise ValueError(
            f"{parser.unresolved_levels} list item(s) had no resolvable nesting "
            f"level -- Google's export format may have changed."
        )
    sections = {name: parser.sections[name] for name in SECTION_ORDER}
    if not any(sections.values()):
        raise ValueError("no known section headers found in the doc export")
    return sections


def flatten(nodes, prefix=()):
    """Yield (breadcrumb_tuple, name) for every leaf-and-branch node, depth-first."""
    for node in nodes:
        path = prefix + (node["name"],)
        yield path
        yield from flatten(node["children"], path)


def canonical_items(sections):
    """A flat, order-preserving, diff-friendly view: {section: [breadcrumb strings]}."""
    out = {}
    for name in SECTION_ORDER:
        out[name] = [" > ".join(path) for path in flatten(sections.get(name, []))]
    return out
