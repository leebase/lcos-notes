"""U7 GUI: toggling task boxes in reading view, reloading files changed on disk, the vault
following external changes (CONTRACT.md: U7)."""
import os

from harness import title, wait_for
from test_gui import assert_only_changed, gui, settle, vault, x  # noqa: F401  (pytest fixtures)
from test_u4_gui import BLUE, _link_point, _note

RELOAD = 3.0          # the contract's 2 seconds, plus slack


def _external(path, text):
    """Write as another program would: a new file renamed over the old one."""
    tmp = path.with_name(path.name + ".ext~")
    tmp.write_bytes(text.encode())
    os.replace(tmp, path)


# ---------------------------------------------------------------- task boxes

def test_space_toggles_task_boxes_in_reading_view(x, vault):
    v, before = vault
    text = "# T\n\n- [ ] first\n- [x] second\n"
    _note(v, "Todo.md", text)
    app = gui(x, v, "Todo.md")
    app.focus(title("Todo"))
    app.key("Down", "Down")                              # editor line 3: reading caret on its box
    app.key("ctrl+e")
    settle(0.8)
    app.key("space")
    wait_for(lambda: (v / "Todo.md").read_text() == "# T\n\n- [x] first\n- [x] second\n", what="first checked")
    app.wait_title(title("Todo"))                        # saved: not modified
    app.key("space")                                     # the caret stayed on the box
    wait_for(lambda: (v / "Todo.md").read_text() == text, what="first unchecked again")
    app.key("Down", "space")                             # same x on the next line: the second box
    wait_for(lambda: (v / "Todo.md").read_text() == "# T\n\n- [ ] first\n- [ ] second\n", what="second unchecked")
    app.key("Right", "space")                            # after the box: Space does nothing
    settle(1.0)
    assert (v / "Todo.md").read_text() == "# T\n\n- [ ] first\n- [ ] second\n"
    app.wait_title(title("Todo"))
    app.key("ctrl+e")                                    # the editor shows the toggled text
    app.key("ctrl+Home", "Down", "Down", "Right", "Right", "Right", "Delete")
    app.type("X")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Todo.md").read_text() == "# T\n\n- [X] first\n- [ ] second\n", what="editor edit")
    app.key("ctrl+e")
    settle(0.8)
    app.key("space")                                     # "X" counts as checked
    wait_for(lambda: (v / "Todo.md").read_text() == "# T\n\n- [ ] first\n- [ ] second\n", what="X unchecked")
    assert_only_changed(v, before, {"Todo.md"})


def test_toggle_saves_unsaved_edits_like_ctrl_s(x, vault):
    v, before = vault
    _note(v, "Edit.md", "- [ ] a\n")
    app = gui(x, v, "Edit.md")
    app.focus(title("Edit"))
    app.key("ctrl+End")
    app.type("tail")                                     # lazy continuation of the item's paragraph
    app.wait_title(title("Edit", modified=True))
    app.key("ctrl+e")
    settle(0.8)
    app.key("space")
    wait_for(lambda: (v / "Edit.md").read_text() == "- [x] a\ntail", what="toggle saved the edit too")
    app.wait_title(title("Edit"))
    assert_only_changed(v, before, {"Edit.md"})


def test_click_on_a_box_toggles_it(x, vault):
    v, before = vault
    _note(v, "Click.md", "Plain words first.\n\n- [ ] click me\n")
    app = gui(x, v, "Click.md")
    app.focus(title("Click"))
    app.key("ctrl+e")
    settle(0.8)
    px, py = _link_point(app, "Click", BLUE)             # the only link-colored glyph is the box
    app.click(title("Click"), px, py)
    wait_for(lambda: (v / "Click.md").read_text() == "Plain words first.\n\n- [x] click me\n", what="click toggled")
    app.click(title("Click"), px, py, "ctrl")            # only a plain click toggles
    settle(1.0)
    assert (v / "Click.md").read_text() == "Plain words first.\n\n- [x] click me\n"
    assert_only_changed(v, before, {"Click.md"})


def test_toggle_refused_when_changed_on_disk_keeps_buffer(x, vault):
    v, before = vault
    _note(v, "Race.md", "- [ ] a\n")
    app = gui(x, v, "Race.md")
    app.focus(title("Race"))
    app.key("ctrl+End")
    app.type("more")                                     # unsaved: an external change is not reloaded
    app.wait_title(title("Race", modified=True))
    _external(v / "Race.md", "- [ ] a\nother\n")
    settle(RELOAD)
    app.key("ctrl+e")
    settle(0.8)
    app.key("space")
    settle(1.0)
    assert (v / "Race.md").read_text() == "- [ ] a\nother\n"
    app.wait_title(title("Race", modified=True))
    assert_only_changed(v, before, {"Race.md"})


# ---------------------------------------------------------------- reloading the open note

