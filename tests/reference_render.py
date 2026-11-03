"""Independent reference for the reading-view rules (CONTRACT.md: U3 > Reading view, as
changed by U4-U7).

Parses with the system libcmark-gfm 0.29.0.gfm.13 through ctypes, with exactly the
`table`, `tasklist` and `strikethrough` extensions attached and the option
CMARK_OPT_STRIKETHROUGH_DOUBLE_TILDE (CONTRACT.md U7), and applies the contract's text,
span and link rules. Wikilinks come from the accepted U1 `links` command, passed in.
"""
import ctypes
import re

_lib = ctypes.CDLL("libcmark-gfm.so.0.29.0.gfm.13")
_ext = ctypes.CDLL("libcmark-gfm-extensions.so.0.29.0.gfm.13")
_P = ctypes.c_void_p
for lib, name, res, args in [
    (_lib, "cmark_parser_new", _P, [ctypes.c_int]),
    (_lib, "cmark_parser_free", None, [_P]),
    (_lib, "cmark_parser_feed", None, [_P, ctypes.c_char_p, ctypes.c_size_t]),
    (_lib, "cmark_parser_finish", _P, [_P]),
    (_lib, "cmark_find_syntax_extension", _P, [ctypes.c_char_p]),
    (_lib, "cmark_parser_attach_syntax_extension", ctypes.c_int, [_P, _P]),
    (_lib, "cmark_node_free", None, [_P]),
    (_lib, "cmark_node_get_type_string", ctypes.c_char_p, [_P]),
    (_lib, "cmark_node_first_child", _P, [_P]),
    (_lib, "cmark_node_next", _P, [_P]),
    (_lib, "cmark_node_get_literal", ctypes.c_char_p, [_P]),
    (_lib, "cmark_node_get_heading_level", ctypes.c_int, [_P]),
    (_lib, "cmark_node_get_list_type", ctypes.c_int, [_P]),
    (_lib, "cmark_node_get_list_start", ctypes.c_int, [_P]),
    (_lib, "cmark_node_get_list_delim", ctypes.c_int, [_P]),
    (_lib, "cmark_node_get_list_tight", ctypes.c_int, [_P]),
    (_lib, "cmark_node_get_start_line", ctypes.c_int, [_P]),
    (_lib, "cmark_node_get_start_column", ctypes.c_int, [_P]),
    (_ext, "cmark_gfm_core_extensions_ensure_registered", None, []),
    (_ext, "cmark_gfm_extensions_get_tasklist_item_checked", ctypes.c_bool, [_P]),
    (_ext, "cmark_gfm_extensions_get_table_columns", ctypes.c_uint16, [_P]),
    (_ext, "cmark_gfm_extensions_get_table_alignments", ctypes.POINTER(ctypes.c_uint8), [_P]),
]:
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = res, args
_ext.cmark_gfm_core_extensions_ensure_registered()
OPTIONS = 1 << 14                                           # CMARK_OPT_STRIKETHROUGH_DOUBLE_TILDE
EXTENSIONS = (b"table", b"tasklist", b"strikethrough")
PLACEHOLDER = 0xF0000
RULE = "\u2500" * 20
BOX = {False: "\u2610", True: "\u2611"}                  # CONTRACT.md U7: task boxes
BAR, CROSS = " \u2502 ", "\u2500\u253c\u2500"            # CONTRACT.md U7: table cell joints


def _kind(node):
    return _lib.cmark_node_get_type_string(node).decode()


def _children(node):
    c = _lib.cmark_node_first_child(node)
    while c:
        yield c
        c = _lib.cmark_node_next(c)


def _literal(node):
    raw = _lib.cmark_node_get_literal(node)
    return raw.decode("utf-8") if raw else ""


BLOCK_ID = re.compile(r"[ \t]+\^[A-Za-z0-9-]+$")          # CONTRACT.md U6: hidden in reading view


