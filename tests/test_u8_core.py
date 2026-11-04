"""U8 core: highlights, callouts, embeds; `highlights` and `render`'s `images` (CONTRACT.md: U8)."""
import random
from pathlib import Path

import pytest

from harness import cli, cli_json
from reference_links import markdown_links
from reference_render import blocks as ref_blocks
from reference_render import highlights as ref_highlights
from reference_render import render as ref_render
from reference_render import tasks as ref_tasks
from test_u3_core import INLINE, _block, _vault
from test_u7_core import _table, _tasks
from u8_load import LOAD

ROOT = Path(__file__).resolve().parents[1]


def _spans(r, style=None):
    return [(s["start"], s["end"], s["style"]) for s in r["spans"] if style in (None, s["style"])]


# ---------------------------------------------------------------- highlights

HIGHLIGHTS = [
    ("==a==", "a", [(0, 1, "highlight")]),
    ("x ==b c== y", "x b c y", [(2, 5, "highlight")]),
    ("== a==", "== a==", []),                                   # no opener before a space
    ("==a ==", "==a ==", []),                                   # no closer after a space
    ("====", "====", []),
    ("===w==", "=w", [(1, 2, "highlight")]),
    ("==a==b==", "ab==", [(0, 1, "highlight")]),
    ("a==b==c", "abc", [(1, 2, "highlight")]),
    ("==x== and ==y==", "x and y", [(0, 1, "highlight"), (6, 7, "highlight")]),
    ("`==no==`", "==no==", [(0, 6, "code")]),                   # literal text is never scanned
    ("==*em*==", "==em==", [(2, 4, "em")]),                     # an emphasis node ends the run
    ("*==em==*", "em", [(0, 2, "em"), (0, 2, "highlight")]),
    ("==[[A]]==", "A", [(0, 1, "highlight"), (0, 1, "link")]),
    ("==a\nb==", "==a b==", []),                                # a soft break ends the run
    ("# ==Head==", "Head", [(0, 4, "h1"), (0, 4, "highlight")]),
]


@pytest.mark.parametrize("source,text,spans", HIGHLIGHTS)
def test_highlight_delimiters_exact(tmp_path, source, text, spans):
    v = _vault(tmp_path, {"A.md": "", "H.md": source})
    r = cli_json("render", v, "H.md")
    assert (r["text"], _spans(r)) == (text, spans)


def test_highlights_command(tmp_path):
    v = _vault(tmp_path, {"A.md": "", "H.md": "==a== x ==[[A]]==\n\nnone here\n", "Bad.md": b"==\xff==\n"})
    assert cli_json("highlights", v, "H.md") == [{"start": 0, "end": 1, "text": "a"},
                                                 {"start": 4, "end": 5, "text": "A"}]
    for note in ("Bad.md", "Nope.md"):
        out = cli("highlights", v, note, check=False)
        assert out.returncode == 2 and out.stderr.decode().startswith("refused: ")


# ---------------------------------------------------------------- callouts

CALLOUTS = ("> [!warning]- Watch ==out==\n> body line\n> more\n>\n> second para\n\n"
            "> [!TIP]\n\n> [!x] **bold**\n\n> [!note]x\n\n> [!note] Title ^abc\n")


def test_callouts_exact(tmp_path):
    v = _vault(tmp_path, {"C.md": CALLOUTS})
    r = cli_json("render", v, "C.md")
    assert r["text"] == "Watch out\nbody line more\n\nsecond para\n\nTip\n\nbold\n\n[!note]x\n\nTitle"
    assert _spans(r) == [
        (0, 9, "callout-title"), (0, 37, "callout-warning"), (6, 9, "highlight"), (9, 37, "folded"),
        (39, 42, "callout-tip"), (39, 42, "callout-title"),
        (44, 48, "callout-note"), (44, 48, "callout-title"), (44, 48, "strong"),
        (50, 58, "quote"),                                      # no space before the title: a quote
        (60, 65, "callout-note"), (60, 65, "callout-title")]    # the block id is hidden
    assert cli_json("blocks", v, "C.md") == [
        {"line": 1, "offset": 0}, {"line": 5, "offset": 26}, {"line": 7, "offset": 39},
        {"line": 9, "offset": 44}, {"line": 11, "offset": 50}, {"line": 13, "offset": 60}]


def test_quotes_that_are_not_callouts(tmp_path):
    for i, body in enumerate(("> [!note", "> [! note]", "> text [!note]", "> [!no te]", "> [[!note]]", "> `[!note]`", "> [!note] a&#10;b")):
        (tmp_path / str(i)).mkdir()
        v = _vault(tmp_path / str(i), {"Q.md": body + "\n"})
        styles = {s for _a, _b, s in _spans(cli_json("render", v, "Q.md"))}
        assert "quote" in styles and not any(s.startswith("callout") for s in styles), body


