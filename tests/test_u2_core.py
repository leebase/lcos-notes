"""U2 core rules through lcos-notes-cli: tags, search, backlinks, rename (CONTRACT.md: U2)."""
import json
import os
import random
from pathlib import Path

import pytest

from harness import cli, cli_json, copy_vault, shared_vault, tree_digest

V = shared_vault()


def make(root: Path, files: dict) -> Path:
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return root


TAG_VAULT = {
    "T1.md": "---\ntags: [Project, \"#Work\", 123, 'a b']\nother: x\n---\n# Title\n"
             "Body #Inbox and #y2025 and #123 and x#nottag and `#code` #nested/child #Ünï\n"
             "```\n#fenced\n```\n",
    "T2.md": "---\ntags:\n  - inbox\n  - '#Later'\nnot: [x]\n---\n#project at start\nTrailing #work.\n",
    "T3.md": "---\ntags: solo, duo three\n---\n",
    "T4.md": "No frontmatter\n---\ntags: [fake]\n---\n#real\n",
    "T5.md": "---\ntags: [unclosed]\n#body1\n",
    "T6.md": "---\r\ntags: [crlf]\r\n---\r\n#Inbox\r\n",
    "NotUTF8.md": b"#ghost \xff\xfe\n",
}


@pytest.fixture
def tag_vault(tmp_path):
    return make(tmp_path / "t", TAG_VAULT)


def test_tags_inline_frontmatter_display_and_counts(tag_vault):
    assert cli_json("tags", tag_vault) == [
        {"tag": "body1", "count": 1}, {"tag": "crlf", "count": 1}, {"tag": "duo", "count": 1},
        {"tag": "Inbox", "count": 3}, {"tag": "Later", "count": 1},
        {"tag": "nested", "count": 1},                         # U6: implicit parent tag
        {"tag": "nested/child", "count": 1},
        {"tag": "Project", "count": 2}, {"tag": "real", "count": 1}, {"tag": "solo", "count": 1},
        {"tag": "three", "count": 1}, {"tag": "Work", "count": 2}, {"tag": "y2025", "count": 1},
        {"tag": "Ünï", "count": 1},
    ]


@pytest.mark.parametrize("tag,notes", [
    ("nested", ["T1.md"]), ("nested/child", ["T1.md"]), ("#INBOX", ["T1.md", "T2.md", "T6.md"]),
    ("nest", []), ("project", ["T1.md", "T2.md"]), ("ghost", []), ("fenced", []), ("code", []),
    ("üNÏ", ["T1.md"]), ("fake", []),
])
def test_tagged(tag_vault, tag, notes):
    assert cli_json("tagged", tag_vault, tag) == notes


@pytest.mark.parametrize("tag", ["123", "", "#", "a b", "x.y"])
def test_tagged_refuses_invalid(tag_vault, tag):
    proc = cli("tagged", tag_vault, tag, check=False)
    assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: ")


def test_tags_change_with_files(tag_vault):
    (tag_vault / "T7.md").write_text("#Fresh #inbox")
    got = {d["tag"]: d["count"] for d in cli_json("tags", tag_vault)}
    assert got["Fresh"] == 1 and got["Inbox"] == 4


def test_find_fixture():
    assert cli_json("find", V, "plan") == [
        {"path": "Home.md", "line": 4, "col": 27, "text": "Heading: [[Projects/Alpha#Plan]] and self [[#Home]]."},
        {"path": "Nav.md", "line": 1, "col": 18, "text": "[[Projects/Alpha#plan]]"},
        {"path": "Projects/Alpha.md", "line": 5, "col": 4, "text": "## Plan"},
        {"path": "Projects/Alpha.md", "line": 7, "col": 5, "text": "The plan. Back to [[Ideas]]."},
        {"path": "Projects/Alpha.md", "line": 9, "col": 4, "text": "## Plan"},
        {"path": "Projects/Alpha.md", "line": 11, "col": 8, "text": "Second plan heading."},
    ]
    assert cli_json("find", V, "CAFÉ") == [
        {"path": "Café.md", "line": 1, "col": 1, "text": "Café note"},
        {"path": "Home.md", "line": 6, "col": 9,
         "text": "Case: [[café]] [[IDEAS.md]] [[Sub/Deep]] [[2025/Deep]] [[rojects/Alpha]]."},
    ]
    assert cli_json("find", V, "line two") == [{"path": "Notes CRLF.md", "line": 2, "col": 1, "text": "Line two"}]


