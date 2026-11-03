"""U6 core rules through lcos-notes-cli: tags, search options, folder and attachment rename,
unlinked mentions (CONTRACT.md: U6)."""
import json
import posixpath
import random

import pytest

from harness import cli, cli_json, copy_vault, tree_digest
from reference_links import markdown_links, mentions as ref_mentions
from test_u2_core import make


def _tags(v):
    return [(d["tag"], d["count"]) for d in cli_json("tags", v)]


def test_parent_tags_and_tag_key(tmp_path):
    v = make(tmp_path / "v", {
        "A.md": "#Area/Sub/Leaf and #area/other\n",
        "B.md": "---\ntag: [area, Solo]\n---\n#Proj/x\n",
        "C.md": "---\ntag:\n  - '#proj/Y/z'\n---\n",
        "D.md": "---\ntags: one\ntag: two\n---\n",
    })
    assert _tags(v) == [("area", 2), ("area/other", 1), ("Area/Sub", 1), ("Area/Sub/Leaf", 1), ("one", 1),
                        ("Proj", 2), ("Proj/x", 1), ("proj/Y", 1), ("proj/Y/z", 1), ("Solo", 1), ("two", 1)]
    assert cli_json("tagged", v, "proj") == ["B.md", "C.md"]


def _retag(v, old, new, check=True):
    return cli("retag", v, old, new, check=check)


RETAGS = [
    ({"A.md": "#Old and #old/Kid and #older and `#old` x#old\n",
      "B.md": "---\ntags: [\"#Old\", keep, 'old/a']\n---\n#OLD\r\n",
      "C.md": "---\ntag:\n  - old\n  - Other\n---\nno tags\n", "D.md": "#other only\n"},
     "#old", "New/Name",
     {"A.md": "#New/Name and #New/Name/Kid and #older and `#old` x#old\n",
      "B.md": "---\ntags: [\"#New/Name\", keep, 'New/Name/a']\n---\n#New/Name\r\n",
      "C.md": "---\ntag:\n  - New/Name\n  - Other\n---\nno tags\n"},
     ["A.md", "B.md", "C.md"]),
    ({"A.md": "#a/b/c #a/bx #A/B\n", "B.md": "#z\n"}, "a/b", "zz",
     {"A.md": "#zz/c #a/bx #zz\n"}, ["A.md"]),
    ({"A.md": "#p/q #p\n"}, "p/q", "p",                       # OLD nested under NEW: allowed (merge up)
     {"A.md": "#p #p\n"}, ["A.md"]),
]


@pytest.mark.parametrize("files,old,new,want,updated", RETAGS)
def test_retag(tmp_path, files, old, new, want, updated):
    v = make(tmp_path / "v", files)
    untouched = {p: (v / p).stat().st_mtime_ns for p in files if p not in want}
    got = json.loads(_retag(v, old, new).stdout)
    assert got == {"from": old.lstrip("#"), "to": new.lstrip("#"), "updated": updated}
    for p, data in want.items():
        assert (v / p).read_bytes() == data.encode(), p
    for p, m in untouched.items():
        assert (v / p).stat().st_mtime_ns == m, p


@pytest.mark.parametrize("old,new", [("123", "x"), ("x", "a b"), ("missing", "x"), ("a", "a/b"), ("A", "a/b/c"),
                                     ("", "x"), ("a", "")])
def test_retag_refusals_change_nothing(tmp_path, old, new):
    v = make(tmp_path / "v", {"A.md": "#a #x\n", "Bad.md": b"#a \xff\n"})
    before = tree_digest(v)
    proc = _retag(v, old, new, check=False)
    assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: "), (old, new)
    assert tree_digest(v) == before


def test_retag_skips_non_utf8_and_code(tmp_path):
    v = make(tmp_path / "v", {"A.md": "```\n#a\n```\n#a\n", "Bad.md": b"#a \xff\n"})
    _retag(v, "a", "b")
    assert (v / "A.md").read_text() == "```\n#a\n```\n#b\n"
    assert (v / "Bad.md").read_bytes() == b"#a \xff\n"


