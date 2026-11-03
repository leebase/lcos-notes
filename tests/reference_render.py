"""Independent reference for the reading-view rules (CONTRACT.md: U3 > Reading view, as
changed by U4-U8).

Parses with the system libcmark-gfm 0.29.0.gfm.13 through ctypes, with exactly the
`table`, `tasklist` and `strikethrough` extensions attached and the option
CMARK_OPT_STRIKETHROUGH_DOUBLE_TILDE (CONTRACT.md U7), and applies the contract's text,
span and link rules. Wikilinks come from the accepted U1 `links` command, passed in.
U8 embeds read other notes through `load(path) -> (text or None, links, md)`; see `loader`.
"""
import ctypes
import re
import unicodedata

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
    (_lib, "cmark_node_get_end_line", ctypes.c_int, [_P]),
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
OBJECT = "\ufffc"                                         # CONTRACT.md U8: an embedded image
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
CALLOUT = re.compile(r"\[!([A-Za-z0-9_-]+)\]([+-]?)(?:[ \t]+(.*))?")
KINDS = ("note", "tip", "warning", "danger", "question", "quote")
MAX_DEPTH = 3


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
    def __init__(self, links, source_name, body=(), load=None, stack=(), depth=0):
        self.links = links
        self.source_name = source_name
        self.body = body                                    # the parsed bytes, split at b"\n"
        self.load = load                                    # U8: reads embedded notes
        self.stack = stack                                  # U8: vault paths being rendered
        self.depth = depth                                  # U8: embedding depth of this content

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

    def inlines(self, node, nodes=None):
        """CONTRACT.md U8: runs of sibling text nodes are scanned for ==highlights==."""
        nodes = list(_children(node)) if nodes is None else nodes
        parts, run = [], []
        for c in nodes + [None]:
            if c is not None and _kind(c) == "text":
                run.append(_literal(c))
                continue
            if run:
                parts.append(self.highlights("".join(run)))
                run = []
            if c is not None:
                parts.append(self.inline(c))
        text, spans, links = "", [], []
        for t, s, l in parts:
            off = len(text)
            text += t
            spans += [(a + off, b + off, st) for a, b, st in s]
            links += [(a + off, b + off, r, res) for a, b, r, res in l]
        return text, spans, links

    def highlights(self, s):
        pieces, i, last = [], 0, 0
        while i < len(s):
            if s.startswith("==", i) and i + 2 < len(s) and not _space(s[i + 2]) and s[i + 2] != "=":
                j = i + 3
                while j < len(s) - 1 and not (s.startswith("==", j) and not _space(s[j - 1])):
                    j += 1
                if j < len(s) - 1 and s.startswith("==", j):
                    pieces += [(s[last:i], False), (s[i + 2:j], True)]
                    i = last = j + 2
                    continue
            i += 1
        pieces.append((s[last:], False))
        text, spans, links = "", [], []
        for piece, marked in pieces:
            t, sp, l = self.text(piece)
            off = len(text)
            text += t
            spans += [(a + off, b + off, st) for a, b, st in sp]
            links += [(a + off, b + off, r, res) for a, b, r, res in l]
            if marked:
                spans.append((off, off + len(t), "highlight"))
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

    def blocks(self, node, sep, nodes=None):
        text, spans, links = "", [], []
        for i, c in enumerate(list(_children(node)) if nodes is None else nodes):
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
            embedded = self.embed(node)
            if embedded is not None:
                return embedded
            kids = list(_children(node))
            return _hide_id(*self.inlines(node), kids[-1:])
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
            callout = self.callout(node)
            if callout is not None:
                return callout
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

    def callout(self, node):
        """CONTRACT.md U8: a block quote whose first paragraph's head is [!type][+-] title."""
        kids = list(_children(node))
        if not kids or _kind(kids[0]) != "paragraph":
            return None
        inl = list(_children(kids[0]))
        cut = next((i for i, c in enumerate(inl) if _kind(c) in ("softbreak", "linebreak")), len(inl))
        head, rest = inl[:cut], inl[cut + 1:]
        h, hs, hl = self.inlines(kids[0], head)
        if not rest:
            h, hs, hl = _hide_id(h, hs, hl, head[-1:])
        m = CALLOUT.fullmatch(h)
        if not m or any(a < m.end(2) for a, _b, _st in hs) or any(a < m.end(2) for a, *_x in hl):
            return None
        kind_ = m.group(1).lower() if m.group(1).lower() in KINDS else "note"
        if m.group(3):
            k = m.start(3)
            title = (h[k:], [(max(a - k, 0), b - k, st) for a, b, st in hs if b - k > 0],
                     [(a - k, b - k, r, res) for a, b, r, res in hl])
        else:
            title = (m.group(1)[:1].upper() + m.group(1)[1:].lower(), [], [])
        parts = []
        if rest:
            r = _hide_id(*self.inlines(kids[0], rest), rest[-1:])
            if r[0]:
                parts.append((None, r))
        parts += [(c, self.block(c)) for c in kids[1:]]
        text, spans, links = title[0], list(title[1]) + [(0, 0, ("@", kids[0]))], list(title[2])
        tl = len(text)
        for i, (c, (t, s, l)) in enumerate(parts):
            text += "\n" if i == 0 else "\n\n"
            off = len(text)
            text += t
            if c is not None:
                spans.append((off, off, ("@", c)))
            spans += [(a + off, b + off, st) for a, b, st in s]
            links += [(a + off, b + off, r, res) for a, b, r, res in l]
        spans += [(0, len(text), "callout-" + kind_), (0, tl, "callout-title")]
        if m.group(2) == "-" and parts:
            spans.append((tl, len(text), "folded"))
        return text, spans, links

    def embed(self, node):
        """CONTRACT.md U8: a paragraph that is exactly one ![[embed]]; None when it is not."""
        kids = list(_children(node))
        if len(kids) != 1 or _kind(kids[0]) != "text":
            return None
        lit = _literal(kids[0]).strip()
        if len(lit) != 1 or ord(lit) < PLACEHOLDER:
            return None
        link = self.links[ord(lit) - PLACEHOLDER]
        if link.get("kind") != "wiki" or not link["embed"]:
            return None
        path = link["resolved"]
        if not path or self.load is None:
            return None
        if path.lower().endswith(IMAGE_EXT):
            return OBJECT, [(0, 1, "image"), (0, 1, ("I", path))], []
        if not path.lower().endswith(".md") or path in self.stack or self.depth >= MAX_DEPTH:
            return None
        text, links, md = self.load(path)
        if text is None:
            return None
        links = _merge(links, md)
        doc, removed, body = _parse(text, links)
        try:
            heading = (link["heading"] or "").strip()
            top = list(_children(doc))
            if not heading:
                part = top
            elif heading.startswith("^"):
                line = _block_line(text, heading[1:].strip())
                hits = [n for n in _preorder(doc) if line is not None and
                        _lib.cmark_node_get_start_line(n) + removed <= line <= _lib.cmark_node_get_end_line(n) + removed]
                part = hits[-1:]
            else:
                line = _heading_line(text, heading)
                start = [i for i, n in enumerate(top) if _kind(n) == "heading" and
                         _lib.cmark_node_get_start_line(n) + removed == line]
                part = []
                if start:
                    level = _lib.cmark_node_get_heading_level(top[start[0]])
                    part = [top[start[0]]]
                    for n in top[start[0] + 1:]:
                        if _kind(n) == "heading" and _lib.cmark_node_get_heading_level(n) <= level:
                            break
                        part.append(n)
            if not part:
                return None
            inner = _R(links, path.rsplit("/", 1)[-1][:-3], body, self.load, self.stack + (path,), self.depth + 1)
            t, s, l = inner.blocks(None, "\n\n", part)
        finally:
            _lib.cmark_node_free(doc)
        if not t:
            return None
        s = [(a, b, st) for a, b, st in s if st != "task" and not (isinstance(st, tuple) and st[0] in ("@", "T"))]
        return t, s + [(0, len(t), "embed")], l

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