def test_find_overlap_columns_cap_and_skips(tmp_path):
    v = make(tmp_path / "f", {
        "A.md": "üüaaaa\n",
        "B.md": "x\n" * 600,
        "Bad.md": b"aaaa \xff\n",
        ".hidden/H.md": "aaaa\n",
    })
    got = cli_json("find", v, "aa")
    assert got[:2] == [{"path": "A.md", "line": 1, "col": 3, "text": "üüaaaa"},
                       {"path": "A.md", "line": 1, "col": 5, "text": "üüaaaa"}]
    assert len(got) == 2
    assert len(cli_json("find", v, "X")) == 500
    assert cli_json("find", v, " a") == []
    proc = cli("find", v, "", check=False)
    assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: ")


@pytest.mark.parametrize("note,want", [
    ("Ideas.md", [("Home.md", 3, 8, "[[Ideas]]"), ("Home.md", 6, 16, "[[IDEAS.md]]"),
                  ("Home.md", 19, 7, "[[Ideas#  Spaced Heading  | Alias ]]"), ("Home.md", 20, 14, "[[Ideas]]"),
                  ("Home.md", 22, 7, "[[Ideas#^abc123]]"), ("Notes CRLF.md", 3, 1, "[[Ideas]]"),
                  ("Projects/Sub/Deep.md", 3, 10, "[[Ideas]]")]),
    ("Home.md", []),                                         # only self links
    ("Projects/Alpha.md", [("Home.md", 3, 22, "[[Projects/Alpha|the alpha]]"),
                           ("Home.md", 4, 10, "[[Projects/Alpha#Plan]]"), ("Nav.md", 1, 1, "[[Projects/Alpha#plan]]"),
                           ("Projects/Ideas.md", 3, 19, "[[Alpha]]")]),
    ("Archive/2025/Deep.md", [("Home.md", 3, 55, "[[Deep]]"), ("Home.md", 6, 42, "[[2025/Deep]]"),
                              ("Nav.md", 2, 1, "[[Deep]]")]),
    ("Notes CRLF.md", []),
])
def test_backlinks(note, want):
    assert cli_json("backlinks", V, note) == [dict(source=s, line=ln, col=c, raw=r) for s, ln, c, r in want]


def test_backlinks_refusals():
    for note in ("Nope.md", "Link.md", ".trash/Old.md"):
        proc = cli("backlinks", V, note, check=False)
        assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: ")


# ---------------- rename ----------------

def all_links(v):
    out = {}
    for note in cli_json("notes", v):
        proc = cli("links", v, note, check=False)
        if proc.returncode == 0:
            out[note] = json.loads(proc.stdout)
    return out


def check_invariant(v, old, new, before_links, before_bytes, result):
    new_path = result["to"]
    mp = lambda p: new_path if p == old else p
    after_links = all_links(v)
    assert set(after_links) == {mp(n) for n in before_links}
    for note, links in before_links.items():
        after = after_links[mp(note)]
        assert len(after) == len(links), note
        for b, a in zip(links, after):
            if b["resolved"] is None:
                assert a["raw"] == b["raw"], (note, b)
            else:
                assert a["resolved"] == mp(b["resolved"]), (note, b, a)
                if a["raw"] != b["raw"]:
                    assert a["embed"] == b["embed"] and a["heading"] == b["heading"] and a["alias"] == b["alias"]
    changed = sorted((mp(p) for p, data in before_bytes.items()
                      if (v / mp(p)).read_bytes() != data), key=lambda s: s.encode())
    assert result["updated"] == changed
    assert not (v / old).exists() or old.casefold() == new_path.casefold()


def snapshot(v):
    notes = cli_json("notes", v)
    return all_links(v), {n: (v / n).read_bytes() for n in notes}