# ---------------------------------------------------------------- embeds

A = ("---\ntags: [x]\n---\n# Alpha\n\nIntro [[B]] and [[#Sub]].\n\n## Sub\n\nsub text ^blk\n\n"
     "- [ ] task in A\n\n# Next\n\nafter\n")
E = "\n\n".join(["![[A]]", "![[A#Sub]]", "![[A#^blk]]", "![[red.png]]", "![[doc.pdf]]", "![[Nope]]",
                 "see ![[B]] inline", "![[A#Missing]]", "![[Bad]]", "![[Empty]]", "![[Code#H]]",
                 "![[Loop1]]", "![[D1]]", "![[Sub/S]]"]) + "\n"
EMBED_VAULT = {"A.md": A, "B.md": "b body\n", "E.md": E, "red.png": b"\x89PNG", "doc.pdf": b"%PDF",
               "Bad.md": b"\xff\n", "Empty.md": "", "Code.md": "```\n# H\n```\n",
               "Loop1.md": "one\n\n![[Loop2]]\n", "Loop2.md": "two\n\n![[Loop1]]\n",
               "D1.md": "d1\n\n![[D2]]\n", "D2.md": "d2\n\n![[D3]]\n", "D3.md": "d3\n\n![[D4]]\n",
               "D4.md": "d4\n\n![[D5]]\n", "D5.md": "d5\n",
               "Sub/S.md": "links [[C]] here\n", "Sub/C.md": "c\n", "C.md": "root c\n"}


def test_embeds_exact(tmp_path):
    v = _vault(tmp_path, EMBED_VAULT)
    r = cli_json("render", v, "E.md")
    whole = "Alpha\n\nIntro B and Sub.\n\nSub\n\nsub text\n\n☐ task in A\n\nNext\n\nafter"
    parts = [whole, "Sub\n\nsub text\n\n☐ task in A", "sub text", "￼", "doc.pdf", "Nope",
             "see B inline", "A > Missing", "Bad", "Empty", "Code > H", "one\n\ntwo\n\nLoop1",
             "d1\n\nd2\n\nd3\n\nD4", "links C here"]
    assert r["text"] == "\n\n".join(parts)
    assert r["images"] == [{"offset": 104, "path": "red.png"}]
    assert _spans(r) == [
        (0, 5, "h1"), (0, 64, "embed"), (13, 14, "link"), (19, 22, "link"), (25, 28, "h2"), (53, 57, "h1"),
        (66, 69, "h2"), (66, 92, "embed"), (94, 102, "embed"), (104, 105, "image"),
        (107, 114, "link"), (116, 120, "unresolved"), (126, 127, "link"), (136, 147, "link"),
        (149, 152, "link"), (154, 159, "link"), (161, 169, "link"),
        (171, 186, "embed"), (176, 186, "embed"), (181, 186, "link"),         # Loop1 > Loop2 > link
        (188, 202, "embed"), (192, 202, "embed"), (196, 202, "embed"), (200, 202, "link"),  # depth 3
        (204, 216, "embed"), (210, 211, "link")]
    assert [(l["start"], l["end"], l["raw"], l["resolved"]) for l in r["links"]] == [
        (13, 14, "[[B]]", "B.md"), (19, 22, "[[#Sub]]", "A.md"), (107, 114, "![[doc.pdf]]", "doc.pdf"),
        (116, 120, "![[Nope]]", None), (126, 127, "![[B]]", "B.md"), (136, 147, "![[A#Missing]]", "A.md"),
        (149, 152, "![[Bad]]", "Bad.md"), (154, 159, "![[Empty]]", "Empty.md"),
        (161, 169, "![[Code#H]]", "Code.md"), (181, 186, "![[Loop1]]", "Loop1.md"),
        (200, 202, "![[D4]]", "D4.md"),
        (210, 211, "[[C]]", cli_json("resolve", v, "Sub/S.md", "C")["resolved"])]   # resolved from S
    assert cli_json("blocks", v, "E.md") == [{"line": 2 * i + 1, "offset": o} for i, o in enumerate(
        [0, 66, 94, 104, 107, 116, 122, 136, 149, 154, 161, 171, 188, 204])]
    assert cli_json("tasks", v, "E.md") == []                    # embedded tasks are not the note's
    assert cli_json("highlights", v, "E.md") == []


def test_embeds_match_reference(tmp_path):
    v = _vault(tmp_path, EMBED_VAULT)
    text = E
    links = cli_json("links", v, "E.md")
    md = markdown_links(v, "E.md", text, links)
    assert cli_json("render", v, "E.md") == ref_render(text, links, "E.md", md, LOAD(v))


