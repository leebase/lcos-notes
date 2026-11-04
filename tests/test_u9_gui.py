"""U9 GUI: Today's Note, previous/next daily note, New Note templates and timestamp names,
Insert Template, the capture window and captures into an open note (CONTRACT.md: U9)."""
import json
import os
import subprocess

from harness import build, title, tree_digest, wait_for
from test_gui import assert_only_changed, gui, settle, vault, x  # noqa: F401  (pytest fixtures)
from test_u4_gui import _note

NOW = "2026-11-03T09:30:05"                                       # a Tuesday
RELOAD = 3.0


def _clock(x):
    x.env["LCOS_NOTES_NOW"] = NOW


def _settings(v, name, obj):
    (v / ".obsidian").mkdir(exist_ok=True)
    (v / ".obsidian" / name).write_text(json.dumps(obj))


def _capture_window(x, v=None):
    argv = [str(build() / "lcos-notes"), "--capture"] + (["--vault", str(v)] if v else [])
    return x.launch(argv)


def test_today_note_from_template_opens_for_writing(x, vault):
    v, _ = vault
    _clock(x)
    _settings(v, "daily-notes.json", {"folder": "Journal", "format": "YYYY/MM-DD", "template": "Templates/Day"})
    _note(v, "Templates/Day.md", "# {{title}}\n{{date:dddd}}\n")
    before = tree_digest(v)
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+e")                                            # reading view: Ctrl+D leaves it
    settle(0.8)
    app.key("ctrl+d")
    app.wait_title(title("11-03"))
    app.type("x")                                                # caret at the end, editor focused
    app.key("ctrl+s")
    wait_for(lambda: (v / "Journal/2026/11-03.md").read_text() == "# 11-03\nTuesday\nx", what="today's note")
    app.focus(title("11-03"))
    app.key("ctrl+d")                                            # exists: opened, not created again
    settle(1.0)
    app.wait_title(title("11-03"))
    assert (v / "Journal/2026/11-03.md").read_text() == "# 11-03\nTuesday\nx"
    assert_only_changed(v, before, {"Journal", "Journal/2026", "Journal/2026/11-03.md"})


def test_previous_and_next_daily_note_skip_gaps(x, vault):
    v, _ = vault
    _note(v, "2026-10-30.md", "older\n")
    _note(v, "2026-11-03.md", "newer\n")
    _note(v, "Plain.md", "plain\n")
    before = tree_digest(v)
    app = gui(x, v, "2026-11-03.md")
    app.focus(title("2026-11-03"))
    app.key("alt+Left")
    app.wait_title(title("2026-10-30"))
    app.key("alt+Left")                                          # no earlier daily note
    settle(1.0)
    app.wait_title(title("2026-10-30"))
    app.key("ctrl+e")                                            # reading view: still works, stays on
    settle(0.8)
    app.key("alt+Right")
    app.wait_title(title("2026-11-03"))
    app.type("z")                                                # reading view is still on: no edit
    settle(0.5)
    app.wait_title(title("2026-11-03"))
    app.key("alt+Right")                                         # no later daily note
    settle(1.0)
    app.wait_title(title("2026-11-03"))
    app.key("ctrl+o")
    settle(0.8)
    app.type("Plain")
    app.key("Return")
    app.wait_title(title("Plain"))
    app.key("alt+Left")                                          # not a daily note: nothing happens
    settle(1.0)
    app.wait_title(title("Plain"))
    assert_only_changed(v, before, set())


def test_new_note_with_template_and_timestamp_name(x, vault):
    v, _ = vault
    _clock(x)
    _note(v, "Templates/Meeting.md", "## {{title}}\n{{date}} {{time}}\n")
    before = tree_digest(v)
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+n")
    app.wait_title("New Note")
    app.type("Standup")
    app.key("alt+t")                                             # the Template drop-down
    app.key("Down")                                              # None → Meeting
    app.key("Return")                                            # Enter creates from the drop-down too
    app.wait_title(title("Standup"))
    wait_for(lambda: (v / "Standup.md").exists(), what="Standup.md")
    assert (v / "Standup.md").read_text() == "## Standup\n2026-11-03 09:30\n"
    app.key("ctrl+n")
    app.wait_title("New Note")
    app.key("alt+n")                                             # Timestamp Name
    app.key("Return")
    app.wait_title(title("202611030930"))
    assert (v / "202611030930.md").read_bytes() == b""
    assert_only_changed(v, before, {"Standup.md", "202611030930.md"})