def _hide_id(t, s, l, last):
    """CONTRACT.md U6: a trailing block id on the paragraph's last text node is not rendered."""
    if last and _kind(last[0]) == "text":
        m = BLOCK_ID.search(_literal(last[0]))
        if m:
            n = len(t) - len(m.group(0))
            return t[:n], [(min(a, n), min(b, n), st) for a, b, st in s], [x for x in l if x[1] <= n]
    return t, s, l


def _space(ch):
    """g_unichar_isspace: tab, newline, carriage return, form feed, or a Unicode separator."""
    return ch in "\t\n\r\f" or unicodedata.category(ch) in ("Zs", "Zl", "Zp")


BLOCK_KINDS = {"paragraph", "heading", "code_block", "html_block", "thematic_break", "block_quote",
               "item", "tasklist", "table", "table_row"}


def _preorder(node):
    """Block nodes except the document and lists, in pre-order (CONTRACT.md U6 `blocks`)."""
    for c in _children(node):
        kind = _kind(c)
        if kind in BLOCK_KINDS:
            yield c
        if kind in ("list", "block_quote", "item", "tasklist", "table"):
            yield from _preorder(c)


def _fold(s):
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", s).casefold())


def _lines(text):
    for i, line in enumerate(text.split("\n")):
        yield i + 1, line[:-1] if line.endswith("\r") else line


