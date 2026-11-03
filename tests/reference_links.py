"""Independent reference for U5 Markdown note links (CONTRACT.md: U5 > Markdown note links).

`prose` mirrors the accepted U1/U2 mask (fenced code, matched inline code spans, a
recognized wikilink is one token). Wikilinks themselves come from the accepted U1 `links`
command, passed in.
"""
import os
import re
import unicodedata

_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*:")


def prose(text: str) -> list:
    """True for every code point of text that is prose."""
    mask = [True] * len(text)
    fence, fence_len = "", 0
    start = 0
    while start < len(text):
        end = text.find("\n", start)
        if end < 0:
            end = len(text)
        s = text[start:end]
        stripped = s.lstrip(" ")
        first = len(s) - len(stripped)
        c = stripped[0] if stripped else ""
        run = 0
        if c in ("`", "~"):
            while first + run < len(s) and s[first + run] == c:
                run += 1
        hidden = bool(fence)
        if fence:
            if c == fence and run >= fence_len:
                fence = ""
        elif run >= 3:
            fence, fence_len, hidden = c, run, True
        if hidden:
            for k in range(start, end):
                mask[k] = False
        else:
            i = start
            while i < end:
                embed = text[i] == "!" and text.startswith("[[", i + 1)
                op = i + (1 if embed else 0)
                if text.startswith("[[", op):
                    close = text.find("]]", op + 2)
                    if 0 <= close < end and close > op + 2 and not set(text[op + 2:close]) & set("[]\r\n"):
                        i = close + 2
                        continue
                if text[i] != "`":
                    i += 1
                    continue
                n = 1
                while i + n < end and text[i + n] == "`":
                    n += 1
                j, found = i + n, False
                while j < end:
                    if text[j] != "`":
                        j += 1
                        continue
                    m = 1
                    while j + m < end and text[j + m] == "`":
                        m += 1
                    if m == n:
                        for k in range(i, j + m):
                            mask[k] = False
                        i, found = j + m, True
                        break
                    j += m
                if not found:
                    i += n
        start = end + 1
    return mask


def _decode(s):
    out, i, b = bytearray(), 0, s.encode("utf-8")
    while i < len(b):
        if b[i:i + 1] == b"%" and len(b) >= i + 3 and all(chr(x) in "0123456789abcdefABCDEF" for x in b[i + 1:i + 3]):
            out.append(int(b[i + 1:i + 3], 16))
            i += 3
        else:
            out.append(b[i])
            i += 1
    return bytes(out).decode("utf-8")  # raises on invalid UTF-8


def mdlinks(text: str, wikilinks: list) -> list:
    """[{raw, text, path, heading, line, col}] without resolution."""
    mask = prose(text)
    lines = text.split("\n")
    taken = set()                                   # absolute code point offsets in wikilinks
    starts = [0]
    for ln in lines[:-1]:
        starts.append(starts[-1] + len(ln) + 1)
    for w in wikilinks:
        a = starts[w["line"] - 1] + w["col"] - 1
        taken.update(range(a, a + len(w["raw"])))
    out = []
    for li, line in enumerate(lines):
        base, i, n = starts[li], 0, len(line)
        while i < n:
            if line[i] != "[" or (i and line[i - 1] in "!\\"):
                i += 1
                continue
            j = i + 1
            while j < n and line[j] not in "[]\r":
                j += 1
            if not (j + 1 < n and line[j] == "]" and line[j + 1] == "("):
                i += 1
                continue
            k = j + 2
            if k < n and line[k] == "<":
                m = k + 1
                while m < n and line[m] not in "<>\r":
                    m += 1
                if not (m + 1 < n and line[m] == ">" and line[m + 1] == ")"):
                    i += 1
                    continue
                dest, end = line[k + 1:m], m + 2
            else:
                m = k
                while m < n and line[m] not in " \t()<\r":
                    m += 1
                if m == k or m >= n or line[m] != ")":
                    i += 1
                    continue
                dest, end = line[k:m], m + 1
            span = range(base + i, base + end)
            if not all(mask[p] for p in span) or any(p in taken for p in span) \
                    or _SCHEME.match(dest) or dest.startswith("//"):
                i += 1
                continue
            raw_path, sep, raw_head = dest.partition("#")
            try:
                path, heading = _decode(raw_path), (_decode(raw_head).strip(" ") if sep else None)
            except UnicodeDecodeError:
                i += 1
                continue
            if not path and not sep:
                i += 1
                continue
            out.append({"raw": line[i:end], "text": line[i + 1:j], "path": path, "heading": heading,
                        "line": li + 1, "col": i + 1})
            i = end
    return out


