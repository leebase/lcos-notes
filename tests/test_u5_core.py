"""U5 core rules through lcos-notes-cli: Markdown note links, NFC names (CONTRACT.md: U5)."""
import json
import random
import re
import unicodedata

import pytest

from harness import cli, cli_json, tree_digest
from reference_links import markdown_links
from reference_render import blocks as ref_blocks, render as ref_render
from u8_load import LOAD                                    # U8: embeds read the vault
from test_u2_core import make
from test_u3_core import _doc

M=("See [one](Target.md) and [two](../Root%20Note.md#Some%20Head) and <[three](<Sub Dir/X.md>)>\n"
   "Not: ![img](Target.md) \\[esc](Target.md) [t](Target.md \"title\") [ext](https://x.y) [proto](//h/x) `[code](Target.md)` [[Target]](Target.md)\n"
   "```\n[f](Target.md)\n```\n"
   "[self](#Top) [empty]() [bad](%FF.md) [pct](100%25.md) [lit](50%.md) [](Target) [ci](target.MD)\n"
   "[up](../../Root%20Note.md) [abs](/Target) [pdf](files/doc.pdf) [miss](New/Thing) [hash](#) [a](x.md)[b](y.md)\r\n")

FILES = {"Sub/M.md": M, "Sub/Target.md": "# Top\n", "Target.md": "", "Root Note.md": "",
         "Sub/Sub Dir/X.md": "", "100%.md": "", "files/doc.pdf": "x"}

WANT = [
    # line, col, raw, text, path, heading, resolved
    (1, 5, "[one](Target.md)", "one", "Target.md", None, "Sub/Target.md"),
    (1, 26, "[two](../Root%20Note.md#Some%20Head)", "two", "../Root Note.md", "Some Head", "Root Note.md"),
    (1, 68, "[three](<Sub Dir/X.md>)", "three", "Sub Dir/X.md", None, "Sub/Sub Dir/X.md"),
    (6, 1, "[self](#Top)", "self", "", "Top", "Sub/M.md"),
    (6, 38, "[pct](100%25.md)", "pct", "100%.md", None, "100%.md"),
    (6, 55, "[lit](50%.md)", "lit", "50%.md", None, None),
    (6, 69, "[](Target)", "", "Target", None, "Sub/Target.md"),
    (6, 80, "[ci](target.MD)", "ci", "target.MD", None, "Sub/Target.md"),
    (7, 1, "[up](../../Root%20Note.md)", "up", "../../Root Note.md", None, None),
    (7, 28, "[abs](/Target)", "abs", "/Target", None, "Target.md"),
    (7, 43, "[pdf](files/doc.pdf)", "pdf", "files/doc.pdf", None, "files/doc.pdf"),
    (7, 64, "[miss](New/Thing)", "miss", "New/Thing", None, None),
    (7, 82, "[hash](#)", "hash", "", "", "Sub/M.md"),
    (7, 92, "[a](x.md)", "a", "x.md", None, None),
    (7, 101, "[b](y.md)", "b", "y.md", None, None),
]


def _md(v, note):
    return [(d["line"], d["col"], d["raw"], d["text"], d["path"], d["heading"], d["resolved"])
            for d in cli_json("mdlinks", v, note)]


def test_mdlinks_exact(tmp_path):
    v = make(tmp_path / "v", FILES)
    assert _md(v, "Sub/M.md") == WANT
    assert set(cli_json("mdlinks", v, "Sub/M.md")[0]) == {"raw", "text", "path", "heading", "line", "col", "resolved"}
    # `links` is unchanged: wikilinks only.
    assert [d["raw"] for d in cli_json("links", v, "Sub/M.md")] == ["[[Target]]"]


def test_mdlinks_refusals(tmp_path):
    v = make(tmp_path / "v", {"Bad.md": b"\xff [a](b.md)\n", "A.md": ""})
    for args in [("mdlinks", v, "Bad.md"), ("mdlinks", v, "Missing.md"), ("mdlinks", v, "../A.md")]:
        proc = cli(*args, check=False)
        assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: "), args