@pytest.mark.parametrize("seed", range(20))
def test_retag_random_property(tmp_path, seed):
    rng = random.Random(70_000 + seed)
    tags = ["alpha", "Alpha/one", "alpha/two/x", "beta", "beta/alpha", "gamma", "ALPHAish"]
    files = {}
    for i in range(rng.randint(3, 8)):
        body = " ".join(rng.choice(["#" + rng.choice(tags), "word", "`#alpha`", "x#alpha"]) for _ in range(6))
        fm = ""
        if rng.random() < 0.4:
            fm = "---\n" + rng.choice(["tags", "tag"]) + ": [" + ", ".join(rng.sample(tags, 2)) + "]\n---\n"
        files[f"N{i}.md"] = fm + body + "\n"
    v = make(tmp_path / "v", files)
    before_alpha = set(cli_json("tagged", v, "alpha"))
    before_delta = set(cli_json("tagged", v, "delta"))
    before_counts = dict(_tags(v))
    proc = _retag(v, "alpha", "delta", check=False)
    if not before_alpha:
        assert proc.returncode == 2
        return
    assert proc.returncode == 0, proc.stderr
    assert set(cli_json("tagged", v, "delta")) == before_alpha | before_delta
    assert cli_json("tagged", v, "alpha") == []
    after = dict(_tags(v))
    for t, c in before_counts.items():                       # tags outside the renamed subtree keep counts
        if not t.lower().startswith("alpha") or t.lower() == "alphaish":
            assert after.get(t) == c, t
    for p, data in files.items():                            # only tag text changed
        new = (v / p).read_text()
        assert new.replace("delta", "alpha").lower() == data.lower() or new == data, p


FIND_VAULT = {"A.md": "plan planning Plan_x plan-b xplan\nplán plan\n", "B.md": "a1 a22 a333\n\n", "C.md": "über Über\n"}


@pytest.mark.parametrize("args,want", [
    (["plan", "--word"], [("A.md", 1, 1), ("A.md", 1, 22), ("A.md", 2, 6)]),
    (["--word", "plan"], None),                              # QUERY comes first: options after it
    (["plan", "--regex"], [("A.md", 1, 1), ("A.md", 1, 6), ("A.md", 1, 15), ("A.md", 1, 22), ("A.md", 1, 30),
                            ("A.md", 2, 6)]),
    (["pla[nñ]", "--regex", "--word"], [("A.md", 1, 1), ("A.md", 1, 22), ("A.md", 2, 6)]),
    (["a\\d+", "--regex"], [("B.md", 1, 1), ("B.md", 1, 4), ("B.md", 1, 8)]),
    (["a\\d", "--word", "--regex"], [("B.md", 1, 1)]),
    (["x*", "--regex"], [("A.md", 1, 20), ("A.md", 1, 29)]),                  # empty matches are skipped
    (["ÜBER", "--word"], [("C.md", 1, 1), ("C.md", 1, 6)]),
    (["^plán", "--regex"], [("A.md", 2, 1)]),
    (["n$", "--regex"], [("A.md", 1, 33), ("A.md", 2, 9)]),
])
def test_find_options(tmp_path, args, want):
    v = make(tmp_path / "v", FIND_VAULT)
    if want is None:
        proc = cli("find", v, *args, check=False)
        assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: ")
        return
    got = [(m["path"], m["line"], m["col"]) for m in cli_json("find", v, *args)]
    assert got == want, args


def test_find_regex_refusals(tmp_path):
    v = make(tmp_path / "v", FIND_VAULT)
    for args in [("(", "--regex"), ("plan", "--bogus"), ("plan", "--regex", "--regex", "x")]:
        proc = cli("find", v, *args, check=False)
        assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: "), args


DIR_RENAMES = [
    ({"P/A.md": "[[B]] [m](B.md) [r](../Top.md)\n", "P/B.md": "", "Top.md": "[[P/A]] [x](P/A.md) [[A]]\n",
      "P/img.png": "i", "Q.md": "![[P/img.png]] [i](P/img.png)\n"}, "P", "R/S",
     {"R/S/A.md": "[[B]] [m](B.md) [r](../../Top.md)\n", "Top.md": "[[A]] [x](R/S/A.md) [[A]]\n",
      "Q.md": "![[img.png]] [i](R/S/img.png)\n"},
     ["Q.md", "R/S/A.md", "Top.md"]),
    ({"F/img.png": "i", "N.md": "![[img.png]] ![[F/img.png]] [i](F/img.png)\n"}, "F/img.png", "G/pic.png",
     {"N.md": "![[pic.png]] ![[pic.png]] [i](G/pic.png)\n"}, ["N.md"]),
]


@pytest.mark.parametrize("files,old,new,want,updated", DIR_RENAMES)
def test_rename_folder_and_attachment(tmp_path, files, old, new, want, updated):
    v = make(tmp_path / "v", files)
    result = cli_json("rename", v, old, new)
    assert result == {"from": old, "to": new, "updated": updated}
    for p, data in want.items():
        assert (v / p).read_bytes() == data.encode(), p
    assert not (v / old).exists()
    for p in files:
        if p.startswith(old + "/") or p == old:
            moved = new + p[len(old):]
            assert (v / moved).exists(), moved


@pytest.mark.parametrize("old,new", [("P", "P/Inner"), ("P", "top.MD"), ("P", "q"), ("", "X"),
                                     (".hidden", "X"), ("Nope", "X"), ("P", "../X"), ("P/img.png", "Top.md")])
