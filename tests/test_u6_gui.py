"""U6 GUI: sidebar keyboard access, tree renames, tag rename, search options, unlinked
mentions (CONTRACT.md: U6)."""
from harness import cli_json, title, wait_for
from test_gui import assert_only_changed, gui, settle, vault, x  # noqa: F401  (pytest fixtures)
from test_u4_gui import RED, _link_point, _note


def _switch(app, query, name):
    app.key("ctrl+o")
    settle(0.8)
    app.type(query)
    settle(0.5)
    app.key("Return")
    app.wait_title(title(name))


def test_tree_keyboard_follows_note_and_refreshes(x, vault):
    v, before = vault
    _note(v, "Read.md", "[[Brand New]]\n")
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+shift+e")
    settle(0.5)
    app.key("Down", "Return")                            # the row after Home.md is Ideas.md
    app.wait_title(title("Ideas"))
    _switch(app, "nav", "Nav")
    app.key("ctrl+shift+e")
    settle(0.5)
    app.key("Up", "Return")                              # the selection followed the note: Ideas.md is above Nav.md
    app.wait_title(title("Ideas"))
    _switch(app, "read", "Read")
    app.key("Right", "Right", "alt+Return")              # creates Brand New.md
    app.wait_title(title("Brand New"))
    app.key("ctrl+shift+e")
    settle(0.5)
    app.key("Down", "Return")                            # refreshed tree: Café.md follows Brand New.md
    app.wait_title(title("Café"))
    assert_only_changed(v, before, {"Read.md", "Brand New.md"})


def test_tree_renames_folder_and_reopens_note(x, vault):
    v, before = vault
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+shift+e")
    settle(0.5)
    app.key("Up", "Up", "Up")                            # Café.md, diagram.png, then the images folder
    app.key("F2")
    settle(0.8)
    app.key("ctrl+a")
    app.type("pics")
    app.key("Return")
    wait_for(lambda: (v / "pics" / "diagram.png").exists() and not (v / "images").exists(), what="folder moved")
    wait_for(lambda: (v / "Home.md").read_text().split("\n")[4] == "Embed: ![[diagram.png]] and ![[diagram.png]].",
             what="embed rewritten")
    app.wait_title(title("Home"))
    settle(0.5)
    app.key("ctrl+Home")
    app.type("Z")                                        # the open note was reloaded: no stale buffer
    app.key("ctrl+s")
    wait_for(lambda: (v / "Home.md").read_text().split("\n")[4] == "Embed: ![[diagram.png]] and ![[diagram.png]]."
             and (v / "Home.md").read_text().startswith("Z"), what="reloaded note saved")
    # Q291 (Lee, 2026-11-02): Nav.md's [[images/diagram.png]] must be rewritten to keep resolving.
    assert (v / "Nav.md").read_text().split("\n")[3] == "[[diagram.png]]"
    assert cli_json("resolve", v, "Nav.md", "diagram.png")["resolved"] == "pics/diagram.png"
    assert_only_changed(v, before, {"Home.md", "Nav.md", "images", "images/diagram.png", "pics", "pics/diagram.png"})


def test_tree_renames_attachment(x, vault):
    v, before = vault
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+shift+e")
    settle(0.5)
    app.key("Up", "Up")                                  # images/diagram.png
    app.key("F2")
    settle(0.8)
    app.key("ctrl+a")
    app.type("images/chart.png")
    app.key("Return")
    wait_for(lambda: (v / "images" / "chart.png").exists(), what="attachment moved")
    wait_for(lambda: (v / "Home.md").read_text().split("\n")[4] == "Embed: ![[chart.png]] and ![[chart.png]].",
             what="embeds rewritten")
    # Q291 (Lee, 2026-11-02): Nav.md's [[images/diagram.png]] must be rewritten to keep resolving.
    assert (v / "Nav.md").read_text().split("\n")[3] == "[[chart.png]]"
    assert cli_json("resolve", v, "Nav.md", "chart.png")["resolved"] == "images/chart.png"
    assert_only_changed(v, before, {"Home.md", "Nav.md", "images/diagram.png", "images/chart.png"})


