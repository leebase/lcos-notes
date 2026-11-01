"""U3 core: reading-view rendering through lcos-notes-cli render (CONTRACT.md: U3 > Reading view)."""
import random

import pytest

from harness import cli, cli_json
from reference_render import render as reference

SAMPLE = """---
tags: [x]
---
# Title with [[A]]

Some *emph and **strong*** text,
soft break and `code [[A]]` here.\x20\x20
hard break [md](http://x) ![alt *e*](p.png)

> quote [[Missing]]
>
> - one
> - two

1. first
   continued

   para two
2) nope
3. second
   - nested [[A#H|al]]

```
code [[A]]
```

---
<b>html</b>
"""

SAMPLE_TEXT = (
    "Title with A\n\nSome emph and strong text, soft break and code [[A]] here.\nhard break md alt e\n\n"
    "quote Missing\n\n\u2022 one\n\u2022 two\n\n1. first continued\n\n   para two\n\n2) nope\n\n"
    "3. second\n   \u2022 nested al\n\ncode [[A]]\n\n" + "\u2500" * 20 + "\n\n<b>html</b>")


def _vault(tmp_path, notes):
    v = tmp_path / "v"
    v.mkdir()
    for name, data in notes.items():
        p = v / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return v


def _spans(r):
    return [(s["start"], s["end"], s["style"]) for s in r["spans"]]


def test_sample_exact(tmp_path):
    v = _vault(tmp_path, {"A.md": "", "R.md": SAMPLE})
    r = cli_json("render", v, "R.md")
    assert r["text"] == SAMPLE_TEXT
    assert _spans(r) == [
        (0, 12, "h1"), (11, 12, "link"), (19, 34, "em"), (28, 34, "strong"), (56, 66, "code"),
        (84, 86, "url"), (87, 92, "url"), (91, 92, "em"), (94, 120, "quote"), (100, 107, "unresolved"),
        (186, 188, "link"), (190, 200, "codeblock"), (202, 222, "rule")]
    assert r["links"] == [
        {"start": 11, "end": 12, "raw": "[[A]]", "resolved": "A.md"},
        {"start": 100, "end": 107, "raw": "[[Missing]]", "resolved": None},
        {"start": 186, "end": 188, "raw": "[[A#H|al]]", "resolved": "A.md"}]


def test_display_text_rules(tmp_path):
    v = _vault(tmp_path, {"A.md": "", "Sub/N.md": "[[A|]] [[A#]] [[#]] [[|x]] [[ # | ]] [[A#H]] [[#H]] ![[A]] [[Gone|g]]"})
    r = cli_json("render", v, "Sub/N.md")
    assert r["text"] == "A A N x N A > H H A g"
    assert [(l["start"], l["end"], l["resolved"]) for l in r["links"]] == [
        (0, 1, "A.md"), (2, 3, "A.md"), (4, 5, "Sub/N.md"), (6, 7, "Sub/N.md"), (8, 9, "Sub/N.md"),
        (10, 15, "A.md"), (16, 17, "Sub/N.md"), (18, 19, "A.md"), (20, 21, None)]
    assert [s for s in _spans(r) if s[2] == "unresolved"] == [(20, 21, "unresolved")]


def test_wikilink_is_an_ordinary_character_for_markdown(tmp_path):
    # As a single ordinary character, the link sits inside intraword emphasis, and a
    # bracketed link never becomes a Markdown reference link.
    v = _vault(tmp_path, {"A.md": "", "N.md": "foo*[[A]]*bar\n\n[[A]]\n\n[A]: http://x\n"})
    r = cli_json("render", v, "N.md")
    assert r["text"] == "fooAbar\n\nA"
    assert _spans(r) == [(3, 4, "em"), (3, 4, "link"), (9, 10, "link")]


def test_literal_contexts_show_raw_links(tmp_path):
    v = _vault(tmp_path, {"A.md": "", "N.md": "    indented [[A]]\n\n<div>[[A]]</div>\n\n[t]([[A]] \"[[A]]\") `x`"})
    r = cli_json("render", v, "N.md")
    assert r["text"] == "indented [[A]]\n\n<div>[[A]]</div>\n\nt x"
    assert r["links"] == []
    assert _spans(r) == [(0, 14, "codeblock"), (34, 35, "url"), (36, 37, "code")]