class _R:
    """Zero-length spans with style ("@", node) mark where a block's rendering starts (U6 blocks)."""
    def __init__(self, links, source_name, body=()):
        self.links = links
        self.source_name = source_name
        self.body = body                                    # the parsed bytes, split at b"\n"

    def marker(self, item):
        """CONTRACT.md U7: the item's task marker is the first "[" on its start line at or after
        its start column; returns (line, byte index of "[" in that line, checked)."""
        n = _lib.cmark_node_get_start_line(item)
        raw = self.body[n - 1]
        at = raw.index(b"[", _lib.cmark_node_get_start_column(item) - 1)
        # Not cmark_gfm_extensions_get_tasklist_item_checked: gfm.13 sets it when "[x]"
        # occurs anywhere later on the line.
        return n, at, raw[at + 1:at + 2] in (b"x", b"X")

    def display(self, link):
        if link.get("kind") == "markdown":                  # CONTRACT.md U5
            if link["text"]:
                return link["text"]
            for name in (link["resolved"], link["path"].rsplit("/", 1)[-1]):
                if name:
                    name = name.rsplit("/", 1)[-1]
                    return name[:-3] if name.lower().endswith(".md") else name
            return self.source_name
        if link["alias"]:
            return link["alias"]
        if link["heading"]:
            return f'{link["target"]} > {link["heading"]}' if link["target"] else link["heading"]
        return link["target"] or self.source_name

    def literal(self, s):
        """Literal text (code, HTML): placeholders become the raw link text, no link."""
        return "".join(self.links[ord(ch) - PLACEHOLDER]["raw"] if ord(ch) >= PLACEHOLDER else ch
                       for ch in s)

    def text(self, s):
        out, spans, found = [], [], []
        pos = 0
        for ch in s:
            if ord(ch) >= PLACEHOLDER:
                link = self.links[ord(ch) - PLACEHOLDER]
                d = self.display(link)
                spans.append((pos, pos + len(d), "link" if link["resolved"] else "unresolved"))
                found.append((pos, pos + len(d), link["raw"], link["resolved"]))
                out.append(d)
                pos += len(d)
            else:
                out.append(ch)
                pos += 1
        return "".join(out), spans, found

    def inlines(self, node):
        text, spans, links = "", [], []
        for c in _children(node):
            t, s, l = self.inline(c)
            off = len(text)
            text += t
            spans += [(a + off, b + off, st) for a, b, st in s]
            links += [(a + off, b + off, r, res) for a, b, r, res in l]
        return text, spans, links

    def inline(self, node):
        kind = _kind(node)
        if kind == "text":
            return self.text(_literal(node))
        if kind == "softbreak":
            return " ", [], []
        if kind == "linebreak":
            return "\n", [], []
        if kind == "code":
            t = self.literal(_literal(node))
            return t, [(0, len(t), "code")], []
        if kind == "html_inline":
            return self.literal(_literal(node)), [], []
        style = {"emph": "em", "strong": "strong", "link": "url", "image": "url",
                 "strikethrough": "strike"}.get(kind)
        t, s, l = self.inlines(node)
        if style:
            s = s + [(0, len(t), style)]
        return t, s, l

    def blocks(self, node, sep):
        text, spans, links = "", [], []
        for i, c in enumerate(_children(node)):
            t, s, l = self.block(c)
            if i:
                text += sep
            off = len(text)
            text += t
            spans += [(off, off, ("@", c))] + [(a + off, b + off, st) for a, b, st in s]
            links += [(a + off, b + off, r, res) for a, b, r, res in l]
        return text, spans, links

    def block(self, node):
        kind = _kind(node)
        if kind == "paragraph":
            t, s, l = self.inlines(node)
            last = list(_children(node))[-1:]
            if last and _kind(last[0]) == "text":
                m = BLOCK_ID.search(_literal(last[0]))
                if m:
                    n = len(t) - len(m.group(0))
                    t = t[:n]
                    s = [(min(a, n), min(b, n), st) for a, b, st in s]
                    l = [x for x in l if x[1] <= n]
            return t, s, l
        if kind == "heading":
            t, s, l = self.inlines(node)
            return t, s + [(0, len(t), f"h{_lib.cmark_node_get_heading_level(node)}")], l
        if kind == "code_block":
            t = self.literal(_strip_nl(_literal(node)))
            return t, [(0, len(t), "codeblock")], []
        if kind == "html_block":
            return self.literal(_strip_nl(_literal(node))), [], []
        if kind == "thematic_break":
            return RULE, [(0, len(RULE), "rule")], []
        if kind == "block_quote":
            t, s, l = self.blocks(node, "\n\n")
            return t, s + [(0, len(t), "quote")], l
        if kind == "list":
            ordered = _lib.cmark_node_get_list_type(node) == 2
            start = _lib.cmark_node_get_list_start(node)
            delim = ")" if _lib.cmark_node_get_list_delim(node) == 2 else "."
            inner = "\n" if _lib.cmark_node_get_list_tight(node) else "\n\n"
            text, spans, links = "", [], []
            for i, item in enumerate(_children(node)):
                number = f"{start + i}{delim} " if ordered else ""
                task = _kind(item) == "tasklist"
                if task:                                    # CONTRACT.md U7: the box replaces "• "
                    checked = self.marker(item)[2]
                    prefix = number + BOX[checked] + " "
                else:
                    prefix = number or "• "
                t, s, l = self.blocks(item, inner)
                if task and checked:
                    first = list(_children(item))[:1]
                    if first:
                        n = len(self.block(first[0])[0])
                        s = s + [(0, n, "done")]
                t, s, l = _indent(prefix, t, s, l)
                if task:
                    s = s + [(len(number), len(number) + 1, "task"), (len(number), len(number), ("T", item))]
                if i:
                    text += "\n"
                off = len(text)
                text += t
                spans += [(off, off, ("@", item))] + [(a + off, b + off, st) for a, b, st in s]
                links += [(a + off, b + off, r, res) for a, b, r, res in l]
            return text, spans, links
        if kind == "table":
            return self.table(node)
        return "", [], []

    def table(self, node):
        """CONTRACT.md U7: padded cells joined by " │ ", a rule under the header row."""
        ncols = _ext.cmark_gfm_extensions_get_table_columns(node)
        aligns = _ext.cmark_gfm_extensions_get_table_alignments(node)
        aligns = [chr(aligns[i]) if aligns[i] else "" for i in range(ncols)]
        rows = []
        for row in _children(node):
            cells = [self.inlines(c) for c in _children(row)]
            rows.append((row, _kind(row) == "table_header", cells))
        widths = [max([1] + [len(cells[j][0]) for _r, _h, cells in rows if j < len(cells)]) for j in range(ncols)]
        text, spans, links = "", [], []
        for k, (row, header, cells) in enumerate(rows):
            if k:
                text += "\n"
            spans.append((len(text), len(text), ("@", row)))
            for j in range(ncols):
                t, s, l = cells[j] if j < len(cells) else ("", [], [])
                if j:
                    text += BAR
                gap = widths[j] - len(t)
                left = gap if aligns[j] == "r" else gap // 2 if aligns[j] == "c" else 0
                off = len(text) + left
                text += " " * left + t + " " * (gap - left)
                spans += [(a + off, b + off, st) for a, b, st in s]
                links += [(a + off, b + off, r, res) for a, b, r, res in l]
                if header:
                    spans.append((off, off + len(t), "th"))
            if header:
                text += "\n" + CROSS.join("\u2500" * w for w in widths)
        return text, spans + [(0, len(text), "table")], links