DESTS = ["A.md", "A", "a.MD", "B/C.md", "B/C", "../A.md", "../../A", "/A", "/B/C", "./A.md", "B//C.md",
         "B/./C", "Missing.md", "x%20y.md", "<x y.md>", "<B/C.md>", "img.png", "B/img.png", "#H", "#^blk",
         "A.md#Head", "A.md#%5Eid", "%41.md", "%e9t%C3%A9.md", "%ZZ.md", "https://e.x/A.md", "//A.md",
         "A.md \"t\"", "", "<>", "(A.md)", "Caf\u00e9.md", "Cafe\u0301.md"]
TEXTS = ["t", "", "two words", "**b**", "`c`", "a]b", "[[A]]"]
PRE = ["", " ", "!", "\\", "x", "`", "[[A]] "]


def _md_line(rng):
    parts = []
    for _ in range(rng.randint(1, 4)):
        parts.append(rng.choice(PRE) + "[" + rng.choice(TEXTS) + "](" + rng.choice(DESTS) + ")" +
                     rng.choice(["", " ", "`", "]", ")", "x"]))
    return "".join(parts)


def _md_doc(rng):
    lines = []
    for _ in range(rng.randint(1, 8)):
        k = rng.random()
        if k < 0.1:
            lines += ["```", _md_line(rng), "```"]
        elif k < 0.15:
            lines += ["~~~~", _md_line(rng)]                # may stay unclosed
        else:
            lines.append(_md_line(rng))
    text = "\n".join(lines) + rng.choice(["", "\n"])
    return text.replace("\n", "\r\n") if rng.random() < 0.2 else text


MD_VAULT = {"A.md": "# Head\n", "B/C.md": "", "B/D.md": "", "x y.md": "", "img.png": "p", "B/img.png": "p",
            "Caf\u00e9.md": "", "\u00e9t\u00e9.md": "", "Sub/A.md": ""}


def _ref(v, name, text):
    return markdown_links(v, name, text, cli_json("links", v, name))


@pytest.mark.parametrize("seed", range(40))
def test_mdlinks_match_reference(tmp_path, seed):
    rng = random.Random(20_000 + seed)
    docs = {rng.choice(["", "B/", "Sub/", "B/E/"]) + f"D{i}.md": _md_doc(rng) for i in range(6)}
    v = make(tmp_path / "v", {**MD_VAULT, **docs})
    for name, text in docs.items():
        assert cli_json("mdlinks", v, name) == _ref(v, name, text), (name, text)


def test_markdown_links_are_backlinks(tmp_path):
    v = make(tmp_path / "v", FILES)
    got = [(b["source"], b["line"], b["col"], b["raw"]) for b in cli_json("backlinks", v, "Sub/Target.md")]
    assert got == [("Sub/M.md", 1, 5, "[one](Target.md)"), ("Sub/M.md", 2, 119, "[[Target]]"),
                   ("Sub/M.md", 6, 69, "[](Target)"), ("Sub/M.md", 6, 80, "[ci](target.MD)")]
    got = [(b["source"], b["raw"]) for b in cli_json("backlinks", v, "Root Note.md")]
    assert got == [("Sub/M.md", "[two](../Root%20Note.md#Some%20Head)")]


RENAMES = [
    # files, old, new, {path: expected bytes after}
    ({"A.md": "[x](B.md) [y](B) [z](<B.md>)\n", "B.md": ""}, "B.md", "Sub/New Name",
     {"A.md": "[x](Sub/New%20Name.md) [y](Sub/New%20Name) [z](<Sub/New Name.md>)\n"}),
    ({"S/A.md": "[x](../B.md#Head%20One) [q](/B.md)\r\n", "B.md": "# Head One\n"}, "B.md", "T/B(2)",
     {"S/A.md": "[x](../T/B%282%29.md#Head%20One) [q](/T/B%282%29.md)\r\n"}),
    ({"S/A.md": "[x](B.md) [[B]]\n", "S/B.md": ""}, "S/A.md", "Top",   # the source itself moves
     {"Top.md": "[x](S/B.md) [[B]]\n"}),
    ({"S/A.md": "[p](img.png) [n](Missing.md)\n", "S/img.png": "p"}, "S/A.md", "D/A",
     {"D/A.md": "[p](../S/img.png) [n](Missing.md)\n"}),
    ({"A.md": "[s](#Top) [s2](A.md#Top)\n"}, "A.md", "Z",
     {"Z.md": "[s](#Top) [s2](Z.md#Top)\n"}),
    ({"A.md": "[c](B.md) `[k](B.md)`\n", "B.md": "", "C.md": "unrelated [o](Other.md)\n"}, "B.md", "B 50%",
     {"A.md": "[c](B%2050%25.md) `[k](B.md)`\n", "C.md": "unrelated [o](Other.md)\n"}),
]


