"""U4 core rules through lcos-notes-cli: blocks, search within a line (CONTRACT.md: U4)."""
import random

import pytest

from harness import cli, cli_json
from reference_render import blocks as reference_blocks
from test_u3_core import _doc, _vault


def test_blocks_exact(tmp_path):
    text = "---\ntags: [x]\n---\n# Head [[A]]\n\npara one\nline two\n\n- a\n- b\n\n> q\n"
    v = _vault(tmp_path, {"A.md": "", "R.md": text, "C.md": text.replace("\n", "\r\n")})
    want = [{"line": 4, "offset": 0}, {"line": 6, "offset": 8}, {"line": 9, "offset": 27},
            {"line": 12, "offset": 36}]
    assert cli_json("blocks", v, "R.md") == want
    assert cli_json("blocks", v, "C.md") == want


def test_blocks_empty_frontmatter_only_and_unclosed(tmp_path):
    v = _vault(tmp_path, {"E.md": "", "F.md": "---\na: b\n---\n", "U.md": "---\nx\n\npara\n"})
    assert cli_json("blocks", v, "E.md") == []
    assert cli_json("blocks", v, "F.md") == []
    # Unclosed frontmatter is not frontmatter: the thematic break is block 1.
    assert cli_json("blocks", v, "U.md") == [{"line": 1, "offset": 0}, {"line": 2, "offset": 22},
                                             {"line": 4, "offset": 25}]


def test_blocks_offsets_follow_rendered_link_text(tmp_path):
    v = _vault(tmp_path, {"Long Name.md": "", "R.md": "[[Long Name|a much longer alias]]\n\n``` \n[[x]]\n```\n\nz\n"})
    r = cli_json("render", v, "R.md")
    got = cli_json("blocks", v, "R.md")
    assert got == [{"line": 1, "offset": 0}, {"line": 3, "offset": 21}, {"line": 7, "offset": 28}]
    assert r["text"][21:26] == "[[x]]" and r["text"][28:] == "z"


def test_blocks_refusals(tmp_path):
    v = _vault(tmp_path, {"Bad.md": b"\xff\n", "A.md": ""})
    for args in [("blocks", v, "Bad.md"), ("blocks", v, "Missing.md"), ("blocks", v, "../A.md")]:
        proc = cli(*args, check=False)
        assert proc.returncode == 2 and proc.stderr.decode().startswith("refused: "), args


@pytest.mark.parametrize("seed", range(40))
def test_blocks_match_reference(tmp_path, seed):
    rng = random.Random(10_000 + seed)
    docs = {f"D{i}.md": _doc(rng) for i in range(8)}
    v = _vault(tmp_path, {"A.md": "# H\n", "B.md": "", "Sub/C.md": "", **docs})
    for name, text in docs.items():
        links = cli_json("links", v, name)
        got = cli_json("blocks", v, name)
        assert got == reference_blocks(text, links, name), (name, text)
        rendered = cli_json("render", v, name)["text"]
        assert all(0 <= b["offset"] <= len(rendered) for b in got)


def test_search_never_spans_a_line_end(tmp_path):
    v = _vault(tmp_path, {"A.md": "xa\r\nya\rb\nza\n", "B.md": "end a\r\n\r\n", "C.md": "q\r"})
    assert cli_json("find", v, "a\r") == [{"path": "A.md", "line": 2, "col": 2, "text": "ya\rb"}]
    assert cli_json("find", v, "\r") == [{"path": "A.md", "line": 2, "col": 3, "text": "ya\rb"}]
    assert cli_json("find", v, "q") == [{"path": "C.md", "line": 1, "col": 1, "text": "q"}]
    for q in ["a\n", "\n", "\r\n", "a\r\ny", "xa\r\n"]:
        assert cli_json("find", v, q) == [], repr(q)
    assert cli_json("find", v, "a") == [
        {"path": "A.md", "line": 1, "col": 2, "text": "xa"}, {"path": "A.md", "line": 2, "col": 2, "text": "ya\rb"},
        {"path": "A.md", "line": 3, "col": 2, "text": "za"}, {"path": "B.md", "line": 1, "col": 5, "text": "end a"}]