def _strip_nl(s):
    return s[:-1] if s.endswith("\n") else s


def _indent(prefix, text, spans, links):
    """Prefix the first line; indent every later non-empty line by len(prefix) spaces."""
    pad = " " * len(prefix)
    inserts = [0]  # original positions where padding goes, with its length
    out, sizes = [prefix], [len(prefix)]
    for i, ch in enumerate(text):
        out.append(ch)
        if ch == "\n" and i + 1 < len(text) and text[i + 1] != "\n":
            inserts.append(i + 1)
            out.append(pad)
            sizes.append(len(pad))
    def start(o):
        return o + sum(n for p, n in zip(inserts, sizes) if p <= o)
    def end(o):
        return o + sum(n for p, n in zip(inserts, sizes) if p < o)
    return ("".join(out), [(start(a), end(b), st) for a, b, st in spans],
            [(start(a), end(b), r, res) for a, b, r, res in links])


def _frontmatter_end(lines):
    def bare(line):
        return line[:-1] if line.endswith("\r") else line
    if not lines or bare(lines[0]) != "---":
        return 0
    for i in range(1, len(lines)):
        if bare(lines[i]) in ("---", "..."):
            return i + 1
    return 0


def _merge(links, md):
    """Wikilinks and Markdown note links in document order (they never overlap)."""
    out = [dict(l, kind="wiki") for l in links] + [dict(m, kind="markdown") for m in md]
    return sorted(out, key=lambda l: (l["line"], l["col"]))


