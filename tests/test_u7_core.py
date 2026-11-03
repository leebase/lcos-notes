"""U7 core: cmark-gfm tables, task items, strikethrough; `tasks`; the parser switch
(CONTRACT.md: U7)."""
import random
import subprocess
from pathlib import Path

import pytest

from harness import build, cli, cli_json
from reference_links import markdown_links
from reference_render import blocks as ref_blocks
from reference_render import render as ref_render
from reference_render import tasks as ref_tasks
from test_u3_core import INLINE, _block, _vault

ROOT = Path(__file__).resolve().parents[1]
BOXES = {False: "☐", True: "☑"}


def _spans(r):
    return [(s["start"], s["end"], s["style"]) for s in r["spans"]]


# ---------------------------------------------------------------- hand-pinned samples

TASKS = "- [ ] open\n- [x] done ~~gone~~ ~one~\n  - [X] sub\n7) [ ] seven\n\n* plain\n"


def test_tasks_and_strikethrough_exact(tmp_path):
    v = _vault(tmp_path, {"T.md": TASKS})
    r = cli_json("render", v, "T.md")
    assert r["text"] == "☐ open\n☑ done gone ~one~\n  ☑ sub\n\n7) ☐ seven\n\n• plain"
    assert _spans(r) == [(0, 1, "task"), (7, 8, "task"), (9, 24, "done"), (14, 18, "strike"),
                         (27, 28, "task"), (29, 32, "done"), (37, 38, "task")]   # "7)" starts a new list
    assert cli_json("tasks", v, "T.md") == [
        {"line": 1, "col": 3, "checked": False, "offset": 0},
        {"line": 2, "col": 3, "checked": True, "offset": 7},
        {"line": 3, "col": 5, "checked": True, "offset": 27},
        {"line": 4, "col": 4, "checked": False, "offset": 37}]


def test_checked_comes_from_the_marker_not_the_line(tmp_path):
    # cmark-gfm 0.29.0.gfm.13 flags an item checked when "[x]" occurs anywhere on its line.
    v = _vault(tmp_path, {"T.md": "- [ ] see [x] here\n- [ ] and [X]\n"})
    assert cli_json("render", v, "T.md")["text"] == "☐ see [x] here\n☐ and [X]"
    assert [t["checked"] for t in cli_json("tasks", v, "T.md")] == [False, False]


def test_task_lines_and_columns_count_frontmatter_and_code_points(tmp_path):
    text = "---\ntags: [a]\n---\n- é\n  1. [x] ok\n> - [ ] quoted\n"
    v = _vault(tmp_path, {"T.md": text})
    assert cli_json("tasks", v, "T.md") == [{"line": 5, "col": 6, "checked": True, "offset": 9}]
    assert cli_json("render", v, "T.md")["text"] == "• é\n  1. ☑ ok\n\n• [ ] quoted"


TABLE = ("| Name | [[A|al]] | n |\n"
         "|:-----|:--:|--:|\n"
         "| **b** | x | 10 |\n"
         "| \\| p | [[Missing]] |\n"
         "| 1 | 2 | 3 | 4 |\n")


def test_table_exact(tmp_path):
    v = _vault(tmp_path, {"A.md": "", "T.md": "before\n\n" + TABLE})
    r = cli_json("render", v, "T.md")
    rows = ["Name │   al    │  n",
            "─" * 4 + "─┼─" + "─" * 7 + "─┼─" + "─" * 2,
            "b    │    x    │ 10",
            "| p  │ Missing │   ",
            "1    │    2    │  3"]
    assert r["text"] == "before\n\n" + "\n".join(rows)
    t0 = len("before\n\n")
    row = [t0 + sum(len(x) + 1 for x in rows[:i]) for i in range(len(rows))]
    assert r["links"] == [
        {"start": row[0] + 9, "end": row[0] + 11, "raw": "[[A|al]]", "resolved": "A.md"},
        {"start": row[3] + 7, "end": row[3] + 14, "raw": "[[Missing]]", "resolved": None}]
    assert _spans(r) == sorted([
        (t0, len(r["text"]), "table"), (row[0], row[0] + 4, "th"), (row[0] + 9, row[0] + 11, "th"),
        (row[0] + 9, row[0] + 11, "link"), (row[0] + 18, row[0] + 19, "th"),
        (row[2], row[2] + 1, "strong"), (row[3] + 7, row[3] + 14, "unresolved")])
    assert cli_json("blocks", v, "T.md") == [
        {"line": 1, "offset": 0}, {"line": 3, "offset": t0},
        {"line": 5, "offset": row[2]}, {"line": 6, "offset": row[3]}, {"line": 7, "offset": row[4]}]


