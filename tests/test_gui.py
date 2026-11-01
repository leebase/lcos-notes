"""GUI behavior under Xvfb + xfwm4, driven through XTest (CONTRACT.md: GUI behavior)."""
import os
import time
from pathlib import Path

import pytest

from harness import XSession, build, copy_vault, title, tree_digest, wait_for


@pytest.fixture
def vault(tmp_path):
    v = copy_vault(tmp_path / "v")
    return v, tree_digest(v)


@pytest.fixture
def x():
    build()
    with XSession() as session:
        yield session


def gui(x, v, note=None):
    exe = build() / "lcos-notes"
    return x.launch([str(exe), "--vault", str(v), *([note] if note else [])])


def assert_only_changed(v, before, allowed):
    after = tree_digest(v)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed <= set(allowed), f"unexpected vault changes: {sorted(changed - set(allowed))}"
    for k, digest in before.items():
        if k.startswith((".obsidian", ".trash")):
            assert after.get(k) == digest, k


def settle(seconds=1.2):
    time.sleep(seconds)


def test_window_chrome_titles_and_last_vault(x, vault):
    v, before = vault
    app = gui(x, v, "Home.md")
    row = app.focus(title("Home"))
    assert row["frame"] is True, "window manager must draw the title bar"
    assert row["csd"] is False, "no client-side decorations / HeaderBar"
    app.close(title("Home"))
    assert app.proc.returncode == 0
    again = x.launch([str(build() / "lcos-notes")])     # no --vault: last vault, no note
    again.wait_title(title("v"))
    again.close(title("v"))
    assert_only_changed(v, before, set())


def test_follow_heading_case_insensitive_first_match(x, vault):
    v, before = vault
    app = gui(x, v, "Nav.md")
    app.focus(title("Nav"))
    app.key("Right", "Right", "alt+Return")             # caret inside [[Projects/Alpha#plan]]
    app.wait_title(title("Alpha"))
    app.type("ZZ")
    app.wait_title(title("Alpha", modified=True))
    app.key("ctrl+s")
    app.wait_title(title("Alpha"))
    lines = (v / "Projects" / "Alpha.md").read_text().split("\n")
    assert lines[4] == "ZZ## Plan"
    assert lines[8] == "## Plan"
    assert lines[0] == "# Alpha"
    assert_only_changed(v, before, {"Projects/Alpha.md"})


def test_follow_ambiguous_link_uses_core_resolution(x, vault):
    v, before = vault
    sub = (v / "Projects" / "Sub" / "Deep.md").read_bytes()
    app = gui(x, v, "Nav.md")
    app.focus(title("Nav"))
    app.key("Down", "Right", "Right", "alt+Return")     # [[Deep]] from the vault root
    app.wait_title(title("Deep"))
    app.type("Q")
    app.key("ctrl+s")
    app.wait_title(title("Deep"))
    wait_for(lambda: (v / "Archive" / "2025" / "Deep.md").read_bytes().startswith(b"Q# Deep (archive)"),
             what="archive Deep saved")
    assert (v / "Projects" / "Sub" / "Deep.md").read_bytes() == sub
    assert_only_changed(v, before, {"Archive/2025/Deep.md"})


def test_follow_unresolved_creates_and_attachment_does_not(x, vault):
    v, before = vault
    app = gui(x, v, "Nav.md")
    app.focus(title("Nav"))
    app.key("Down", "Down", "Down", "Right", "Right", "alt+Return")   # [[images/diagram.png]]
    settle()
    assert [w["title"] for w in app.windows()] == [title("Nav")]
    assert tree_digest(v) == before
    app.key("ctrl+Home", "Down", "Down", "Right", "Right", "alt+Return")   # [[Brand New]]
    app.wait_title(title("Brand New"))
    wait_for(lambda: (v / "Brand New.md").exists(), what="Brand New.md created")
    assert (v / "Brand New.md").read_bytes() == b""
    assert_only_changed(v, before, {"Brand New.md"})


def test_quick_switcher_open_escape_create(x, vault):
    v, before = vault
    app = gui(x, v, "Home.md")
    app.focus(title("Home"))
    app.key("ctrl+o")
    settle(0.8)
    app.type("alph")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("Alpha"))
    app.key("ctrl+o")
    settle(0.8)
    app.type("ideas")
    settle(0.5)
    app.key("Escape")
    settle()
    assert [w["title"] for w in app.windows()] == [title("Alpha")]
    app.key("ctrl+o")
    settle(0.8)
    app.type("zzq new")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("zzq new"))
    assert (v / "zzq new.md").read_bytes() == b""
    assert_only_changed(v, before, {"zzq new.md"})


