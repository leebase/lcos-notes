"""Core rules through lcos-notes-cli (CONTRACT.md: vault, wikilinks, resolution, create, switcher)."""
import json
import os
from pathlib import Path

import pytest

from harness import FIXTURE_VAULT, cli, cli_json, copy_vault, shared_vault, tree_digest

V = shared_vault()

NOTES = [
    "Archive/2025/Deep.md",
    "Café.md",
    "Home.md",
    "Ideas.md",
    "Nav.md",
    "Notes CRLF.md",
    "Projects/Alpha.md",
    "Projects/Ideas.md",
    "Projects/Sub/Deep.md",
]


def test_notes_lists_only_visible_md_files_sorted():
    # .obsidian/.trash skipped, symlink Link.md skipped, Shout.MD and README.txt are not notes
    assert cli_json("notes", V) == NOTES


HOME_LINKS = [
    # line, col, embed, raw, target, heading, alias, resolved
    (3, 8, False, "[[Ideas]]", "Ideas", None, None, "Ideas.md"),
    (3, 22, False, "[[Projects/Alpha|the alpha]]", "Projects/Alpha", None, "the alpha", "Projects/Alpha.md"),
    (3, 55, False, "[[Deep]]", "Deep", None, None, "Archive/2025/Deep.md"),
    (4, 10, False, "[[Projects/Alpha#Plan]]", "Projects/Alpha", "Plan", None, "Projects/Alpha.md"),
    (4, 43, False, "[[#Home]]", "", "Home", None, "Home.md"),
    (5, 8, True, "![[images/diagram.png]]", "images/diagram.png", None, None, "images/diagram.png"),
    (5, 36, True, "![[diagram.png]]", "diagram.png", None, None, "images/diagram.png"),
    (6, 7, False, "[[café]]", "café", None, None, "Café.md"),
    (6, 16, False, "[[IDEAS.md]]", "IDEAS.md", None, None, "Ideas.md"),
    (6, 29, False, "[[Sub/Deep]]", "Sub/Deep", None, None, "Projects/Sub/Deep.md"),
    (6, 42, False, "[[2025/Deep]]", "2025/Deep", None, None, "Archive/2025/Deep.md"),
    (6, 56, False, "[[rojects/Alpha]]", "rojects/Alpha", None, None, None),
    (7, 10, False, "[[Not Yet]]", "Not Yet", None, None, None),
    (7, 26, False, "[[Shout]]", "Shout", None, None, None),
    (7, 40, False, "[[.trash/Old]]", ".trash/Old", None, None, None),
    (8, 60, False, "[[Real]]", "Real", None, None, None),
    (19, 7, False, "[[Ideas#  Spaced Heading  | Alias ]]", "Ideas", "Spaced Heading", "Alias", "Ideas.md"),
    (20, 14, False, "[[Ideas]]", "Ideas", None, None, "Ideas.md"),
    (21, 16, False, "[[ ]]", "", None, None, "Home.md"),
    (22, 7, False, "[[Ideas#^abc123]]", "Ideas", "^abc123", None, "Ideas.md"),
    (22, 29, False, "[[README.txt]]", "README.txt", None, None, "README.txt"),
]


def test_links_in_home_exact():
    got = cli_json("links", V, "Home.md")
    want = [dict(raw=r, target=t, heading=h, alias=a, embed=e, line=ln, col=c, resolved=res)
            for ln, c, e, r, t, h, a, res in HOME_LINKS]
    assert got == want


def test_links_skip_code_and_fences():
    raws = {d["raw"] for d in cli_json("links", V, "Home.md")}
    for absent in ("[[NotALink]]", "[[Nope]]", "[[InFence]]", "[[InTilde]]", "[[StillFenced]]"):
        assert absent not in raws


@pytest.mark.parametrize("source,inner,resolved", [
    ("Projects/Ideas.md", "Ideas", "Projects/Ideas.md"),        # same directory wins
    ("Projects/Ideas.md", "Alpha", "Projects/Alpha.md"),
    ("Projects/Sub/Deep.md", "Deep", "Projects/Sub/Deep.md"),   # self, same directory
    ("Projects/Sub/Deep.md", "Ideas", "Ideas.md"),              # fewest segments
    ("Archive/2025/Deep.md", "Deep", "Archive/2025/Deep.md"),
    ("Home.md", "Deep", "Archive/2025/Deep.md"),                # equal segments: byte order
    ("Home.md", "projects/sub/deep", "Projects/Sub/Deep.md"),
    ("Home.md", "Projects/Alpha.MD", "Projects/Alpha.md"),
    ("Home.md", "CAFÉ", "Café.md"),
    ("Home.md", "Notes CRLF", "Notes CRLF.md"),
    ("Home.md", "Sub", None),                                    # folders are not notes
    ("Home.md", "Link", None),                                   # symlink skipped
    ("Home.md", "Shout.MD", None),                               # .MD stripped -> no note "Shout"
    ("Home.md", "workspace.json", None),                         # hidden files never resolve
    ("Home.md", "Alpha", "Projects/Alpha.md"),
])
def test_resolve_rules(source, inner, resolved):
    assert cli_json("resolve", V, source, inner)["resolved"] == resolved