def test_documents_without_extensions_are_unchanged(tmp_path):
    # A pipe line without a delimiter row, single tildes and bracket text are ordinary text.
    text = "a | b\nc | d\n\n~x~ [ ] y\n\n- [y] no\n- [ ]\n"
    v = _vault(tmp_path, {"T.md": text})
    r = cli_json("render", v, "T.md")
    assert r["text"] == "a | b c | d\n\n~x~ [ ] y\n\n• [y] no\n• [ ]"
    assert r["spans"] == [] and cli_json("tasks", v, "T.md") == []


def test_tasks_refusals(tmp_path):
    v = _vault(tmp_path, {"Bad.md": b"- [ ] \xff\n", "T.md": "x\n"})
    out = cli("tasks", v, "Bad.md", check=False)
    assert out.returncode == 2 and out.stderr.decode().startswith("refused: ")
    assert cli("tasks", v, "Nope.md", check=False).returncode == 2


def test_program_links_cmark_gfm_not_cmark():
    exe = build()
    for name in ("lcos-notes", "lcos-notes-cli"):
        libs = subprocess.run(["ldd", str(exe / name)], capture_output=True, text=True, check=True).stdout
        assert "libcmark-gfm.so" in libs and "libcmark-gfm-extensions.so" in libs, libs
        assert "libcmark.so" not in libs, libs


# ---------------------------------------------------------------- random documents vs the reference

CELLS = INLINE + ["", " ", "\\|", "~~s~~", "a ~~b~~ c", "~t~", "[x]", "[ ]", "**[[B]]**", "`a|b`",
                  "[[A|al]]", "[[Sub/C|c]]"]
TASK_TEXT = INLINE + ["~~s~~", "see [x] later", "[X]", "x ~~[[A]]~~ y"]


def _cell(rng):
    return " ".join(rng.choice(CELLS) for _ in range(rng.randint(0, 2)))


def _table(rng):
    n = rng.randint(1, 4)
    delim = [rng.choice(["---", ":--", ":-:", "--:", "-"]) for _ in range(n)]
    lead = rng.random() < 0.7
    def line(cells):
        s = " | ".join(cells)
        return ("| " + s + " |") if lead else s + (" |" if len(cells) == 1 else "")
    rows = [line([_cell(rng) or "h" for _ in range(n)]), line(delim)]
    for _ in range(rng.randint(0, 4)):
        rows.append(line([_cell(rng) for _ in range(max(1, n + rng.randint(-1, 1)))]))
    return "\n".join(rows)


def _tasks(rng, depth=0):
    ordered = rng.random() < 0.3
    start = rng.randint(1, 9)
    delim = rng.choice([".", ")"])
    items = []
    for i in range(rng.randint(1, 4)):
        marker = f"{start + i}{delim} " if ordered else rng.choice(["- ", "* ", "+ "])
        box = rng.choice(["[ ] ", "[x] ", "[X] ", "", "[ ]  "])
        body = box + " ".join(rng.choice(TASK_TEXT) for _ in range(rng.randint(1, 3)))
        if depth < 2 and rng.random() < 0.3:
            body += "\n" + _tasks(rng, depth + 1)
        elif rng.random() < 0.2:
            body += "\n\n" + _block(rng, 2)
        pad = " " * len(marker)
        items.append(marker + body.replace("\n", "\n" + pad))
    return ("\n\n" if rng.random() < 0.2 else "\n").join(items)