@pytest.mark.parametrize("old,new,to,updated,expect", [
    ("Ideas.md", "Thoughts", "Thoughts.md", ["Home.md", "Notes CRLF.md", "Projects/Sub/Deep.md"], {
        "Home.md": {3: "Links: [[Thoughts]] and [[Projects/Alpha|the alpha]] and [[Deep]].",
                    6: "Case: [[café]] [[Thoughts]] [[Sub/Deep]] [[2025/Deep]] [[rojects/Alpha]].",
                    19: "After [[Thoughts#Spaced Heading|Alias]].",
                    22: "Block [[Thoughts#^abc123]] and [[README.txt]]."},
        "Projects/Sub/Deep.md": {3: "[[Deep]] [[Thoughts]]"}}),
    ("Projects/Alpha.md", "Archive/Alpha.md", "Archive/Alpha.md", ["Archive/Alpha.md", "Home.md", "Nav.md"], {
        "Home.md": {3: "Links: [[Ideas]] and [[Alpha|the alpha]] and [[Deep]].",
                    4: "Heading: [[Alpha#Plan]] and self [[#Home]]."},
        "Nav.md": {1: "[[Alpha#plan]]"},
        "Archive/Alpha.md": {7: "The plan. Back to [[Projects/Ideas]]."}}),
    ("Café.md", "Deep", "Deep.md", ["Home.md", "Nav.md"], {
        "Home.md": {3: "Links: [[Ideas]] and [[Projects/Alpha|the alpha]] and [[Archive/2025/Deep]].",
                    6: "Case: [[Deep]] [[IDEAS.md]] [[Sub/Deep]] [[2025/Deep]] [[rojects/Alpha]]."},
        "Nav.md": {2: "[[Archive/2025/Deep]]"}}),
    ("Home.md", " home ", "home.md", [], {}),
])
def test_rename_cases(tmp_path, old, new, to, updated, expect):
    v = copy_vault(tmp_path / "v")
    before_links, before_bytes = snapshot(v)
    crlf_before = (v / "Notes CRLF.md").read_bytes()
    result = cli_json("rename", v, old, new)
    assert result == {"from": old, "to": to, "updated": updated}
    for note, lines in expect.items():
        text = (v / note).read_bytes().decode().split("\n")
        for n, line in lines.items():
            assert text[n - 1] == line, (note, n)
    if "Notes CRLF.md" in updated:
        assert (v / "Notes CRLF.md").read_bytes() == crlf_before.replace(b"[[Ideas]]", b"[[Thoughts]]")
    assert (v / to).exists()
    check_invariant(v, old, new, before_links, before_bytes, result)
    assert tree_digest(v)[".obsidian/app.json"] == tree_digest(copy_vault(tmp_path / "fresh"))[".obsidian/app.json"]


def test_rename_unchanged_notes_not_written(tmp_path):
    v = copy_vault(tmp_path / "v")
    for p in v.rglob("*.md"):
        if not p.is_symlink():
            os.utime(p, (1_000_000_000, 1_000_000_000))
    cli_json("rename", v, "Ideas.md", "Thoughts")
    untouched = ["Archive/2025/Deep.md", "Café.md", "Nav.md", "Projects/Alpha.md", "Projects/Ideas.md"]
    for rel in untouched:
        assert (v / rel).stat().st_mtime == 1_000_000_000, rel
    fresh = {q.relative_to(tmp_path / "f").as_posix() for q in copy_vault(tmp_path / "f").rglob("*")}
    now = {q.relative_to(v).as_posix() for q in v.rglob("*")}
    assert sorted(now - fresh) == ["Thoughts.md"] and sorted(fresh - now) == ["Ideas.md"]