def test_rename_folder_refusals(tmp_path, old, new):
    v = make(tmp_path / "v", {"P/A.md": "", "P/img.png": "i", "Top.md": "", "Q/x.md": "", ".hidden/h.md": ""})
    before = tree_digest(v)
    proc = cli("rename", v, old, new, check=False)
    assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: "), (old, new)
    assert tree_digest(v) == before


def _snapshot(v):
    out = {}
    for name in cli_json("notes", v):
        out[name] = ((v / name).read_bytes(), [(d["raw"], d["resolved"]) for d in cli_json("mdlinks", v, name)],
                     [(d["raw"], d["resolved"]) for d in cli_json("links", v, name)])
    return out


def _folder_case(seed):
    rng = random.Random(80_000 + seed)
    dirs = ["", "A/", "A/B/", "C/"]
    names = ["One", "Two", "Three"]
    paths = sorted({rng.choice(dirs) + rng.choice(names) + ".md" for _ in range(rng.randint(4, 8))}
                   | {"A/pic.png", "C/doc.pdf"})
    files = {}
    for p in paths:
        if not p.endswith(".md"):
            files[p] = "bin"
            continue
        parts = []
        for _ in range(rng.randint(1, 5)):
            q = rng.choice(paths)
            src = posixpath.dirname(p) or "."
            k = rng.choice(["wname", "wpath", "rel", "root"])
            if k == "wname":
                parts.append("[[" + posixpath.basename(q)[:-3 if q.endswith(".md") else None] + "]]")
            elif k == "wpath":
                parts.append("[[" + (q[:-3] if q.endswith(".md") else q) + "]]")
            elif k == "rel":
                parts.append(f"[r]({posixpath.relpath(q, src)})")
            else:
                parts.append(f"[o](/{q})")
        files[p] = " ".join(parts) + "\n"
    old = rng.choice(["A", "A/B", "C"])
    new = rng.choice(["D", "E/F", "A/G", "C/H"])
    return files, old, new


@pytest.mark.parametrize("seed", range(25))
def test_folder_rename_invariant(tmp_path, seed):
    files, old, new = _folder_case(seed)
    v = make(tmp_path / "v", files)
    before = _snapshot(v)
    digest = tree_digest(v)
    proc = cli("rename", v, old, new, check=False)
    if proc.returncode == 2:
        assert proc.stderr.decode().startswith("refused: ")
        assert tree_digest(v) == digest
        return
    assert proc.returncode == 0, proc.stderr

    def moved(p):
        return new + p[len(old):] if p.startswith(old + "/") else p

    after = _snapshot(v)
    updated = []
    for p, (data, md, wiki) in before.items():
        a_data, a_md, a_wiki = after[moved(p)]
        for (raw, res), (a_raw, a_res) in zip(md + wiki, a_md + a_wiki):
            if res is None:
                assert a_raw == raw, (p, raw, a_raw)
            else:
                assert a_res == moved(res), (p, raw, a_raw, a_res)
        if a_data != data:
            updated.append(moved(p))
    assert json.loads(proc.stdout)["updated"] == sorted(updated, key=str.encode)


# The collision model accepts 21 of 25; ambiguous wikilinks may refuse a few more.
MIN_FOLDER_OK, MIN_FOLDER_REWROTE = 15, 10


def test_folder_renames_mostly_succeed(tmp_path):
    # Folders A, A/B and C always exist (A/pic.png, C/doc.pdf); NEW never collides except
    # A/G or C/H inside OLD. A model of the contract's refusals accepts the count below.
    succeeded = rewrote = 0
    for seed in range(25):
        files, old, new = _folder_case(seed)
        v = make(tmp_path / f"f{seed}", files)
        proc = cli("rename", v, old, new, check=False)
        if proc.returncode == 0:
            succeeded += 1
            rewrote += bool(json.loads(proc.stdout)["updated"])
    assert succeeded >= MIN_FOLDER_OK and rewrote >= MIN_FOLDER_REWROTE, (succeeded, rewrote)


def test_mentions_exact(tmp_path):
    v = make(tmp_path / "v", {
        "Big Idea.md": "Big Idea mentions itself\n",
        "A.md": "---\ntitle: big idea\n---\nThe big idea, [[Big Idea]] and BIG IDEA! `big idea` bigidea big ideas\n"
                "[x](Big%20Idea.md) _big idea_ (big idea)\r\n```\nbig idea\n```\n",
        "B.md": "nothing here\n", "Bad.md": b"big idea \xff\n",
    })
    got = [(m["source"], m["line"], m["col"], m["text"]) for m in cli_json("mentions", v, "Big Idea.md")]
    line4 = "The big idea, [[Big Idea]] and BIG IDEA! `big idea` bigidea big ideas"
    line5 = "[x](Big%20Idea.md) _big idea_ (big idea)"
    assert got == [("A.md", 4, 5, line4), ("A.md", 4, 32, line4), ("A.md", 5, 32, line5)]
    for args in [("mentions", v, "Missing.md"), ("mentions", v, "B")]:
        proc = cli(*args, check=False)
        assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: ")


