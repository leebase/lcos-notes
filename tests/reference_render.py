"""Independent reference for the U3 reading-view rules (CONTRACT.md: U3 > Reading view).

Parses with the system libcmark 0.30.2 through ctypes and applies the contract's text,
span and link rules. Wikilinks come from the accepted U1 `links` command, passed in.
"""
import ctypes
import ctypes.util

_lib = ctypes.CDLL("libcmark.so.0.30.2")
_P = ctypes.c_void_p
for name, res, args in [
    ("cmark_parse_document", _P, [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]),
    ("cmark_node_free", None, [_P]),
    ("cmark_node_get_type", ctypes.c_int, [_P]),
    ("cmark_node_first_child", _P, [_P]),
    ("cmark_node_next", _P, [_P]),
    ("cmark_node_get_literal", ctypes.c_char_p, [_P]),
    ("cmark_node_get_heading_level", ctypes.c_int, [_P]),
    ("cmark_node_get_list_type", ctypes.c_int, [_P]),
    ("cmark_node_get_list_start", ctypes.c_int, [_P]),
    ("cmark_node_get_list_delim", ctypes.c_int, [_P]),
    ("cmark_node_get_list_tight", ctypes.c_int, [_P]),
    ("cmark_node_get_start_line", ctypes.c_int, [_P]),
]:
    fn = getattr(_lib, name)
    fn.restype, fn.argtypes = res, args

(DOCUMENT, BLOCK_QUOTE, LIST, ITEM, CODE_BLOCK, HTML_BLOCK, CUSTOM_BLOCK, PARAGRAPH, HEADING,
 THEMATIC_BREAK, TEXT, SOFTBREAK, LINEBREAK, CODE, HTML_INLINE, CUSTOM_INLINE, EMPH, STRONG,
 LINK, IMAGE) = range(1, 21)
PLACEHOLDER = 0xF0000
RULE = "─" * 20


def _children(node):
    c = _lib.cmark_node_first_child(node)
    while c:
        yield c
        c = _lib.cmark_node_next(c)


def _literal(node):
    raw = _lib.cmark_node_get_literal(node)
    return raw.decode("utf-8") if raw else ""


class _R:
    def __init__(self, links, source_name):
        self.links = links
        self.source_name = source_name

    def display(self, link):
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
        kind = _lib.cmark_node_get_type(node)
        if kind == TEXT:
            return self.text(_literal(node))
        if kind == SOFTBREAK:
            return " ", [], []
        if kind == LINEBREAK:
            return "\n", [], []
        if kind == CODE:
            t = self.literal(_literal(node))
            return t, [(0, len(t), "code")], []
        if kind == HTML_INLINE:
            return self.literal(_literal(node)), [], []
        style = {EMPH: "em", STRONG: "strong", LINK: "url", IMAGE: "url"}.get(kind)
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
            spans += [(a + off, b + off, st) for a, b, st in s]
            links += [(a + off, b + off, r, res) for a, b, r, res in l]
        return text, spans, links

    def block(self, node):
        kind = _lib.cmark_node_get_type(node)
        if kind == PARAGRAPH:
            return self.inlines(node)
        if kind == HEADING:
            t, s, l = self.inlines(node)
            return t, s + [(0, len(t), f"h{_lib.cmark_node_get_heading_level(node)}")], l
        if kind == CODE_BLOCK:
            t = self.literal(_strip_nl(_literal(node)))
            return t, [(0, len(t), "codeblock")], []
        if kind == HTML_BLOCK:
            return self.literal(_strip_nl(_literal(node))), [], []
        if kind == THEMATIC_BREAK:
            return RULE, [(0, len(RULE), "rule")], []
        if kind == BLOCK_QUOTE:
            t, s, l = self.blocks(node, "\n\n")
            return t, s + [(0, len(t), "quote")], l
        if kind == LIST:
            ordered = _lib.cmark_node_get_list_type(node) == 2
            start = _lib.cmark_node_get_list_start(node)
            delim = ")" if _lib.cmark_node_get_list_delim(node) == 2 else "."
            inner = "\n" if _lib.cmark_node_get_list_tight(node) else "\n\n"
            text, spans, links = "", [], []
            for i, item in enumerate(_children(node)):
                prefix = f"{start + i}{delim} " if ordered else "• "
                t, s, l = _indent(prefix, *self.blocks(item, inner))
                if i:
                    text += "\n"
                off = len(text)
                text += t
                spans += [(a + off, b + off, st) for a, b, st in s]
                links += [(a + off, b + off, r, res) for a, b, r, res in l]
            return text, spans, links
        return "", [], []


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


def _parse(text, links):
    """Placeholders in, frontmatter out; returns (cmark document, frontmatter line count)."""
    lines = text.split("\n")
    for idx in sorted(range(len(links)), key=lambda i: (-links[i]["line"], -links[i]["col"])):
        ln = links[idx]
        line = lines[ln["line"] - 1]
        c = ln["col"] - 1
        assert line[c:c + len(ln["raw"])] == ln["raw"], (line, ln)
        lines[ln["line"] - 1] = line[:c] + chr(PLACEHOLDER + idx) + line[c + len(ln["raw"]):]
    removed = _frontmatter_end(lines)
    data = "\n".join(lines[removed:]).encode("utf-8")
    return _lib.cmark_parse_document(data, len(data), 0), removed


def blocks(text: str, links: list, source_path: str) -> list:
    """CONTRACT.md U4: top-level blocks as {"line", "offset"}."""
    doc, removed = _parse(text, links)
    try:
        r = _R(links, source_path.rsplit("/", 1)[-1][:-3])
        out, length = [], 0
        for i, c in enumerate(_children(doc)):
            if i:
                length += 2
            out.append({"line": _lib.cmark_node_get_start_line(c) + removed, "offset": length})
            length += len(r.block(c)[0])
        return out
    finally:
        _lib.cmark_node_free(doc)


def render(text: str, links: list, source_path: str) -> dict:
    """links: the U1 `links` output for this text, in document order."""
    doc, _removed = _parse(text, links)
    try:
        name = source_path.rsplit("/", 1)[-1][:-3]
        t, s, l = _R(links, name).blocks(doc, "\n\n")
    finally:
        _lib.cmark_node_free(doc)
    spans = sorted({(a, b, st) for a, b, st in s if a < b})
    return {"text": t,
            "spans": [{"start": a, "end": b, "style": st} for a, b, st in spans],
            "links": [{"start": a, "end": b, "raw": r, "resolved": res} for a, b, r, res in l]}
