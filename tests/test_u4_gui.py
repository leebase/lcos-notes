"""U4 GUI: window size, reading-view margins, clicks and caret, rename caret (CONTRACT.md: U4).

Pointer tests locate text by color in a screenshot of the window (xdrive shot) and click
it (xdrive click). The colors are the contract's link colors and the code tint."""
import pytest

from harness import XSession, build, copy_vault, title, tree_digest, wait_for
from test_gui import assert_only_changed, gui, settle, vault, x  # noqa: F401  (pytest fixtures)

BLUE = (0x20, 0x5C, 0xA8)        # resolved link
RED = (0xA3, 0x3B, 0x24)         # unresolved link
TINT = (0xEE, 0xEE, 0xEA)        # code background
WHITE = (255, 255, 255)          # text view base color under the test theme (Adwaita)


def _note(v, name, text):
    (v / name).parent.mkdir(parents=True, exist_ok=True)
    (v / name).write_bytes(text.encode())
    return (v / name).read_bytes()


def _link_point(app, name, color=BLUE):
    wait_for(lambda: app.shot(title(name)).find(color, 12), what=f"{color} text on screen")
    pts = app.shot(title(name)).find(color, 12)
    # Take a pixel row in the middle of the glyphs' vertical extent, not the underline.
    ys = sorted({p[1] for p in pts})
    top = ys[0]
    rows = [y for y in ys if y - top < 20]
    y = rows[len(rows) // 3]
    xs = sorted(p[0] for p in pts if p[1] == y)
    return xs[len(xs) // 2], y


@pytest.mark.parametrize("screen", ["1024x768", "800x600", "1600x1200"])
def test_window_fits_the_screen(screen, tmp_path):
    build()
    v = copy_vault(tmp_path / "v")
    sw, sh = map(int, screen.split("x"))
    with XSession(screen=screen) as s:
        app = s.launch([str(build() / "lcos-notes"), "--vault", str(v), "Home.md"])
        app.focus(title("Home"))
        settle(0.5)
        g = app.geometry(title("Home"))
        cx, cy, cw, ch = g["client"]
        fx, fy, fw, fh = g["frame"]
        if sw >= 1200 and sh >= 780:
            assert (cw, ch) == (1100, 650), g
        assert fx >= 0 and fy >= 0 and fx + fw <= sw and fy + fh <= sh, g
        assert cw >= 640 and ch >= 480, g
        app.close(title("Home"))


def _runs(shot, y, color):
    """[start, end) x-runs of exactly this color on row y."""
    out, start = [], None
    for x in range(shot.w + 1):
        on = x < shot.w and shot.pixel(x, y) == color
        if on and start is None:
            start = x
        if not on and start is not None:
            out.append((start, x))
            start = None
    return out


def test_editor_and_backlinks_widths_at_1024(tmp_path):
    build()
    v = copy_vault(tmp_path / "v")
    with XSession() as s:
        app = s.launch([str(build() / "lcos-notes"), "--vault", str(v), "Ideas.md"])
        app.focus(title("Ideas"))
        settle(0.8)
        shot = app.shot(title("Ideas"))
        cw = app.geometry(title("Ideas"))["client"][2]
        y = shot.h // 2
        whites = [r for r in _runs(shot, y, WHITE) if r[1] - r[0] >= 40]
        # The two rightmost base-color areas on a blank row: the editor text area, then the
        # Backlinks list, which ends at the client's right edge.
        assert len(whites) >= 2, whites
        editor, backlinks = whites[-2], whites[-1]
        assert backlinks[1] - backlinks[0] >= 290, whites
        assert editor[1] - editor[0] >= 300, whites
        assert cw - backlinks[1] <= 4, (cw, whites)


def test_reading_view_has_side_margins(x, vault):
    v, before = vault
    _note(v, "Code.md", "```\n" + "x" * 400 + "\n```\n")
    app = gui(x, v, "Code.md")
    app.focus(title("Code"))
    app.key("ctrl+e")
    settle(0.8)
    shot = app.shot(title("Code"))
    tint = shot.find(TINT)
    assert tint, "code block tint not found"
    rows = sorted({p[1] for p in tint})
    y = rows[len(rows) // 4]                              # a row inside a full, wrapped line
    xs = [p[0] for p in tint if p[1] == y]
    left, right = min(xs), max(xs)

    def gap(start, step):
        """Skip the edge glyph's own pixels, then count base-color pixels up to the border."""
        x, n = start, 0
        while 0 <= x < shot.w and shot.pixel(x, y) != WHITE and n < 12:
            x, n = x + step, n + 1
        count = 0
        while 0 <= x < shot.w and shot.pixel(x, y) == WHITE:
            x, count = x + step, count + 1
        return count

    gap_left, gap_right = gap(left - 1, -1), gap(right + 1, 1)
    assert gap_left >= 10, gap_left
    assert gap_right >= 10, gap_right
    assert_only_changed(v, before, {"Code.md"})


def test_reading_view_plain_click_follows_modified_clicks_do_not(x, vault):
    v, before = vault
    _note(v, "Read.md", "plain words then [[Ideas]] here\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("ctrl+e")
    settle(0.8)
    px, py = _link_point(app, "Read")
    for mods in ("ctrl", "shift"):
        app.click(title("Read"), px, py, mods)
        settle(0.8)
        assert [w["title"] for w in app.windows()] == [title("Read")], mods
    app.key("Return")                                    # Shift+click moved the caret onto the link
    app.wait_title(title("Ideas"))
    app.key("ctrl+e")                                    # editor, then back to Read and reading again
    settle(0.5)
    app.key("ctrl+o")
    settle(0.8)
    app.type("read")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("Read"))
    app.key("ctrl+e")
    settle(0.8)
    px, py = _link_point(app, "Read")
    app.click(title("Read"), px, py)
    app.wait_title(title("Ideas"))
    assert_only_changed(v, before, {"Read.md"})


def test_editor_ctrl_click_follows_plain_click_moves_caret(x, vault):
    v, before = vault
    _note(v, "Read.md", "plain words then [[Ideas]] here\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    settle(0.8)
    px, py = _link_point(app, "Read")
    app.click(title("Read"), px, py)
    settle(0.8)
    assert [w["title"] for w in app.windows()] == [title("Read")]
    app.key("alt+Return")                                # the plain click put the caret on the link
    app.wait_title(title("Ideas"))
    app.key("ctrl+o")
    settle(0.8)
    app.type("read")
    settle(0.5)
    app.key("Return")
    app.wait_title(title("Read"))
    settle(0.8)
    px, py = _link_point(app, "Read")
    app.click(title("Read"), px, py, "ctrl")
    app.wait_title(title("Ideas"))
    assert_only_changed(v, before, {"Read.md"})


def test_editor_highlights_resolved_and_unresolved_links(x, vault):
    v, before = vault
    _note(v, "Read.md", "see [[Ideas]] only\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    wait_for(lambda: app.shot(title("Read")).find(BLUE, 12), what="resolved link color")
    assert not app.shot(title("Read")).find(RED, 12)
    app.type("[[Nowhere]] ")
    wait_for(lambda: app.shot(title("Read", modified=True)).find(RED, 12), timeout=3, what="unresolved link color")
    assert_only_changed(v, before, {"Read.md"})


def test_reading_caret_starts_at_the_editor_block(x, vault):
    v, before = vault
    filler = "".join(f"Filler {i}\n\n" for i in range(25))
    text = "---\na: b\n---\n" + filler + "[[Nav]] in the middle\nsecond line\n\n" + filler
    _note(v, "Long.md", text)
    app = gui(x, v, "Long.md")
    app.focus(title("Long"))
    app.key(*["Down"] * 54)                              # editor line 55: "second line"
    app.key("ctrl+e")
    settle(1.0)
    assert app.shot(title("Long")).find(BLUE, 12), "the link's block is scrolled into view"
    app.key("Return")                                    # reading caret at the block start: the link
    app.wait_title(title("Nav"))
    assert_only_changed(v, before, {"Long.md"})


def test_reading_caret_in_frontmatter_goes_to_text_start(x, vault):
    v, before = vault
    _note(v, "Front.md", "---\na: b\nc: d\n---\n[[Nav]] first\n\nlater\n")
    app = gui(x, v, "Front.md")
    app.focus(title("Front"))
    app.key("Down")                                      # editor line 2, inside frontmatter
    app.key("ctrl+e")
    settle(0.8)
    app.key("Return")
    app.wait_title(title("Nav"))
    assert_only_changed(v, before, {"Front.md"})


def test_heading_follow_in_reading_view_places_reading_caret(x, vault):
    v, before = vault
    filler = "".join(f"Filler {i}\n\n" for i in range(40))
    _note(v, "Long.md", filler + "## Target\n\n[[Nav]] after target\n")
    _note(v, "Read.md", "[[Long#Target]]\n")
    app = gui(x, v, "Read.md")
    app.focus(title("Read"))
    app.key("ctrl+e")
    settle(0.8)
    app.key("Return")
    app.wait_title(title("Long"))
    settle(0.8)
    app.key("Down", "Down", "Return")                    # heading, blank line, then the Nav link
    app.wait_title(title("Nav"))
    assert_only_changed(v, before, {"Long.md", "Read.md"})


def _rename(app, old, new):
    app.key("F2")
    settle(0.8)
    app.key("ctrl+a")
    app.type(new)
    settle(0.3)
    app.key("Return")
    app.wait_title(title(new))
    settle(0.5)


def test_rename_keeps_caret_on_the_same_text(x, vault):
    v, before = vault
    _note(v, "Self.md", "[[Self]] and [[Self|x]] tail\n")
    app = gui(x, v, "Self.md")
    app.focus(title("Self"))
    app.key("End", "Left", "Left", "Left", "Left")       # before "tail"; both links are before it
    _rename(app, "Self", "Selves")
    app.type("M")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Selves.md").read_bytes() == b"[[Selves]] and [[Selves|x]] Mtail\n", what="caret after links")
    app.key("Home", *["Right"] * 18)                     # inside "[[Selves|x]]" (it starts at 15)
    _rename(app, "Selves", "S")
    app.type("K")
    app.key("ctrl+s")
    wait_for(lambda: (v / "S.md").read_bytes() == b"[[S]] and K[[S|x]] Mtail\n", what="caret at link start")
    app.key("Home")                                      # at a link's start: not inside, does not move
    _rename(app, "S", "Tt")
    app.type("Q")
    app.key("ctrl+s")
    wait_for(lambda: (v / "Tt.md").read_bytes() == b"Q[[Tt]] and K[[Tt|x]] Mtail\n", what="caret before links")
    assert_only_changed(v, before, {"Self.md", "Selves.md", "S.md", "Tt.md"})