def test_tag_rename_dialog(x, vault):
    v, before = vault
    _note(v, "Read.md", "#aaa/x and #aaa\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("ctrl+shift+t")                              # first tag row: aaa
    settle(0.5)
    app.key("F2")
    settle(0.8)
    app.key("ctrl+a")
    app.type("zzz")
    app.key("Return")
    wait_for(lambda: (v / "Read.md").read_bytes() == b"#zzz/x and #zzz\n", what="tags rewritten")
    settle(0.5)
    _switch(app, "read", "Read")
    app.type("Q")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Read.md").read_bytes() == b"Q#zzz/x and #zzz\n", what="open note reloaded")
    assert_only_changed(v, before, {"Read.md"})


def test_search_dialog_word_and_regex(x, vault):
    v, before = vault
    _note(v, "Read.md", "zebras first\nzebra here\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("ctrl+shift+f")
    settle(0.8)
    app.type("z.bra")
    app.key("alt+r", "alt+w")
    settle(0.8)
    app.key("Return")                                    # first result: line 2 (line 1 is "zebras")
    settle(0.8)
    app.type("M")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Read.md").read_bytes() == b"zebras first\nMzebra here\n", what="whole-word regex hit")
    app.key("ctrl+shift+f")
    settle(0.8)
    app.type("zebra")                                    # options are off again: plain search, line 1
    settle(0.8)
    app.key("Return")
    settle(0.8)
    app.type("K")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Read.md").read_bytes() == b"Kzebras first\nMzebra here\n", what="plain hit")
    assert_only_changed(v, before, {"Read.md"})


def test_unlinked_mentions_pane(x, vault):
    v, before = vault
    _note(v, "Zeta Topic.md", "about\n")
    _note(v, "M.md", "first line [[Zeta Topic]]\nwe discuss zeta topic today\n")
    app = gui(x, v, "Zeta Topic.md")
    app.focus(title("Zeta Topic"))
    settle(0.8)
    app.key("ctrl+shift+m")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("M"))
    app.type("Q")
    app.key("ctrl+s")
    wait_for(lambda: (v / "M.md").read_bytes() == b"first line [[Zeta Topic]]\nwe discuss Qzeta topic today\n",
             what="caret at the mention")
    assert_only_changed(v, before, {"Zeta Topic.md", "M.md"})


# Usability (CONTRACT.md U6), from testing 0.5.0 on a real LCOS 1.0 install.

def test_new_note_from_reading_view_opens_for_writing(x, vault):
    v, before = vault
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+e")                                    # reading view on
    settle(0.8)
    app.key("ctrl+n")
    settle(0.8)
    app.type("Fresh/One")
    app.key("Return")
    app.wait_title(title("One"))
    settle(0.5)
    app.type("hello")                                    # editor focused, not reading view
    app.key("ctrl+s")
    wait_for(lambda: (v / "Fresh" / "One.md").exists() and (v / "Fresh" / "One.md").read_bytes() == b"hello",
             what="typed into the new note")
    assert_only_changed(v, before, {"Fresh", "Fresh/One.md"})


def test_new_note_with_existing_name_opens_it(x, vault):
    v, before = vault
    original = (v / "Ideas.md").read_bytes()
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+n")
    settle(0.8)
    app.type("ideas")
    app.key("Return")
    app.wait_title(title("Ideas"))
    settle(0.5)
    app.type("Q")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Ideas.md").read_bytes() == b"Q" + original, what="existing note opened, not duplicated")
    assert_only_changed(v, before, {"Ideas.md"})


def test_new_note_escape_cancels(x, vault):
    v, before = vault
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+n")
    settle(0.8)
    app.type("Never")
    app.key("Escape")
    settle(0.8)
    app.type("E")                                        # focus is back in the Home editor
    app.key("ctrl+s")
    wait_for(lambda: (v / "Home.md").read_bytes().startswith(b"E"), what="dialog cancelled")
    assert not (v / "Never.md").exists()
    assert_only_changed(v, before, {"Home.md"})


def test_switcher_create_row_after_matches(x, vault):
    v, before = vault
    _note(v, "Read.md", "x\n")
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+e")
    settle(0.8)
    app.key("ctrl+o")
    settle(0.8)
    app.type("Rea")                                      # matches Read.md; "Rea" itself is no note
    settle(0.8)
    app.key(*["Down"] * 30)                              # the last row is Create "Rea"
    app.key("Return")
    app.wait_title(title("Rea"))
    settle(0.5)
    app.type("z")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Rea.md").exists() and (v / "Rea.md").read_bytes() == b"z", what="created via the row")
    assert (v / "Read.md").read_bytes() == b"x\n"
    assert_only_changed(v, before, {"Read.md", "Rea.md"})


def test_switcher_enter_still_opens_first_match(x, vault):
    v, before = vault
    _note(v, "Read.md", "x\n")
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    _switch(app, "read", "Read")
    assert_only_changed(v, before, {"Read.md"})


def test_missing_link_from_reading_view_opens_for_writing(x, vault):
    v, before = vault
    _note(v, "Read.md", "go [[Brand New]] now\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("ctrl+e")
    settle(0.8)
    px, py = _link_point(app, "Read", RED)
    app.click(title("Read"), px, py)
    app.wait_title(title("Brand New"))
    settle(0.5)
    app.type("w")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Brand New.md").read_bytes() == b"w", what="typed into the created note")
    assert_only_changed(v, before, {"Read.md", "Brand New.md"})


def test_tags_tab_keeps_expansion(x, vault):
    v, before = vault
    _note(v, "TA.md", "#aab one\n")
    _note(v, "TB.md", "#aab two\n")
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+shift+t")                              # first tag row: aab (2)
    settle(0.5)
    app.key("Right")                                     # expand: TA.md, TB.md
    settle(0.3)
    app.key("Down", "Down", "Return")
    app.wait_title(title("TB"))
    settle(0.8)
    app.key("ctrl+shift+t")
    settle(0.5)
    app.key("Down", "Return")                            # still expanded: the row below aab is TA.md
    app.wait_title(title("TA"))
    assert_only_changed(v, before, {"TA.md", "TB.md"})


def test_backlink_into_list_lands_on_item_in_reading_view(x, vault):
    v, before = vault
    _note(v, "Zeta.md", "z\n")
    _note(v, "L.md", "# L\n\n- first [[Ideas]]\n- second\n- third [[Zeta]]\n")
    app = gui(x, v, "Zeta.md")
    app.focus(title("Zeta"))
    app.key("ctrl+e")
    settle(0.8)
    app.key("ctrl+shift+b", "Return")                    # the only backlink: L.md line 5
    app.wait_title(title("L"))
    settle(0.8)
    app.key("shift+End", "ctrl+c")                       # reading caret is at the third item
    settle(0.5)
    app.key("ctrl+e")                                    # editor: caret on the link (U2)
    settle(0.5)
    app.key("ctrl+End", "ctrl+v", "ctrl+s")
    wait_for(lambda: (v / "L.md").read_text().endswith("[[Zeta]]\n• third Zeta"), what="reading caret at item 3")
    assert_only_changed(v, before, {"Zeta.md", "L.md"})


def test_tag_rename_keeps_renamed_rows_expanded(x, vault):
    # Lee's 0.6.0 retest B11: expand a parent tag and its child tag, rename the parent with
    # F2, then rename it back; both renamed branches must stay expanded each time.
    v, before = vault
    _note(v, "TA.md", "#aab/x one\n")
    _note(v, "TB.md", "#aab/y two\n")
    _note(v, "TC.md", "#aab three\n")
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+shift+t")                              # first tag row: aab (3)
    settle(0.5)
    app.key("Right")                                     # aab: TA.md, TB.md, TC.md
    settle(0.3)
    app.key("Down", "Down", "Down", "Down", "Right")     # aab/x: TA.md
    settle(0.3)
    for old, new in [("aab", "aac"), ("aac", "aab")]:
        app.key("ctrl+shift+t")                          # first row: the parent tag
        settle(0.5)
        app.key("F2")
        settle(0.8)
        app.key("ctrl+a")
        app.type(new)
        app.key("Return")
        wait_for(lambda: (v / "TA.md").read_bytes() == f"#{new}/x one\n".encode(), what=f"{old} renamed to {new}")
        settle(0.8)
        app.key("ctrl+shift+t")
        settle(0.5)
        # Rows: new (expanded), TA, TB, TC, new/x (expanded), TA, new/y. If either renamed
        # branch collapsed, the sixth row is a tag row and Enter opens no note.
        app.key("Down", "Down", "Down", "Down", "Down", "Return")
        app.wait_title(title("TA"))
    assert_only_changed(v, before, {"TA.md", "TB.md", "TC.md"})