def _parse(text, links):
    """Placeholders in, frontmatter out; returns (cmark document, frontmatter line count, parsed lines)."""
    lines = text.split("\n")
    for idx in sorted(range(len(links)), key=lambda i: (-links[i]["line"], -links[i]["col"])):
        ln = links[idx]
        line = lines[ln["line"] - 1]
        c = ln["col"] - 1
        assert line[c:c + len(ln["raw"])] == ln["raw"], (line, ln)
        lines[ln["line"] - 1] = line[:c] + chr(PLACEHOLDER + idx) + line[c + len(ln["raw"]):]
    removed = _frontmatter_end(lines)
    data = "\n".join(lines[removed:]).encode("utf-8")
    parser = _lib.cmark_parser_new(OPTIONS)
    try:
        for name in EXTENSIONS:
            assert _lib.cmark_parser_attach_syntax_extension(parser, _lib.cmark_find_syntax_extension(name))
        _lib.cmark_parser_feed(parser, data, len(data))
        return _lib.cmark_parser_finish(parser), removed, data.split(b"\n")
    finally:
        _lib.cmark_parser_free(parser)


def blocks(text: str, links: list, source_path: str, md=()) -> list:
    """CONTRACT.md U6 (replacing U4): block starts as {"line", "offset"}. md: U5 Markdown note links."""
    links = _merge(links, md)
    doc, removed, body = _parse(text, links)
    try:
        _t, spans, _l = _R(links, source_path.rsplit("/", 1)[-1][:-3], body).blocks(doc, "\n\n")
        out = []
        for a, _b, st in spans:                              # CONTRACT.md U6: pre-order block starts
            if isinstance(st, tuple) and st[0] == "@":
                line = _lib.cmark_node_get_start_line(st[1]) + removed
                if not out or out[-1]["line"] != line:
                    out.append({"line": line, "offset": a})
        return out
    finally:
        _lib.cmark_node_free(doc)


def render(text: str, links: list, source_path: str, md=()) -> dict:
    """links: the U1 `links` output for this text, in document order; md: the U5 Markdown
    note links ({raw, text, path, line, col, resolved})."""
    links = _merge(links, md)
    doc, _removed, body = _parse(text, links)
    try:
        name = source_path.rsplit("/", 1)[-1][:-3]
        t, s, l = _R(links, name, body).blocks(doc, "\n\n")
    finally:
        _lib.cmark_node_free(doc)
    spans = sorted({(a, b, st) for a, b, st in s if a < b})
    return {"text": t,
            "spans": [{"start": a, "end": b, "style": st} for a, b, st in spans],
            "links": [{"start": a, "end": b, "raw": r, "resolved": res} for a, b, r, res in l]}


def tasks(text: str, links: list, source_path: str, md=()) -> list:
    """CONTRACT.md U7: task items in document order as {"line", "col", "checked", "offset"}."""
    links = _merge(links, md)
    doc, removed, body = _parse(text, links)
    try:
        r = _R(links, source_path.rsplit("/", 1)[-1][:-3], body)
        _t, spans, _l = r.blocks(doc, "\n\n")
        out = []
        for a, _b, st in sorted((x for x in spans if isinstance(x[2], tuple) and x[2][0] == "T"),
                                key=lambda x: x[0]):
            n, at, checked = r.marker(st[1])
            out.append({"line": n + removed, "col": len(body[n - 1][:at].decode("utf-8")) + 1,
                        "checked": checked, "offset": a})
        return out
    finally:
        _lib.cmark_node_free(doc)