@pytest.mark.parametrize("files,old,new,want", RENAMES)
def test_rename_rewrites_markdown_links(tmp_path, files, old, new, want):
    v = make(tmp_path / "v", files)
    untouched = {p: (v / p).stat().st_mtime_ns for p in files if p not in want and p != old}
    result = cli_json("rename", v, old, new)
    assert result["to"] == new + ".md"
    for path, data in want.items():
        assert (v / path).read_bytes() == data.encode(), path
    for path, mtime in untouched.items():
        assert (v / path).stat().st_mtime_ns == mtime, f"{path} must not be written"


def _snapshot(v):
    out = {}
    for name in cli_json("notes", v):
        md = cli_json("mdlinks", v, name)
        out[name] = ((v / name).read_bytes(), [(d["raw"], d["resolved"]) for d in md],
                     [(d["raw"], d["resolved"]) for d in cli_json("links", v, name)])
    return out


def _rename_case(seed):
    rng = random.Random(30_000 + seed)
    names = ["Alpha", "Beta", "Two Words", "Caf\u00e9"]
    dirs = ["", "A/", "B/", "A/B/"]
    paths = sorted({rng.choice(dirs) + rng.choice(names) + ".md" for _ in range(rng.randint(3, 7))})
    files = {}
    for p in paths:
        parts = []
        for _ in range(rng.randint(1, 5)):
            q = rng.choice(paths + ["Missing.md"])
            rel = rng.choice(["rel", "root", "slash", "nomd", "angle"])
            src_dir = p.rsplit("/", 1)[0] if "/" in p else ""
            if rel == "rel":
                import posixpath
                dest = posixpath.relpath(q, src_dir or ".").replace(" ", "%20")
            elif rel == "slash":
                dest = "/" + q.replace(" ", "%20")
            elif rel == "angle":
                dest = "<" + q + ">"
            else:
                dest = q.replace(" ", "%20")
            if rel == "nomd":
                dest = dest[:-3]
            parts.append(f"[t{len(parts)}]({dest}{rng.choice(['', '#H', '#^b'])})")
            if rng.random() < 0.3:
                parts.append("[[" + q[:-3].rsplit("/", 1)[-1] + "]]")
        files[p] = " ".join(parts) + "\n"
    old = rng.choice(paths)
    new = rng.choice(dirs) + rng.choice(names + ["Fresh Name", "Z"])
    return files, old, new


@pytest.mark.parametrize("seed", range(30))
def test_rename_invariant_with_markdown_links(tmp_path, seed):
    files, old, new = _rename_case(seed)
    v = make(tmp_path / "v", files)
    before = _snapshot(v)
    digest = tree_digest(v)
    proc = cli("rename", v, old, new, check=False)
    if proc.returncode == 2:
        assert proc.stderr.decode().startswith("refused: ")
        assert tree_digest(v) == digest
        return
    dest = new + ".md"
    moved = {p: (dest if p == old else p) for p in before}
    after = _snapshot(v)
    updated = []
    for p, (data, md, wiki) in before.items():
        q = moved[p]
        a_data, a_md, a_wiki = after[q]
        assert len(a_md) == len(md) and len(a_wiki) == len(wiki), q
        for (raw, res), (a_raw, a_res) in zip(md + wiki, a_md + a_wiki):
            if res is None:
                assert a_raw == raw, (q, raw, a_raw)
            else:
                assert a_res == (dest if res == old else res), (q, raw, a_raw, a_res)
        if a_data != data:
            updated.append(q)
        if all(r == ar for (r, _), (ar, _) in zip(md + wiki, a_md + a_wiki)):
            assert a_data == data, q
    assert json.loads(proc.stdout)["updated"] == sorted(updated, key=lambda s: s.encode())