def _gfm_doc(rng):
    parts = []
    if rng.random() < 0.25:
        parts.append("---\ntags: [x]\nnote: [[A]]\n---")
    for _ in range(rng.randint(1, 6)):
        k = rng.randrange(6)
        if k == 0:
            parts.append(_table(rng))
        elif k == 1:
            parts.append(_tasks(rng))
        elif k == 2:
            parts.append("> " + _tasks(rng).replace("\n", "\n> "))
        elif k == 3:
            parts.append(" ".join(rng.choice(TASK_TEXT) for _ in range(rng.randint(1, 4))))
        else:
            parts.append(_block(rng))
    text = "\n\n".join(parts) + rng.choice(["", "\n"])
    return text.replace("\n", "\r\n") if rng.random() < 0.2 else text


@pytest.mark.parametrize("seed", range(40))
def test_gfm_render_blocks_and_tasks_match_reference(tmp_path, seed):
    rng = random.Random(7000 + seed)
    docs = {f"D{i}.md": _gfm_doc(rng) for i in range(8)}
    v = _vault(tmp_path, {"A.md": "# H\n", "B.md": "", "Sub/C.md": "", **docs})
    for name, text in docs.items():
        links = cli_json("links", v, name)
        md = markdown_links(v, name, text, links)
        assert cli_json("render", v, name) == ref_render(text, links, name, md), (name, text)
        assert cli_json("blocks", v, name) == ref_blocks(text, links, name, md), (name, text)
        assert cli_json("tasks", v, name) == ref_tasks(text, links, name, md), (name, text)


@pytest.mark.parametrize("seed", range(10))
def test_task_records_point_at_their_markers(tmp_path, seed):
    """Independent of the reference: each record's line/col is a "[", its checked state is the
    next character, and its offset is a box of that state in the rendered text."""
    rng = random.Random(7100 + seed)
    docs = {f"D{i}.md": "\n\n".join(_tasks(rng) for _ in range(3)) for i in range(5)}
    v = _vault(tmp_path, {"A.md": "", "B.md": "", "Sub/C.md": "", **docs})
    for name, text in docs.items():
        lines = text.split("\n")
        rendered = cli_json("render", v, name)["text"]
        recs = cli_json("tasks", v, name)
        assert rendered.count("☐") + rendered.count("☑") >= len(recs)
        for t in recs:
            line = lines[t["line"] - 1]
            assert line[t["col"] - 1] == "[" and line[t["col"] + 1] == "]", (line, t)
            assert t["checked"] == (line[t["col"]] in "xX"), (line, t)
            assert rendered[t["offset"]] == BOXES[t["checked"]], (rendered, t)


# ---------------------------------------------------------------- documentation

def test_user_docs_cover_u7():
    readme = (ROOT / "README.md").read_text()
    assert "Version 0.7.0." in readme
    update, install = readme.find("sudo apt update\n"), readme.find("sudo apt install ./lcos-notes_0.7.0_amd64.deb")
    assert 0 <= update < install
    for term in ("libcmark-gfm-dev", "libcmark-gfm-extensions-dev"):
        assert term in readme, term
    assert "libcmark0.30.2" not in readme and "libcmark-dev" not in readme
    guide = (ROOT / "DOCUMENTATION.md").read_text()
    assert "This guide covers version 0.7.0." in guide
    for term in ("table", "task", "Space", "strikethrough", "Reload from Disk", "Ctrl+Shift+R", "tasks",
                 "block quote"):
        assert term.lower() in guide.lower(), term
    man = next(ROOT.glob("data/lcos-notes-cli.1")).read_text()
    assert "tasks" in man