def test_external_change_reloads_and_keeps_line_and_column(x, vault):
    v, before = vault
    _note(v, "Ext.md", "one\ntwo\nthree\n")
    app = gui(x, v, "Ext.md")
    app.focus(title("Ext"))
    app.key("Down", "Right", "Right", "Right")           # line 2, column 4 (after "two")
    _external(v / "Ext.md", "zero\nonce\ntwo!\nthree\n")
    settle(RELOAD)
    app.wait_title(title("Ext"))
    app.key("ctrl+z")                                    # the reload is not undoable
    app.type("Z")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Ext.md").read_text() == "zero\noncZe\ntwo!\nthree\n", what="caret kept line 2 col 4")
    settle(RELOAD)                                       # our own save does not reload or move the caret
    app.type("Y")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Ext.md").read_text() == "zero\noncZYe\ntwo!\nthree\n", what="caret after own save")
    (v / "Ext.md").write_text("a\nb\n")                 # written in place this time; clamped to line 2's end
    settle(RELOAD)
    app.type("Q")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Ext.md").read_text() == "a\nbQ\n", what="clamped caret")
    assert_only_changed(v, before, {"Ext.md"})


def test_unsaved_edits_are_kept_until_reload_from_disk(x, vault):
    v, before = vault
    _note(v, "Keep.md", "alpha\nbeta\n")
    app = gui(x, v, "Keep.md")
    app.focus(title("Keep"))
    app.key("Down")
    app.type("Z")
    app.wait_title(title("Keep", modified=True))
    _external(v / "Keep.md", "alpha\nBETA\ngamma\n")
    settle(RELOAD)
    app.wait_title(title("Keep", modified=True))         # not reloaded
    app.key("ctrl+s")                                    # U1: refused, file untouched
    settle(1.0)
    assert (v / "Keep.md").read_text() == "alpha\nBETA\ngamma\n"
    app.key("ctrl+shift+r")
    app.wait_title(title("Keep"))
    app.key("ctrl+s")                                    # unmodified: nothing written
    settle(0.5)
    assert (v / "Keep.md").read_text() == "alpha\nBETA\ngamma\n"
    app.type("Q")                                        # caret kept: line 2, column 2
    app.key("ctrl+s")
    wait_for(lambda: (v / "Keep.md").read_text() == "alpha\nBQETA\ngamma\n", what="edit after reload")
    assert_only_changed(v, before, {"Keep.md"})


def test_reload_from_disk_discards_edits_without_external_change(x, vault):
    v, before = vault
    _note(v, "Menu.md", "same\n")
    app = gui(x, v, "Menu.md")
    app.focus(title("Menu"))
    app.type("dirty ")
    app.wait_title(title("Menu", modified=True))
    app.key("ctrl+shift+r")                              # discards the edit, no confirmation
    app.wait_title(title("Menu"))
    app.key("ctrl+s")
    settle(0.5)
    assert (v / "Menu.md").read_text() == "same\n"
    assert_only_changed(v, before, {"Menu.md"})


def test_external_delete_keeps_buffer_and_ctrl_s_restores(x, vault):
    v, before = vault
    _note(v, "Gone.md", "keep me\n")
    app = gui(x, v, "Gone.md")
    app.focus(title("Gone"))
    (v / "Gone.md").unlink()
    app.wait_title(title("Gone", modified=True), timeout=RELOAD + 2)
    app.key("ctrl+s")
    wait_for(lambda: (v / "Gone.md").exists() and (v / "Gone.md").read_text() == "keep me\n", what="written back")
    app.wait_title(title("Gone"))
    assert_only_changed(v, before, {"Gone.md"})


# ---------------------------------------------------------------- the vault follows external changes

def test_notes_tree_follows_external_create_and_delete(x, vault):
    v, before = vault
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    (v / "Hz.md").write_text("# hz\n")                   # sorts between Home.md and Ideas.md
    settle(RELOAD)
    app.key("ctrl+shift+e")
    settle(0.5)
    app.key("Down", "Return")
    app.wait_title(title("Hz"))
    app.key("ctrl+o")
    settle(0.8)
    app.type("home")
    app.key("Return")
    app.wait_title(title("Home"))
    (v / "Hz.md").unlink()
    settle(RELOAD)
    app.key("ctrl+shift+e")
    settle(0.5)
    app.key("Down", "Return")                            # Hz.md is gone: Ideas.md follows Home.md
    app.wait_title(title("Ideas"))
    assert_only_changed(v, before, set())


def test_tags_tab_follows_external_change(x, vault):
    v, before = vault
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+shift+t")
    settle(0.5)
    _note(v, "Aaa.md", "#aaaa first\n")                  # "aaaa" sorts before every fixture tag
    settle(RELOAD)
    app.key("ctrl+shift+t")
    settle(0.5)
    app.key("Home", "Right")                             # expand the first tag
    settle(0.3)
    app.key("Down", "Return")                            # its first note
    app.wait_title(title("Aaa"))
    assert_only_changed(v, before, {"Aaa.md"})
