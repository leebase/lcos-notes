"""U5 GUI: following Markdown note links and block references (CONTRACT.md: U5)."""
from harness import title, wait_for
from test_gui import assert_only_changed, gui, settle, vault, x  # noqa: F401  (pytest fixtures)
from test_u4_gui import BLUE, _link_point, _note


def test_editor_follows_markdown_link_to_heading(x, vault):
    v, before = vault
    _note(v, "Read.md", "[plan](Projects/Alpha.md#Plan) tail\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("Right", "Right", "alt+Return")
    app.wait_title(title("Alpha"))
    app.type("M")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Projects" / "Alpha.md").read_text().split("\n")[4] == "M## Plan", what="heading caret")
    assert_only_changed(v, before, {"Read.md", "Projects/Alpha.md"})


def test_unresolved_markdown_link_creates_relative_note(x, vault):
    v, before = vault
    _note(v, "Docs/R.md", "[new](Fresh/Idea%20One.md)\n")
    app = gui(x, v, "Docs/R.md")
    app.focus(title("R"))
    app.key("Right", "alt+Return")
    app.wait_title(title("Idea One"))
    assert (v / "Docs" / "Fresh" / "Idea One.md").read_bytes() == b""
    assert_only_changed(v, before, {"Docs", "Docs/R.md", "Docs/Fresh", "Docs/Fresh/Idea One.md"})


def test_markdown_link_highlighted_and_clickable(x, vault):
    v, before = vault
    _note(v, "Read.md", "go [to ideas](Ideas.md) now\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    px, py = _link_point(app, "Read")                    # editor highlight in the link color
    app.click(title("Read"), px, py, "ctrl")
    app.wait_title(title("Ideas"))
    assert_only_changed(v, before, {"Read.md"})


def test_reading_view_follows_markdown_link(x, vault):
    v, before = vault
    _note(v, "Read.md", "go [to nav](Nav.md) now\n\n[other](Ideas.md)\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("ctrl+e")
    settle(0.8)
    px, py = _link_point(app, "Read")
    app.click(title("Read"), px, py)
    app.wait_title(title("Nav"))
    assert_only_changed(v, before, {"Read.md"})


BLK = ("intro\n\n```\nfake ^id1\n```\n\n" + "".join(f"Filler {i}\n\n" for i in range(30)) +
       "[[Nav]] real line ^ID1  \nafter\n")
BLK_LINE = 6 + 60 + 1                                    # 1-based line of "[[Nav]] real line ^ID1"


def test_block_reference_places_editor_caret(x, vault):
    v, before = vault
    _note(v, "Blk.md", BLK)
    _note(v, "Read.md", "[[Blk#^id1]] and [m](Blk.md#%5Eid1) and [[Blk#^nope]]\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("Right", "Right", "alt+Return")
    app.wait_title(title("Blk"))
    app.type("M")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Blk.md").read_text().split("\n")[BLK_LINE - 1] == "M[[Nav]] real line ^ID1  ",
             what="caret at block line")
    assert_only_changed(v, before, {"Blk.md", "Read.md"})


def test_markdown_block_reference_and_missing_block(x, vault):
    v, before = vault
    blk = _note(v, "Blk.md", BLK)
    _note(v, "Read.md", "[m](Blk.md#%5Eid1) [[Blk#^nope]]\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("Right", "alt+Return")
    app.wait_title(title("Blk"))
    app.type("Q")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Blk.md").read_text().split("\n")[BLK_LINE - 1] == "Q[[Nav]] real line ^ID1  ",
             what="caret at block line (markdown)")
    app.key("ctrl+z")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Blk.md").read_bytes() == blk, what="undo")
    app.key("ctrl+o")
    settle(0.8)
    app.type("read")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("Read"))
    app.key("End", "Left", "Left", "Left", "alt+Return")  # inside [[Blk#^nope]]
    app.wait_title(title("Blk"))
    app.type("S")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Blk.md").read_bytes() == b"S" + blk, what="missing block: note start")
    assert_only_changed(v, before, {"Blk.md", "Read.md"})


def test_block_reference_in_reading_view_places_reading_caret(x, vault):
    v, before = vault
    _note(v, "Blk.md", BLK)
    _note(v, "Read.md", "[[Blk#^id1]]\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("ctrl+e")
    settle(0.8)
    app.key("Return")
    app.wait_title(title("Blk"))
    settle(0.8)
    assert app.shot(title("Blk")).find(BLUE, 12), "the block is scrolled into view"
    app.key("Return")                                    # reading caret at the block: the Nav link
    app.wait_title(title("Nav"))
    assert_only_changed(v, before, {"Blk.md", "Read.md"})
