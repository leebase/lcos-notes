"""U8 GUI: highlight and callout colors, folding, images, embeds following their source,
Edit > Highlight and the Highlights dialog (CONTRACT.md: U8). Colors are the contract's."""
import os
import struct
import zlib

from harness import title, wait_for
from test_gui import assert_only_changed, gui, settle, vault, x  # noqa: F401  (pytest fixtures)
from test_u4_gui import BLUE, RED, _link_point, _note

HIGHLIGHT = (0xFF, 0xE0, 0x66)
NOTE = (0xE3, 0xEE, 0xFB)
TIP = (0xE2, 0xF5, 0xE7)
PURE_RED = (0xFF, 0x00, 0x00)
RELOAD = 3.0


def _png(path, w, h, rgb):
    """A plain RGB PNG, written without any imaging library."""
    rows = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    return path.read_bytes()


def _reading(app, name):
    app.focus(title(name))
    app.key("ctrl+e")
    settle(0.8)


def _has(app, name, color, n=1):
    return len(app.shot(title(name)).find(color, 2)) >= n


def test_highlight_and_callout_colors(x, vault):
    v, before = vault
    _note(v, "Col.md", "Some ==marked== words.\n\n> [!tip] Hint\n> body\n")
    app = gui(x, v, "Col.md")
    _reading(app, "Col")
    wait_for(lambda: _has(app, "Col", HIGHLIGHT, 20), what="highlight background")
    wait_for(lambda: _has(app, "Col", TIP, 200), what="tip callout background")
    assert_only_changed(v, before, {"Col.md"})


def test_folded_callout_opens_and_closes_on_title_click(x, vault):
    v, before = vault
    _note(v, "Fold.md", "Intro.\n\n> [!note]- Click me\n> ==secret== body\n")
    app = gui(x, v, "Fold.md")
    _reading(app, "Fold")
    wait_for(lambda: _has(app, "Fold", NOTE, 100), what="folded callout title")
    assert not _has(app, "Fold", HIGHLIGHT)                      # the body is hidden
    pts = app.shot(title("Fold")).find(NOTE, 2)
    tx, ty = min(p[0] for p in pts) + 40, min(p[1] for p in pts) + 6
    app.click(title("Fold"), tx, ty)
    wait_for(lambda: _has(app, "Fold", HIGHLIGHT, 20), what="body shown after a click on the title")
    app.click(title("Fold"), tx, ty)
    wait_for(lambda: not _has(app, "Fold", HIGHLIGHT), what="body hidden after a second click")
    assert_only_changed(v, before, {"Fold.md"})


def test_image_embeds_show_the_image_or_a_marker(x, vault):
    v, before = vault
    _png(v / "red.png", 40, 30, PURE_RED)
    (v / "bad.png").write_bytes(b"not an image")
    _note(v, "Pic.md", "Before\n\n![[red.png]]\n\n![[bad.png]]\n")
    app = gui(x, v, "Pic.md")
    _reading(app, "Pic")
    wait_for(lambda: _has(app, "Pic", PURE_RED, 40 * 30 - 80), what="the 40x30 image drawn at full size")
    wait_for(lambda: app.shot(title("Pic")).find(RED, 12), what="[image: bad.png] in the unresolved color")
    assert_only_changed(v, before, {"Pic.md", "red.png", "bad.png"})


def test_embedded_note_follows_its_source_and_its_links_work(x, vault):
    v, before = vault
    _note(v, "Far.md", "far away\n")
    _note(v, "Src.md", "plain text [[Far]]\n")
    _note(v, "Host.md", "Host top\n\n![[Src]]\n")
    app = gui(x, v, "Host.md")
    _reading(app, "Host")
    wait_for(lambda: app.shot(title("Host")).find(BLUE, 12), what="embedded link")
    assert not _has(app, "Host", HIGHLIGHT)
    tmp = v / "Src.md.ext~"
    tmp.write_bytes(b"plain text [[Far]] ==new==\n")
    os.replace(tmp, v / "Src.md")                                # another program changes the source
    wait_for(lambda: _has(app, "Host", HIGHLIGHT, 20), timeout=RELOAD + 2, what="embed re-rendered")
    px, py = _link_point(app, "Host", BLUE)
    app.click(title("Host"), px, py)
    app.wait_title(title("Far"))
    assert_only_changed(v, before, {"Far.md", "Src.md", "Host.md"})


def test_edit_highlight_wraps_and_unwraps_the_selection(x, vault):
    v, before = vault
    _note(v, "W.md", "word rest\n")
    app = gui(x, v, "W.md")
    app.focus(title("W"))
    app.key("ctrl+Home", "ctrl+shift+Right")                    # select "word"
    app.key("ctrl+shift+h")
    app.key("ctrl+s")
    wait_for(lambda: (v / "W.md").read_text() == "==word== rest\n", what="wrapped")
    app.key("ctrl+shift+h")                                      # same text still selected: unwrap
    app.key("ctrl+s")
    wait_for(lambda: (v / "W.md").read_text() == "word rest\n", what="unwrapped")
    app.key("ctrl+End", "Up", "End")                             # no selection: ==|==
    app.key("ctrl+shift+h")
    app.type("x")
    app.key("ctrl+s")
    wait_for(lambda: (v / "W.md").read_text() == "word rest==x==\n", what="empty pair, caret inside")
    app.key("ctrl+z", "ctrl+z")                                  # the typed x, then the one-step pair
    app.key("ctrl+s")
    wait_for(lambda: (v / "W.md").read_text() == "word rest\n", what="pair undone in one step")
    assert_only_changed(v, before, {"W.md"})


def test_highlights_dialog_jumps_to_a_highlight(x, vault):
    v, before = vault
    _note(v, "Far.md", "far\n")
    _note(v, "Hl.md", "==first== words\n\nmiddle\n\n==[[Far]]==\n")
    _note(v, "None.md", "nothing marked\n")
    app = gui(x, v, "Hl.md")
    app.focus(title("Hl"))
    app.key("ctrl+shift+y")
    app.wait_title("Highlights")
    app.key("Return")                                            # first row: plain text
    settle(0.8)
    app.key("Return")                                            # Enter on plain text does nothing
    settle(0.8)
    app.wait_title(title("Hl"))
    app.key("ctrl+shift+y")
    app.wait_title("Highlights")
    app.key("Down", "Return")                                    # second row: the link's start
    settle(0.8)
    app.key("Return")                                            # reading caret on the link
    app.wait_title(title("Far"))
    app.key("ctrl+o")
    settle(0.8)
    app.type("None")
    app.key("Return")
    app.wait_title(title("None"))
    app.key("ctrl+shift+y")
    app.wait_title("Highlights")                                 # empty list, still opens
    app.key("Escape")
    wait_for(lambda: not [w for w in app.windows() if w["title"] == "Highlights"], what="dialog closed")
    assert_only_changed(v, before, {"Far.md", "Hl.md", "None.md"})
