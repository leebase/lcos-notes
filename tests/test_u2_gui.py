"""U2 GUI behavior: backlinks pane, search dialog, rename dialog (CONTRACT.md: U2 GUI additions)."""
from harness import title, tree_digest, wait_for
from test_gui import assert_only_changed, gui, settle, vault, x  # noqa: F401  (pytest fixtures)


def test_backlinks_pane_opens_source_at_link(x, vault):
    v, before = vault
    app = gui(x, v, "Ideas.md")
    app.focus(title("Ideas"))
    settle(0.8)
    app.key("ctrl+shift+b")
    settle(0.5)
    app.key("Return")                                    # first backlink: Home.md line 3, col 8
    app.wait_title(title("Home"))
    app.type("M")
    app.key("ctrl+s")
    app.wait_title(title("Home"))
    wait_for(lambda: (v / "Home.md").read_text().split("\n")[2] ==
             "Links: M[[Ideas]] and [[Projects/Alpha|the alpha]] and [[Deep]].", what="marker at backlink")
    assert_only_changed(v, before, {"Home.md"})


def test_backlinks_follow_the_open_note(x, vault):
    v, before = vault
    app = gui(x, v, "Ideas.md")
    app.focus(title("Ideas"))
    app.key("ctrl+o")
    settle(0.8)
    app.type("alph")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("Alpha"))
    settle(0.8)
    app.key("ctrl+shift+b")
    settle(0.5)
    app.key("Down", "Down", "Return")                    # third backlink of Alpha: Nav.md line 1
    app.wait_title(title("Nav"))
    app.type("N")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Nav.md").read_bytes().startswith(b"N[[Projects/Alpha#plan]]\n"), what="Nav marker")
    assert_only_changed(v, before, {"Nav.md"})


def test_search_dialog_opens_match(x, vault):
    v, before = vault
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+shift+f")
    settle(0.8)
    app.type("second plan")
    settle(0.8)
    app.key("Return")
    app.wait_title(title("Alpha"))
    app.type("S")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Projects" / "Alpha.md").read_text().split("\n")[10] == "SSecond plan heading.",
             what="marker at match")
    app.key("ctrl+shift+f")
    settle(0.8)
    app.type("zzqq nothing")
    settle(0.8)
    app.key("Return")
    settle()
    assert [w["title"] for w in app.windows()] == [title("Alpha")]
    app.key("ctrl+shift+f")
    settle(0.8)
    app.type("ideas")
    settle(0.5)
    app.key("Escape")
    settle()
    assert [w["title"] for w in app.windows()] == [title("Alpha")]
    assert_only_changed(v, before, {"Projects/Alpha.md"})


def test_rename_dialog_saves_renames_rewrites_keeps_caret(x, vault):
    v, before = vault
    ideas = (v / "Ideas.md").read_bytes()
    app = gui(x, v, "Ideas.md")
    app.focus(title("Ideas"))
    app.key("Down", "Down")                              # caret at line 3 start
    app.type("U")                                        # unsaved edit: must be saved first
    app.wait_title(title("Ideas", modified=True))
    app.key("F2")
    settle(0.8)
    app.key("ctrl+a")
    app.type("Archive/Thoughts")
    settle(0.3)
    app.key("Return")
    app.wait_title(title("Thoughts"))
    wait_for(lambda: (v / "Archive" / "Thoughts.md").exists(), what="renamed file")
    assert not (v / "Ideas.md").exists()
    lines = ideas.decode().split("\n")
    lines[2] = "U" + lines[2]
    assert (v / "Archive" / "Thoughts.md").read_text() == "\n".join(lines)
    home = (v / "Home.md").read_text().split("\n")
    assert home[2] == "Links: [[Thoughts]] and [[Projects/Alpha|the alpha]] and [[Deep]]."
    app.type("C")                                        # caret kept its position (after the U)
    app.key("ctrl+s")
    wait_for(lambda: (v / "Archive" / "Thoughts.md").read_text().split("\n")[2] == "UCA root note.",
             what="caret preserved")
    assert_only_changed(v, before, {"Ideas.md", "Archive/Thoughts.md", "Home.md", "Notes CRLF.md",
                                    "Projects/Sub/Deep.md"})


def test_rename_refused_changes_nothing(x, vault):
    v, before = vault
    app = gui(x, v, "Ideas.md")
    app.focus(title("Ideas"))
    app.key("F2")
    settle(0.8)
    app.key("ctrl+a")
    app.type("home")
    settle(0.3)
    app.key("Return")
    settle()
    assert [w["title"] for w in app.windows()] == [title("Ideas")]
    app.key("F2")
    settle(0.8)
    app.type("whatever")
    app.key("Escape")
    settle()
    assert [w["title"] for w in app.windows()] == [title("Ideas")]
    assert tree_digest(v) == before