@pytest.mark.parametrize("old,new", [
    ("Café.md", "Projects/Sub/Ideas"),   # [[Ideas]] in Projects/Sub/Deep.md cannot keep its target
    ("Café.md", "Ideas"), ("Café.md", "projects/IDEAS"), ("Café.md", "README.txt"),
    ("Café.md", "../x"), ("Café.md", ".hidden/x"), ("Café.md", "a:b"),
    ("Café.md", ""), ("Nope.md", "X"), ("Link.md", "X"), (".trash/Old.md", "X"),
])                                       # ("README.txt", "X") moved to test_u6_core (Q291: attachments rename in U6)
def test_rename_refusals_change_nothing(tmp_path, old, new):
    v = copy_vault(tmp_path / "v")
    (v / "README.txt.md").write_text("")  # makes "README.txt" an existing note path
    before = tree_digest(v)
    proc = cli("rename", v, old, new, check=False)
    assert proc.returncode == 2, proc.stdout
    assert proc.stdout == b"" and proc.stderr.decode().startswith("refused: ")
    assert tree_digest(v) == before


def test_rename_never_touches_non_utf8_and_moves_into_new_folders(tmp_path):
    v = copy_vault(tmp_path / "v")
    bad = b"[[Ideas]] \xff\n"
    (v / "Bad.md").write_bytes(bad)
    result = cli_json("rename", v, "Ideas.md", "New/Deeper/Ideas2")
    assert result["to"] == "New/Deeper/Ideas2.md"
    assert (v / "Bad.md").read_bytes() == bad
    assert "Bad.md" not in result["updated"]
    assert (v / "New" / "Deeper" / "Ideas2.md").read_bytes().startswith(b"# Ideas")


NAMES = ["Alpha", "Beta", "Gamma", "Delta", "Notes", "alpha", "Report.2025", "Café"]
DIRS = ["", "A/", "B/", "A/B/", "B/A/"]


def random_vault(root: Path, rng: random.Random) -> Path:
    paths = set()
    while len(paths) < rng.randint(4, 9):
        p = rng.choice(DIRS) + rng.choice(NAMES) + ".md"
        if p.casefold() not in {q.casefold() for q in paths}:
            paths.add(p)
    files = {}
    for p in sorted(paths):
        lines = []
        for _ in range(rng.randint(1, 5)):
            parts = []
            for _ in range(rng.randint(1, 3)):
                target = rng.choice([rng.choice(NAMES), rng.choice(DIRS[1:]) + rng.choice(NAMES),
                                     rng.choice(NAMES).upper(), rng.choice(NAMES) + ".md", "Missing", ""])
                extra = rng.choice(["", "#Head", "|alias", "#H|a b"])
                bang = rng.choice(["", "", "!"])
                parts.append(f"{bang}[[{target}{extra}]]")
            lines.append(" text ".join(parts))
        files[p] = ("\r\n" if rng.random() < 0.2 else "\n").join(lines)
    return make(root, files)


@pytest.mark.parametrize("seed", range(40))
def test_rename_invariant_random(tmp_path, seed):
    rng = random.Random(seed)
    v = random_vault(tmp_path / "r", rng)
    notes = cli_json("notes", v)
    old = rng.choice(notes)
    new = rng.choice(DIRS) + rng.choice(NAMES + ["Fresh", "Zeta"])
    before_tree = tree_digest(v)
    before_links, before_bytes = snapshot(v)
    proc = cli("rename", v, old, new, check=False)
    if proc.returncode == 2:
        assert proc.stderr.decode().startswith("refused: ")
        assert tree_digest(v) == before_tree
        return
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["from"] == old and result["to"] == new + ".md"
    check_invariant(v, old, new, before_links, before_bytes, result)


def test_rename_random_cases_mostly_succeed(tmp_path):
    # The contract's refusals are deterministic; a reference model accepts 35 of these 40
    # renames, 22 with rewritten links. Refusing broadly is not conformant.
    succeeded = rewrote = 0
    for seed in range(40):
        rng = random.Random(seed)
        v = random_vault(tmp_path / f"r{seed}", rng)
        old = rng.choice(cli_json("notes", v))
        new = rng.choice(DIRS) + rng.choice(NAMES + ["Fresh", "Zeta"])
        proc = cli("rename", v, old, new, check=False)
        if proc.returncode == 0:
            succeeded += 1
            rewrote += bool(json.loads(proc.stdout)["updated"])
    assert succeeded >= 30 and rewrote >= 15, (succeeded, rewrote)