def fold(s):
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", s).casefold())


def vault_files(root) -> list:
    out = []
    for cur, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not os.path.islink(os.path.join(cur, d)))
        for f in files:
            p = os.path.join(cur, f)
            if not f.startswith(".") and not os.path.islink(p) and os.path.isfile(p):
                out.append(os.path.relpath(p, root).replace(os.sep, "/"))
    return sorted(out, key=lambda s: s.encode())


def _collapse(parts):
    out = []
    for p in parts:
        if p in ("", "."):
            continue
        if p == "..":
            if not out:
                return None
            out.pop()
        else:
            out.append(p)
    return "/".join(out)


def candidates(source: str, path: str) -> list:
    d = source.rsplit("/", 1)[0] if "/" in source else ""
    out = []

    def add(p):
        if p is None or p == "":
            return
        out.append(p)
        if not p.lower().endswith(".md"):
            out.append(p + ".md")

    if path.startswith("/"):
        add(_collapse(path[1:].split("/")))
    else:
        add(_collapse((d.split("/") if d else []) + path.split("/")))
        add(_collapse(path.split("/")))
    return out


def resolve(files: list, source: str, path: str):
    if path == "":
        return source
    for c in candidates(source, path):
        hits = [f for f in files if fold(f) == fold(c)]
        if hits:
            exact = [f for f in hits if f == c]
            return (exact or sorted(hits, key=lambda s: s.encode()))[0]
    return None


def markdown_links(vault, source: str, text: str, wikilinks: list) -> list:
    """Reference `mdlinks` output: parsed links with their resolution."""
    files = vault_files(vault)
    return [{**d, "resolved": resolve(files, source, d["path"])} for d in mdlinks(text, wikilinks)]


def _low(s):
    return "".join(c.lower() if len(c.lower()) == 1 else c for c in s)


def _word(c):
    return c.isalnum() or c == "_"


def frontmatter_lines(text: str) -> int:
    """Number of leading lines that are frontmatter (U2 definition)."""
    lines = text.split("\n")
    bare = [l[:-1] if l.endswith("\r") else l for l in lines]
    if not bare or bare[0] != "---":
        return 0
    for i in range(1, len(bare)):
        if bare[i] in ("---", "..."):
            return i + 1
    return 0


def mentions(text: str, name: str, wikilinks: list, md: list) -> list:
    """CONTRACT.md U6 unlinked mentions of `name` in one note: [(line, col, line_text)]."""
    mask = prose(text)
    lines = text.split("\n")
    starts = [0]
    for ln in lines[:-1]:
        starts.append(starts[-1] + len(ln) + 1)
    taken = set()
    for l in list(wikilinks) + list(md):
        a = starts[l["line"] - 1] + l["col"] - 1
        taken.update(range(a, a + len(l["raw"])))
    q, out = _low(name), []
    for li in range(frontmatter_lines(text), len(lines)):
        line = lines[li]
        body = line[:-1] if line.endswith("\r") else line
        low, i = _low(body), 0
        while q and i + len(q) <= len(body):
            at = low.find(q, i)
            if at < 0:
                break
            end = at + len(q)
            span = range(starts[li] + at, starts[li] + end)
            ok = (at == 0 or not _word(body[at - 1])) and (end == len(body) or not _word(body[end])) \
                and all(mask[p] and p not in taken for p in span)
            if ok:
                out.append((li + 1, at + 1, body))
                i = end
            else:
                i = at + 1
    return out