def test_insert_template_is_one_undo_step(x, vault):
    v, _ = vault
    _clock(x)
    _note(v, "Templates/A.md", "first template\n")
    _note(v, "Templates/Sig.md", "-- {{title}} {{date:D MMM}}\n")
    _note(v, "Doc.md", "a\n")
    before = tree_digest(v)
    app = gui(x, v, "Doc.md")
    app.focus(title("Doc"))
    app.key("ctrl+End")
    app.key("ctrl+shift+i")
    app.wait_title("Insert Template")
    app.key("Down", "Return")                                    # rows: A, Sig
    settle(0.8)
    app.key("ctrl+s")
    wait_for(lambda: (v / "Doc.md").read_text() == "a\n-- Doc 3 Nov\n", what="inserted template")
    app.key("ctrl+z")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Doc.md").read_text() == "a\n", what="one undo step")
    app.key("ctrl+shift+i")
    app.wait_title("Insert Template")
    app.key("Escape")
    wait_for(lambda: not [w for w in app.windows() if w["title"] == "Insert Template"], what="dialog closed")
    app.key("ctrl+s")
    settle(0.5)
    assert (v / "Doc.md").read_text() == "a\n"
    assert_only_changed(v, before, {"Doc.md"})


def test_capture_window_writes_and_remembers_the_inbox(x, vault):
    v, _ = vault
    _clock(x)
    before = tree_digest(v)
    lost = _capture_window(x)                                    # no --vault and no last vault
    assert lost.proc.wait(15) == 2
    assert b"refused: no vault" in lost.proc.stderr.read()
    app = _capture_window(x, v)
    app.focus("Capture — Notes")
    app.key("ctrl+Return")                                       # nothing typed: nothing happens
    settle(1.0)
    app.wait_title("Capture — Notes")
    app.type("first line")
    app.key("Return")
    app.type("second")
    app.key("ctrl+Return")
    assert app.proc.wait(15) == 0
    assert (v / "2026-11-03.md").read_text() == "- 09:30 first line\n  second\n"
    app = _capture_window(x, v)
    app.focus("Capture — Notes")
    app.key("alt+i")
    app.type("to inbox")
    app.key("ctrl+Return")
    assert app.proc.wait(15) == 0
    app = _capture_window(x, v)                                  # Inbox is now preselected
    app.focus("Capture — Notes")
    app.type("again")
    app.key("ctrl+Return")
    assert app.proc.wait(15) == 0
    assert (v / "Inbox.md").read_text() == "- 09:30 to inbox\n- 09:30 again\n"
    app = _capture_window(x, v)
    app.focus("Capture — Notes")
    app.type("dropped")
    app.key("Escape")
    assert app.proc.wait(15) == 0
    assert (v / "Inbox.md").read_text() == "- 09:30 to inbox\n- 09:30 again\n"
    assert (v / "2026-11-03.md").read_text() == "- 09:30 first line\n  second\n"
    assert_only_changed(v, before, {"2026-11-03.md", "Inbox.md"})


def test_capture_into_an_open_note_with_unsaved_edits(x, vault):
    v, _ = vault
    _clock(x)
    _note(v, "2026-11-03.md", "start\n")
    before = tree_digest(v)
    app = gui(x, v, "2026-11-03.md")
    app.focus(title("2026-11-03"))
    app.key("ctrl+End")
    app.type("mine")
    app.wait_title(title("2026-11-03", modified=True))
    env = {**os.environ, "LCOS_NOTES_NOW": NOW}
    subprocess.run([str(build() / "lcos-notes-cli"), "capture", str(v), "cap"], check=True, env=env,
                   capture_output=True, timeout=30)
    assert (v / "2026-11-03.md").read_text() == "start\n- 09:30 cap\n"
    settle(RELOAD)
    app.wait_title(title("2026-11-03", modified=True))           # edits kept, capture added
    app.key("ctrl+s")
    wait_for(lambda: (v / "2026-11-03.md").read_text() == "start\nmine\n- 09:30 cap\n", what="merged save")
    app.wait_title(title("2026-11-03"))
    assert_only_changed(v, before, {"2026-11-03.md"})