def _heading_line(text, heading):
    """U1's heading rule (the first ATX heading line whose text equals the heading)."""
    for n, line in _lines(text):
        m = re.match(r"( {0,3})(#{1,6})(?=[ \t]|$)", line)
        if not m:
            continue
        title = line[m.end():].strip(" \t")
        tail = title.rstrip("#")
        if len(tail) < len(title) and tail and tail[-1] in " \t":
            title = tail.strip(" \t")
        if _fold(title) == _fold(heading):
            return n
    return None


def _block_line(text, ident):
    """U5's block-reference rule: the first line outside fences ending in " ^id"."""
    if not ident or not re.fullmatch(r"[A-Za-z0-9-]+", ident):
        return None
    fence, size = "", 0
    for n, line in _lines(text):
        stripped = line.lstrip(" ")
        c = stripped[:1]
        run = len(stripped) - len(stripped.lstrip(c)) if c in ("`", "~") else 0
        hidden = bool(fence)
        if fence:
            if c == fence and run >= size:
                fence = ""
        elif run >= 3:
            hidden, fence, size = True, c, run
        body = line.rstrip(" \t")
        cut = max(body.rfind(" "), body.rfind("\t"))
        if not hidden and cut >= 0 and _fold(body[cut + 1:]) == _fold("^" + ident):
            return n
    return None


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


def loader(vault, cli_json, markdown_links):
    """load(path) for embeds: the note's text (None if it is not UTF-8) with its accepted U1
    `links` and its U5 Markdown note links."""
    from pathlib import Path
    def load(path):
        try:
            text = (Path(vault) / path).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            return None, [], []
        links = cli_json("links", vault, path)
        return text, links, markdown_links(vault, path, text, links)
    return load


def blocks(text: str, links: list, source_path: str, md=(), load=None) -> list:
    """CONTRACT.md U6 (replacing U4): block starts as {"line", "offset"}. md: U5 Markdown note links."""
    links = _merge(links, md)
    doc, removed, body = _parse(text, links)
    try:
        r = _R(links, source_path.rsplit("/", 1)[-1][:-3], body, load, (source_path,), 0)
        _t, spans, _l = r.blocks(doc, "\n\n")
        out = []
        for a, _b, st in spans:                              # CONTRACT.md U6: pre-order block starts
            if isinstance(st, tuple) and st[0] == "@":
                line = _lib.cmark_node_get_start_line(st[1]) + removed
                if not out or out[-1]["line"] != line:
                    out.append({"line": line, "offset": a})
        return out
    finally:
        _lib.cmark_node_free(doc)


def render(text: str, links: list, source_path: str, md=(), load=None) -> dict:
    """links: the U1 `links` output for this text, in document order; md: the U5 Markdown
    note links ({raw, text, path, line, col, resolved}); load: see `loader` (U8 embeds)."""
    links = _merge(links, md)
    doc, _removed, body = _parse(text, links)
    try:
        name = source_path.rsplit("/", 1)[-1][:-3]
        t, s, l = _R(links, name, body, load, (source_path,), 0).blocks(doc, "\n\n")
    finally:
        _lib.cmark_node_free(doc)
    spans = sorted({(a, b, st) for a, b, st in s if a < b and isinstance(st, str)})
    images = sorted((a, st[1]) for a, b, st in s if isinstance(st, tuple) and st[0] == "I")
    return {"text": t,
            "spans": [{"start": a, "end": b, "style": st} for a, b, st in spans],
            "links": [{"start": a, "end": b, "raw": r, "resolved": res} for a, b, r, res in l],
            "images": [{"offset": a, "path": p} for a, p in images]}


def highlights(text: str, links: list, source_path: str, md=(), load=None) -> list:
    """CONTRACT.md U8: the rendering's highlight spans as {"start", "end", "text"}."""
    r = render(text, links, source_path, md, load)
    return [{"start": x["start"], "end": x["end"], "text": r["text"][x["start"]:x["end"]]}
            for x in r["spans"] if x["style"] == "highlight"]


def tasks(text: str, links: list, source_path: str, md=(), load=None) -> list:
    """CONTRACT.md U7: task items in document order as {"line", "col", "checked", "offset"}."""
    links = _merge(links, md)
    doc, removed, body = _parse(text, links)
    try:
        r = _R(links, source_path.rsplit("/", 1)[-1][:-3], body, load, (source_path,), 0)
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