# A model of the contract's refusals (folded path collisions) accepts 25 of these 30
# renames, all needing Markdown rewrites; wikilink ambiguity may refuse a few more.
MIN_SUCCEEDED, MIN_REWROTE = 18, 12


def test_rename_random_cases_mostly_succeed(tmp_path):
    # Refusing broadly is not conformant: the contract refuses only collisions and
    # unpreservable links, and a relative rewrite always preserves its destination.
    succeeded = rewrote = 0
    for seed in range(30):
        files, old, new = _rename_case(seed)
        v = make(tmp_path / f"r{seed}", files)
        before = {p: (v / p).read_bytes() for p in files}
        proc = cli("rename", v, old, new, check=False)
        if proc.returncode == 0:
            succeeded += 1
            dest = new + ".md"
            md = re.compile(r"\[t\d+\]\([^)]*\)")
            rewrote += any(md.findall((v / (dest if p == old else p)).read_text()) != md.findall(data.decode())
                           for p, data in before.items())
    assert succeeded >= MIN_SUCCEEDED and rewrote >= MIN_REWROTE, (succeeded, rewrote)


def test_nfc_names_resolve_rank_and_collide(tmp_path):
    nfd = unicodedata.normalize("NFD", "Caf\u00e9")
    v = make(tmp_path / "v", {nfd + ".md": "", "S.md": "[[Caf\u00e9]] [m](Caf%C3%A9.md)\n", "\u00c9t\u00e9.md": ""})
    assert [d["resolved"] for d in cli_json("links", v, "S.md")] == [nfd + ".md"]
    assert [d["resolved"] for d in cli_json("mdlinks", v, "S.md")] == [nfd + ".md"]
    assert cli_json("switch", v, "caf\u00e9")[0] == nfd + ".md"
    got = cli_json("create", v, "CAF\u00c9")
    assert got == {"path": nfd + ".md", "created": False}
    proc = cli("rename", v, "S.md", nfd.upper(), check=False)
    assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: ")
    assert cli_json("resolve", v, "S.md", unicodedata.normalize("NFD", "\u00e9t\u00e9"))["resolved"] == "\u00c9t\u00e9.md"


def test_render_markdown_note_links(tmp_path):
    v = make(tmp_path / "v", {"A.md": "", "R.md": "x [shown](A.md) [](A.md) [gone](Nope.md) ![i](A.md) [u](https://e)\n"})
    r = cli_json("render", v, "R.md")
    assert r["text"] == "x shown A gone i u"
    assert r["links"] == [{"start": 2, "end": 7, "raw": "[shown](A.md)", "resolved": "A.md"},
                          {"start": 8, "end": 9, "raw": "[](A.md)", "resolved": "A.md"},
                          {"start": 10, "end": 14, "raw": "[gone](Nope.md)", "resolved": None}]
    styles = {(s["start"], s["end"], s["style"]) for s in r["spans"]}
    assert {(2, 7, "link"), (8, 9, "link"), (10, 14, "unresolved"), (15, 16, "url"), (17, 18, "url")} <= styles


@pytest.mark.parametrize("seed", range(30))
def test_render_and_blocks_with_markdown_links_match_reference(tmp_path, seed):
    rng = random.Random(40_000 + seed)
    docs = {}
    for i in range(6):
        text = _doc(rng)
        nl = "\r\n" if "\r\n" in text else "\n"
        docs[rng.choice(["", "B/"]) + f"D{i}.md"] = text + nl + nl + _md_line(rng) + nl
    v = make(tmp_path / "v", {**MD_VAULT, **docs, "Sub/C.md": "", "B.md": ""})
    for name, text in docs.items():
        links, md = cli_json("links", v, name), _ref(v, name, text)
        assert cli_json("render", v, name) == ref_render(text, links, name, md, LOAD(v)), (name, text)
        assert cli_json("blocks", v, name) == ref_blocks(text, links, name, md, LOAD(v)), (name, text)