def test_a_note_does_not_embed_itself_and_tasks_stay_its_own(tmp_path):
    v = _vault(tmp_path, {"S.md": "- [x] mine\n\n![[S]]\n\n![[T]]\n", "T.md": "- [ ] theirs\n"})
    r = cli_json("render", v, "S.md")
    assert r["text"] == "☑ mine\n\nS\n\n☐ theirs"
    assert _spans(r) == [(0, 1, "task"), (2, 6, "done"), (8, 9, "link"), (11, 19, "embed")]
    assert cli_json("tasks", v, "S.md") == [{"line": 1, "col": 3, "checked": True, "offset": 0}]


# ---------------------------------------------------------------- random documents vs the reference

U8_INLINE = INLINE + ["==hl==", "==a b==", "== no==", "x==y==z", "==[[A]]==", "==*e*==", "*==e==*", "==`c`=="]


def _u8_inline(rng):
    return " ".join(rng.choice(U8_INLINE) for _ in range(rng.randint(1, 4)))


def _callout(rng):
    head = rng.choice(["[!note]", "[!tip]", "[!WARNING]", "[!danger]-", "[!question]+", "[!quote]",
                       "[!custom]", "[!note]-", "[!note]x", "[! note]", "[!note"])
    title = rng.choice(["", " " + _u8_inline(rng), " Title ^b1"])
    body = [head + title] + [_u8_inline(rng) for _ in range(rng.randint(0, 2))]
    if rng.random() < 0.4:
        body += ["", rng.choice(["- item", "1. one", "> nested", _u8_inline(rng)])]
    return "\n".join("> " + b if b else ">" for b in body)


TARGETS = ["N0", "N1", "N2", "N0#Sec", "N1#Sec", "N2#^b2", "N1#^b1", "Missing", "pic.png", "doc.pdf",
           "N0#Nothing", "Sub/N3", "N3"]


def _note(rng, n):
    parts = []
    if rng.random() < 0.3:
        parts.append("---\ntitle: x\n---")
    for k in range(rng.randint(1, 6)):
        r = rng.randrange(9)
        if r == 0:
            parts.append("![[" + rng.choice(TARGETS) + "]]")
        elif r == 1:
            parts.append(_callout(rng))
        elif r == 2:
            parts.append(rng.choice(["# Sec", "## Sec", "# Other", "### Deep"]))
        elif r == 3:
            parts.append(_u8_inline(rng) + rng.choice(["", " ^b1", " ^b2"]))
        elif r == 4:
            parts.append(_tasks(rng))
        elif r == 5:
            parts.append(_table(rng))
        elif r == 6:
            parts.append("- ![[" + rng.choice(TARGETS) + "]]")
        else:
            parts.append(_block(rng))
    return "\n\n".join(parts) + "\n"


@pytest.mark.parametrize("seed", range(40))
def test_u8_render_blocks_tasks_highlights_match_reference(tmp_path, seed):
    rng = random.Random(8000 + seed)
    notes = {f"N{i}.md": _note(rng, i) for i in range(3)}
    notes["Sub/N3.md"] = _note(rng, 3)
    v = _vault(tmp_path, {"A.md": "# H\n", "B.md": "", "Sub/C.md": "", "pic.png": b"\x89PNG", "doc.pdf": b"%",
                          **notes})
    load = LOAD(v)
    for name, text in notes.items():
        links = cli_json("links", v, name)
        md = markdown_links(v, name, text, links)
        assert cli_json("render", v, name) == ref_render(text, links, name, md, load), (name, text)
        assert cli_json("blocks", v, name) == ref_blocks(text, links, name, md, load), (name, text)
        assert cli_json("tasks", v, name) == ref_tasks(text, links, name, md, load), (name, text)
        assert cli_json("highlights", v, name) == ref_highlights(text, links, name, md, load), (name, text)


# ---------------------------------------------------------------- documentation

def test_user_docs_cover_u8():
    """(The version strings are the current unit's: test_u9_core.)"""
    readme = (ROOT / "README.md").read_text()
    update, install = readme.find("sudo apt update\n"), readme.find("sudo apt install ./lcos-notes_")
    assert 0 <= update < install
    guide = (ROOT / "DOCUMENTATION.md").read_text()
    for term in ("highlight", "Edit > Highlight", "View > Highlights", "callout", "fold", "embed",
                 "image", "depth", "highlights", "![alt](file.png)", "PDF"):
        assert term.lower() in guide.lower(), term
    man = (ROOT / "data/lcos-notes-cli.1").read_text()
    assert "highlights" in man and "images" in man