def test_resolve_parts():
    assert cli_json("resolve", V, "Home.md", " Projects/Alpha # Plan | shown ") == {
        "target": "Projects/Alpha", "heading": "Plan", "alias": "shown", "resolved": "Projects/Alpha.md"}


def test_note_beats_attachment_and_dotted_names(tmp_path):
    v = tmp_path / "v"
    v.mkdir()
    (v / "Report.2025.md").write_text("x")
    (v / "v1.2 plan.md").write_text("x")
    (v / "pic.png").write_bytes(b"x")
    (v / "Home.md").write_text("[[Report.2025]] [[v1.2 plan]] [[pic.png]] [[pic]]")
    got = [d["resolved"] for d in cli_json("links", v, "Home.md")]
    assert got == ["Report.2025.md", "v1.2 plan.md", "pic.png", None]


def test_crlf_and_unicode_columns(tmp_path):
    v = tmp_path / "v"
    v.mkdir()
    (v / "A.md").write_bytes("x\r\nüü [[A]]\r\n[[B]]".encode())
    got = [(d["line"], d["col"], d["resolved"]) for d in cli_json("links", v, "A.md")]
    assert got == [(2, 4, "A.md"), (3, 1, None)]


def test_create_new_note_and_folders(tmp_path):
    v = copy_vault(tmp_path / "v")
    before = tree_digest(v)
    assert cli_json("create", v, "Inbox/Today") == {"path": "Inbox/Today.md", "created": True}
    assert (v / "Inbox" / "Today.md").read_bytes() == b""
    assert cli_json("create", v, " Loose.MD ") == {"path": "Loose.md", "created": True}
    after = tree_digest(v)
    assert set(after) - set(before) == {"Inbox", "Inbox/Today.md", "Loose.md"}
    assert {k: after[k] for k in before} == before


@pytest.mark.parametrize("target,path", [
    ("Ideas", "Ideas.md"), ("ideas", "Ideas.md"), ("projects/ideas", "Projects/Ideas.md"),
    ("Deep", "Archive/2025/Deep.md"),
])
def test_create_existing_never_touches(tmp_path, target, path):
    v = copy_vault(tmp_path / "v")
    before = tree_digest(v)
    os.utime(v / path, (1_000_000_000, 1_000_000_000))
    assert cli_json("create", v, target) == {"path": path, "created": False}
    assert tree_digest(v) == before
    assert (v / path).stat().st_mtime == 1_000_000_000


@pytest.mark.parametrize("target", [
    "", "   ", "/abs", "../out", "a/../b", "./x", ".hidden", "Inbox/.x", ".obsidian/new",
    "bad:name", "why?", "a*b", 'q"q', "a\\b", "a<b", "a>b", "a|b", "x#y", "x^y", "tab\tx",
])
def test_create_refusals_change_nothing(tmp_path, target):
    v = copy_vault(tmp_path / "v")
    before = tree_digest(v)
    proc = cli("create", v, target, check=False)
    assert proc.returncode == 2
    assert proc.stdout == b""
    assert proc.stderr.decode().startswith("refused: ")
    assert tree_digest(v) == before
    assert not (tmp_path / "out.md").exists()


def test_cli_refuses_bad_vault_and_note(tmp_path):
    for args in (("notes", tmp_path / "missing"), ("links", V, "Nope.md"),
                 ("links", V, ".trash/Old.md"), ("resolve", V, "Link.md", "Ideas")):
        proc = cli(*args, check=False)
        assert proc.returncode == 2, args
        assert proc.stderr.decode().startswith("refused: "), args


@pytest.mark.parametrize("query,want", [
    ("ideas", ["Ideas.md", "Projects/Ideas.md"]),
    ("IDEAS", ["Ideas.md", "Projects/Ideas.md"]),
    ("de", ["Archive/2025/Deep.md", "Projects/Sub/Deep.md", "Ideas.md", "Projects/Ideas.md"]),
    ("pa", ["Projects/Alpha.md", "Projects/Ideas.md"]),
    ("café", ["Café.md"]),
    ("zzq", []),
    ("", ["Café.md", "Home.md", "Ideas.md", "Nav.md", "Notes CRLF.md", "Projects/Alpha.md",
          "Projects/Ideas.md", "Archive/2025/Deep.md", "Projects/Sub/Deep.md"]),
])
def test_switcher_ranking(query, want):
    assert cli_json("switch", V, query) == want


def test_switcher_caps_at_50(tmp_path):
    v = tmp_path / "v"
    v.mkdir()
    for i in range(60):
        (v / f"n{i:02d}.md").write_text("")
    got = cli_json("switch", v, "n")
    assert got == [f"n{i:02d}.md" for i in range(50)]


def test_shared_vault_untouched_by_core_suite():
    # Read-only commands above never modify the vault they read.
    assert (V / ".obsidian" / "app.json").read_text() == '{\n  "alwaysUpdateLinks": true\n}\n'
    assert json.loads((V / ".obsidian" / "workspace.json").read_text())["lastOpenFiles"] == ["Home.md"]
    assert os.readlink(V / "Link.md") == "Home.md"
    assert tree_digest(V) == {k: v for k, v in tree_digest(FIXTURE_VAULT).items()} | {"Link.md": "link:Home.md"}