def test_save_writes_exact_bytes_and_skips_unmodified(x, vault):
    v, before = vault
    note = v / "Notes CRLF.md"
    original = note.read_bytes()
    os.utime(note, (1_000_000_000, 1_000_000_000))
    app = gui(x, v, "Notes CRLF.md")
    app.focus(title("Notes CRLF"))
    app.key("ctrl+s")
    settle()
    assert note.read_bytes() == original
    assert note.stat().st_mtime == 1_000_000_000, "saving an unmodified note must not write"
    app.type("X")
    app.wait_title(title("Notes CRLF", modified=True))
    app.key("ctrl+s")
    app.wait_title(title("Notes CRLF"))
    wait_for(lambda: note.read_bytes() == b"X" + original, what="exact saved bytes")
    assert_only_changed(v, before, {"Notes CRLF.md"})


def test_changed_on_disk_is_never_overwritten(x, vault):
    v, before = vault
    note = v / "Ideas.md"
    app = gui(x, v, "Ideas.md")
    app.focus(title("Ideas"))
    settle(0.5)
    note.write_bytes(b"EXTERNAL\n")
    future = time.time() + 5
    os.utime(note, (future, future))
    app.type("Y")
    app.wait_title(title("Ideas", modified=True))
    app.key("ctrl+s")
    settle()
    assert note.read_bytes() == b"EXTERNAL\n"
    app.wait_title(title("Ideas", modified=True))
    app.key("ctrl+o")                                    # switching must not drop or write the text
    settle(0.8)
    app.type("home")
    settle(0.5)
    app.key("Return")
    settle()
    assert note.read_bytes() == b"EXTERNAL\n"
    app.wait_title(title("Ideas", modified=True))
    # Closing asks before discarding; Escape cancels and keeps the window.
    main = app.wait_title(title("Ideas", modified=True))
    x.xdrive("close", main["id"])
    wait_for(lambda: len(app.windows()) == 2, what="discard dialog")
    app.key("Escape")
    settle()
    assert app.proc.poll() is None
    assert [w["title"] for w in app.windows()] == [title("Ideas", modified=True)]
    assert note.read_bytes() == b"EXTERNAL\n"
    assert_only_changed(v, before, {"Ideas.md"})


def test_autosave_on_switch_and_close(x, vault):
    v, before = vault
    app = gui(x, v, "Ideas.md")
    app.focus(title("Ideas"))
    app.type("W")
    app.wait_title(title("Ideas", modified=True))
    app.key("ctrl+o")
    settle(0.8)
    app.type("home")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("Home"))
    assert (v / "Ideas.md").read_bytes().startswith(b"W# Ideas")
    app.type("V")
    app.wait_title(title("Home", modified=True))
    app.close(title("Home", modified=True))
    assert app.proc.returncode == 0
    assert (v / "Home.md").read_bytes().startswith(b"V# Home")
    assert_only_changed(v, before, {"Ideas.md", "Home.md"})


def test_undo_never_crosses_a_note_load(x, vault):
    v, before = vault
    home, ideas = (v / "Home.md").read_bytes(), (v / "Ideas.md").read_bytes()
    app = gui(x, v, "Ideas.md")
    app.focus(title("Ideas"))
    app.key("ctrl+z", "ctrl+z")                          # undo right after the first load
    settle(0.8)
    assert [w["title"] for w in app.windows()] == [title("Ideas")]
    app.type("W")                                        # a real edit, then switch notes
    app.wait_title(title("Ideas", modified=True))
    app.key("ctrl+o")
    settle(0.8)
    app.type("home")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("Home"))
    app.key("ctrl+z", "ctrl+z", "ctrl+z")                # must not blank Home or replay Ideas
    settle(0.8)
    assert [w["title"] for w in app.windows()] == [title("Home")]
    app.key("ctrl+o")                                    # switching away autosaves if modified
    settle(0.8)
    app.type("nav")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("Nav"))
    assert (v / "Home.md").read_bytes() == home
    assert (v / "Ideas.md").read_bytes() == b"W" + ideas
    app.close(title("Nav"))
    assert (v / "Home.md").read_bytes() == home
    assert_only_changed(v, before, {"Ideas.md"})
