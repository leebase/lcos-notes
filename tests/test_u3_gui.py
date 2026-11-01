"""U3 GUI: reading view (CONTRACT.md: U3 > Reading view in the GUI)."""
from harness import title, wait_for
from test_gui import assert_only_changed, gui, settle, vault, x  # noqa: F401  (pytest fixtures)


def _note(v, name, text):
    (v / name).write_bytes(text.encode())
    return (v / name).read_bytes()


def test_reading_view_is_read_only_and_enter_follows(x, vault):
    v, before = vault
    read = _note(v, "Read.md", "ab [[Ideas]] cd\n\n[[Brand New]]\n")
    ideas = (v / "Ideas.md").read_bytes()
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("ctrl+e")
    settle(0.8)
    app.type("X")                                        # read-only: no edit, no save
    app.key("ctrl+s", "ctrl+z", "Return")                # Return at offset 0 is not on a link
    settle()
    assert [w["title"] for w in app.windows()] == [title("Read")]
    assert (v / "Read.md").read_bytes() == read
    app.key("Right", "Right", "Right", "Return")         # offset 3: start of rendered "Ideas"
    app.wait_title(title("Ideas"))
    app.type("Y")                                        # still reading: the mode is sticky
    app.key("ctrl+s")
    settle()
    assert [w["title"] for w in app.windows()] == [title("Ideas")]
    assert (v / "Ideas.md").read_bytes() == ideas
    app.key("ctrl+e")                                    # back to editing
    settle(0.5)
    app.type("Z")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Ideas.md").read_bytes() == b"Z" + ideas, what="edit after leaving reading view")
    assert_only_changed(v, before, {"Read.md", "Ideas.md"})
    assert (v / "Read.md").read_bytes() == read


def test_reading_view_renders_unsaved_buffer_and_saves_before_following(x, vault):
    v, before = vault
    _note(v, "Read.md", "first line\n")
    nav = (v / "Nav.md").read_bytes()
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.type("[[Nav]] ")
    app.wait_title(title("Read", modified=True))
    app.key("ctrl+e")
    settle(0.8)
    app.key("Return")                                    # rendered "Nav first line": caret on the link
    app.wait_title(title("Nav"))
    assert (v / "Read.md").read_bytes() == b"[[Nav]] first line\n"
    app.key("ctrl+e")
    settle(0.5)
    app.type("N")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Nav.md").read_bytes() == b"N" + nav, what="editor caret at note start")
    assert_only_changed(v, before, {"Read.md", "Nav.md"})


def test_reading_view_heading_follow_places_editor_caret(x, vault):
    v, before = vault
    _note(v, "Read.md", "[[Projects/Alpha#Plan]]\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("ctrl+e")
    settle(0.8)
    app.key("alt+Return")
    app.wait_title(title("Alpha"))
    app.key("ctrl+e")
    settle(0.5)
    app.type("M")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Projects" / "Alpha.md").read_text().split("\n")[4] == "M## Plan",
             what="caret at the heading line")
    assert_only_changed(v, before, {"Read.md", "Projects/Alpha.md"})


def test_reading_view_unresolved_link_creates_note(x, vault):
    v, before = vault
    _note(v, "Read.md", "[[Brand New]] is next\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("ctrl+e")
    settle(0.8)
    app.key("Right", "Return")
    app.wait_title(title("Brand New"))
    assert (v / "Brand New.md").read_bytes() == b""
    assert_only_changed(v, before, {"Read.md", "Brand New.md"})


def test_mode_is_sticky_through_the_switcher(x, vault):
    v, before = vault
    nav = (v / "Nav.md").read_bytes()
    app = gui(x, v, "Ideas.md")
    app.focus(title("Ideas"))
    app.key("ctrl+e")
    settle(0.8)
    app.key("ctrl+o")
    settle(0.8)
    app.type("nav")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("Nav"))
    settle(0.5)
    app.type("Q")
    app.key("ctrl+s")
    settle()
    assert (v / "Nav.md").read_bytes() == nav
    app.key("ctrl+e")
    settle(0.5)
    app.type("Q")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Nav.md").read_bytes() == b"Q" + nav, what="edit after switcher in reading view")
    assert_only_changed(v, before, {"Nav.md"})


def test_switching_back_restores_editor_caret(x, vault):
    v, before = vault
    _note(v, "Read.md", "abc\ndef\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("Down", "Right")                             # editor caret: line 2, after "d"
    app.key("ctrl+e")
    settle(0.8)
    app.key("Right", "Right", "Down")                    # moves only the reading caret
    app.key("ctrl+e")
    settle(0.5)
    app.type("K")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Read.md").read_bytes() == b"abc\ndKef\n", what="restored editor caret")
    assert_only_changed(v, before, {"Read.md"})