def test_list_indentation_moves_spans(tmp_path):
    v = _vault(tmp_path, {"A.md": "", "N.md": "10) **a**\n    - *b* [[A]]\n\n      ```\n      c\n      ```\n"})
    r = cli_json("render", v, "N.md")
    assert r["text"] == "10) a\n    • b A\n\n      c"
    assert _spans(r) == [(4, 5, "strong"), (12, 13, "em"), (14, 15, "link"), (23, 24, "codeblock")]


def test_crlf_frontmatter_and_empty(tmp_path):
    v = _vault(tmp_path, {"A.md": "", "C.md": b"---\r\nk: [[A]]\r\n...\r\n# H [[A]]\r\n\r\nx\r\ny",
                          "E.md": "", "F.md": "---\nonly\n"})
    r = cli_json("render", v, "C.md")
    assert r["text"] == "H A\n\nx y"
    assert r["links"] == [{"start": 2, "end": 3, "raw": "[[A]]", "resolved": "A.md"}]
    assert cli_json("render", v, "E.md") == {"text": "", "spans": [], "links": []}
    # No closing line: no frontmatter, so the first line is a thematic break.
    assert cli_json("render", v, "F.md")["text"] == "─" * 20 + "\n\nonly"


def test_render_refusals(tmp_path):
    v = _vault(tmp_path, {"Bad.md": b"\xff\xfe [[A]]", "A.md": ""})
    for note in ("Bad.md", "Missing.md"):
        proc = cli("render", v, note, check=False)
        assert proc.returncode == 2
        assert proc.stdout == b""
        assert proc.stderr.decode().startswith("refused: ")


# --- differential check against the independent reference -------------------------

INLINE = ["word", "\U0001F600 grin", "Café", "日本", "*em*", "**strong**", "_u_", "***both***", "`code`",
          "`[[A]]`", "[md](x.md)", "![img](p.png)", "[[A]]", "[[B]]", "[[Missing]]", "![[A]]",
          "[[A#H]]", "[[A|al]]", "[[#H]]", "[[ ]]", "[[Sub/C]]", "*[[A]]*", "**x [[B]] y**",
          "[see [[A]]](u)", "<i>[[A]]</i>", "\\*esc\\*", "&amp;", "a*b*c", "foo*[[A]]*bar", "x  \ny",
          "line\\\nnext", "#tag", "[[A]]x", "x[[A]]", "<http://e.x>"]


def _inline(rng):
    return " ".join(rng.choice(INLINE) for _ in range(rng.randint(1, 5)))


def _block(rng, depth=0):
    k = rng.randrange(11 if depth < 2 else 7)
    if k == 0:
        return "#" * rng.randint(1, 6) + " " + _inline(rng)
    if k == 1:
        return "```\n" + _inline(rng) + "\n```"
    if k == 2:
        return "    " + _inline(rng)
    if k == 3:
        return rng.choice(["---", "***", "<div>[[A]]</div>", "<!-- [[A]] -->"])
    if k in (4, 5, 6):
        return "\n".join(_inline(rng) for _ in range(rng.randint(1, 3)))
    if k in (7, 8):
        ordered = rng.random() < 0.5
        start = rng.randint(0, 12)
        delim = rng.choice([".", ")"])
        items = []
        for i in range(rng.randint(1, 4)):
            marker = f"{start + i}{delim} " if ordered else rng.choice(["- ", "* ", "+ "])
            body = _block(rng, depth + 1)
            if rng.random() < 0.3:
                body += "\n\n" + _block(rng, depth + 1)
            pad = " " * len(marker)
            items.append(marker + body.replace("\n", "\n" + pad))
        return ("\n\n" if rng.random() < 0.3 else "\n").join(items)
    inner = _block(rng, depth + 1)
    return "\n".join("> " + line if line else ">" for line in inner.split("\n"))


def _doc(rng):
    parts = []
    if rng.random() < 0.25:
        parts.append("---\ntags: [x]\nnote: [[A]]\n---")
    parts += [_block(rng) for _ in range(rng.randint(1, 7))]
    text = "\n\n".join(parts) + rng.choice(["", "\n"])
    return text.replace("\n", "\r\n") if rng.random() < 0.2 else text


@pytest.mark.parametrize("seed", range(40))
def test_render_matches_reference(tmp_path, seed):
    rng = random.Random(seed)
    docs = {f"D{i}.md": _doc(rng) for i in range(8)}
    v = _vault(tmp_path, {"A.md": "# H\n", "B.md": "", "Sub/C.md": "", **docs})
    for name, text in docs.items():
        links = cli_json("links", v, name)
        assert cli_json("render", v, name) == reference(text, links, name), (name, text)