@pytest.mark.parametrize("seed", range(25))
def test_mentions_match_reference(tmp_path, seed):
    rng = random.Random(90_000 + seed)
    words = ["Alpha", "alpha", "ALPHA", "alphas", "xalpha", "[[Alpha]]", "[a](Alpha.md)", "`alpha`", "alpha_1",
             "(alpha)", "Two Words", "two  words", "two words.", "#alpha", "Beta", "-alpha-", "älpha"]
    docs = {}
    for i in range(6):
        lines = [" ".join(rng.choice(words) for _ in range(rng.randint(1, 6))) for _ in range(rng.randint(1, 5))]
        if rng.random() < 0.3:
            lines = ["---", "x: alpha", "---"] + lines
        if rng.random() < 0.2:
            lines += ["```", "alpha", "```"]
        docs[f"D{i}.md"] = "\n".join(lines) + "\n"
    v = make(tmp_path / "v", {"Alpha.md": "alpha\n", "Two Words.md": "", **docs})
    for target in ["Alpha.md", "Two Words.md"]:
        name = target[:-3]
        want = []
        for p in sorted(docs, key=str.encode):
            text = docs[p]
            links = cli_json("links", v, p)
            md = markdown_links(v, p, text, links)
            want += [(p, ln, col, t) for ln, col, t in ref_mentions(text, name, links, md)]
        got = [(m["source"], m["line"], m["col"], m["text"]) for m in cli_json("mentions", v, target)]
        assert got == want, target


def test_user_docs_cover_u6():
    """README and DOCUMENTATION.md cover U6; a fresh LCOS install needs apt update first.
    (The version strings are the current unit's: test_u7_core.)"""
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text()
    update, install = readme.find("sudo apt update\n"), readme.find("sudo apt install ./lcos-notes_")
    assert 0 <= update < install
    guide = (root / "DOCUMENTATION.md").read_text()
    for term in ("retag", "--regex", "--word", "mentions", "Ctrl+Shift+E", "Ctrl+Shift+T", "Ctrl+Shift+M",
                 "Unlinked mentions", "Whole word", "Regular expression", "Ctrl+N", "Create"):
        assert term in guide, term


LISTY = "# H\n\n- a\n- b\n  - c\n\n  d\n> q1\n>\n> - x\n\n1. one\n2. two ^k-1\n\npara ^id\n`^x` ^y\n"


def test_blocks_reach_list_items_and_quotes(tmp_path):
    v = make(tmp_path / "v", {"N.md": LISTY})
    assert cli_json("blocks", v, "N.md") == [
        {"line": 1, "offset": 0}, {"line": 3, "offset": 3}, {"line": 4, "offset": 7}, {"line": 5, "offset": 14},
        {"line": 7, "offset": 21}, {"line": 8, "offset": 24}, {"line": 10, "offset": 28},
        {"line": 12, "offset": 33}, {"line": 13, "offset": 40}, {"line": 15, "offset": 48}]


def test_reading_view_hides_trailing_block_ids(tmp_path):
    v = make(tmp_path / "v", {"N.md": LISTY, "K.md": "keep **^bold**\n\nkeep [[N]] ^z9\n\nnot^id\n\n^alone\n"})
    assert cli_json("render", v, "N.md")["text"] == (
        "H\n\n• a\n• b\n\n  • c\n\n  d\n\nq1\n\n• x\n\n1. one\n2. two\n\npara ^id ^x")
    r = cli_json("render", v, "K.md")
    assert r["text"] == "keep ^bold\n\nkeep N\n\nnot^id\n\n^alone"
    assert r["links"] == [{"start": 17, "end": 18, "raw": "[[N]]", "resolved": "N.md"}]


def test_attachment_renames_to_extensionless_name(tmp_path):
    """Q291 (Lee, 2026-11-02): an attachment may move to a destination without an extension when
    the rename invariant holds. With README.txt.md present, [[README.txt]] resolves to that note
    before and after, so nothing is rewritten."""
    v = copy_vault(tmp_path / "v")
    (v / "README.txt.md").write_text("")
    before = tree_digest(v)
    data = (v / "README.txt").read_bytes()
    got = cli_json("rename", v, "README.txt", "X")
    assert got["updated"] == []
    assert not (v / "README.txt").exists() and (v / "X").read_bytes() == data
    after = tree_digest(v)
    assert {k for k in set(before) | set(after) if before.get(k) != after.get(k)} == {"README.txt", "X"}
