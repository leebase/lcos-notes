"""U10 user journeys; source bytes and destination are the assertions."""
import pytest

from harness import cli_json, title, tree_digest, wait_for
from test_gui import gui, settle, vault, x  # noqa: F401
from test_u4_gui import BLUE, _link_point, _note
from test_u7_gui import _external, RELOAD
from u10_inspect import enable, snapshot, widget


def link_point(app, window_title, rect=None):
    def pixels():
        pts = app.shot(window_title).find(BLUE, 12)
        if rect:
            pts = [(x,y) for x,y in pts if rect["x"] <= x < rect["x"]+rect["w"] and rect["y"] <= y < rect["y"]+rect["h"]]
        return pts
    wait_for(lambda: pixels(), what="blue link in specified region")
    pts = pixels(); ys = sorted({y for _,y in pts}); top = ys[0]
    ys = [y for y in ys if y-top < 20]; y = ys[len(ys)//3]
    xs = sorted(x for x,yy in pts if yy == y)
    return xs[len(xs)//2], y


def test_alias_follow_and_move_preserves_unsaved_and_link(x, vault):
    v, _ = vault
    _note(v, 'AliasTarget.md', '---\naliases: [Bright idea]\n---\nbody\n')
    _note(v, 'AliasSource.md', '[[Bright idea]]\n')
    app = gui(x, v, 'AliasSource.md')
    app.focus(title('AliasSource'))
    app.key('Right', 'alt+Return')
    app.wait_title(title('AliasTarget'))
    app.key('ctrl+End'); app.type('saved')
    app.key('F6'); app.wait_title('Move Note')
    app.type('Projects'); app.key('Return')
    app.wait_title(title('AliasTarget'))
    wait_for(lambda: (v/'Projects/AliasTarget.md').exists(), what='moved note')
    assert (v/'Projects/AliasTarget.md').read_text().endswith('body\nsaved')
    assert (v/'AliasSource.md').read_text() == '[[Bright idea]]\n'
    assert cli_json('resolve', v, 'AliasSource.md', 'Bright idea')['resolved'] == 'Projects/AliasTarget.md'


def test_outline_moves_editor_caret(x, vault):
    v, _ = vault
    _note(v, 'Outline.md', '# First\n\nSecond\n------\nbody\n')
    app = gui(x, v, 'Outline.md'); app.focus(title('Outline'))
    app.key('ctrl+shift+o', 'Down', 'Return')
    app.type('X'); app.key('ctrl+s')
    wait_for(lambda: (v/'Outline.md').read_text().startswith('# First\n\nXSecond'), what='outline editor destination')


def test_supersession_banner_follows_after_rename(x, vault):
    v, _ = vault
    _note(v, 'OldCurrency.md', '---\nsuperseded_by: "[[NewCurrency]]"\n---\nold\n')
    _note(v, 'NewCurrency.md', 'new\n')
    cli_json('rename', v, 'NewCurrency.md', 'RenamedCurrency')
    inspect = enable(x)
    app = gui(x, v, 'OldCurrency.md'); app.focus(title('OldCurrency'))
    app.key('ctrl+e'); settle(1)
    banner = widget(inspect, lambda w: w['text'] == 'Superseded by RenamedCurrency', 'supersession banner text')
    props = widget(inspect, lambda w: w['text'] == 'Properties', 'Properties heading')
    assert banner['y'] < props['y']
    px, py = link_point(app, title('OldCurrency'), banner)
    app.click(title('OldCurrency'), px, py)
    app.wait_title(title('RenamedCurrency'))


def test_properties_tag_click_opens_matching_note(x, vault):
    v, _ = vault
    _note(v, 'PropsView.md', '---\ntags: [widget-test]\n---\nplain body\n')
    _note(v, 'A Tagged.md', '---\ntags: [widget-test]\n---\nother\n')
    inspect = enable(x)
    app = gui(x, v, 'PropsView.md'); app.focus(title('PropsView'))
    app.key('ctrl+e'); settle(1)
    px, py = link_point(app, title('PropsView'))
    app.click(title('PropsView'), px, py)
    def tag_selected():
        widgets, rows = snapshot(inspect)
        return (any(w['cls'].endswith('GtkNotebook') and w['page'] == 1 for w in widgets)
                and any(r['expanded'] and any('widget-test' in v for v in r['values']) for r in rows)
                and any(r['selected'] and any('A Tagged' in v for v in r['values']) for r in rows))
    wait_for(tag_selected, what='Tags tab, expanded tag and selected note')
    app.key('Return'); app.wait_title(title('A Tagged'))


def test_archive_moves_and_refuses_collision(x, vault):
    v, _ = vault
    _note(v, 'Archivable.md', 'content\n')
    _note(v, 'ArchiveSource.md', '[[Archivable]]\n')
    app = gui(x, v, 'Archivable.md'); app.focus(title('Archivable'))
    app.key('ctrl+End'); app.type('pending')
    app.key('alt+f', 'a')
    wait_for(lambda: (v/'Archive/Archivable.md').exists(), what='archive moved note')
    assert (v/'Archive/Archivable.md').read_bytes() == b'content\npending'
    app.key('alt+f', 'a'); settle(1)
    assert not (v/'Archive/Archive/Archivable.md').exists()
    assert cli_json('resolve', v, 'ArchiveSource.md', 'Archivable')['resolved'] == 'Archive/Archivable.md'
    (v/'Archivable.md').write_text('collision source\n')
    before = (v/'Archive/Archivable.md').read_bytes()
    app.key('ctrl+o'); app.type('Archivable'); app.key('Return')
    app.wait_title(title('Archivable'))
    app.key('ctrl+End'); app.type('ROOT'); app.key('ctrl+s')
    wait_for(lambda: (v/'Archivable.md').read_bytes() == b'collision source\nROOT', what='root note is open')
    app.key('alt+f', 'a'); settle(1)
    assert (v/'Archive/Archivable.md').read_bytes() == before
    assert (v/'Archivable.md').read_bytes() == b'collision source\nROOT'


def test_outline_scrolls_reading_view(x, vault):
    v, _ = vault
    _note(v, 'MiddleTarget.md', 'target\n')
    _note(v, 'LongOutline.md', '# Beginning\n\n' + ('ordinary line\n\n' * 70) + '# Destination\n\n[[MiddleTarget]]\n\n' + ('later content\n\n' * 70) + '# End\n')
    inspect = enable(x)
    app = gui(x, v, 'LongOutline.md'); app.focus(title('LongOutline'))
    app.key('ctrl+Home', 'End'); app.type(' changed'); settle(0.6)
    app.key('ctrl+e', 'ctrl+shift+o'); settle(1)
    # Verify live outline refresh before navigating to the middle destination.
    wait_for(lambda: any(any('Beginning changed' in v for v in row['values']) for row in snapshot(inspect)[1]), what='refreshed outline heading')
    body = widget(inspect, lambda w: w['cls'].endswith('GtkTextView') and 'MiddleTarget' in w['text'], 'reading body')
    def blue_in_body():
        return [(px,py) for px,py in app.shot(title('LongOutline', modified=True)).find(BLUE,12)
                if body['x'] <= px < body['x']+body['w'] and body['y'] <= py < body['y']+body['h']]
    assert not blue_in_body()
    app.key('Down', 'Return'); settle(1)
    wait_for(blue_in_body, what='middle destination link visible in reading body')
    px, py = link_point(app, title('LongOutline', modified=True), body)
    app.click(title('LongOutline', modified=True), px, py)
    app.wait_title(title('MiddleTarget'))
    assert (v/'LongOutline.md').read_text().startswith('# Beginning changed\n')


def test_supersede_dialog_writes_reciprocal_metadata(x, vault):
    v, _ = vault
    _note(v, 'Was.md', 'old\n'); _note(v, 'Now.md', 'new\n')
    app = gui(x, v, 'Was.md'); app.focus(title('Was'))
    app.key('ctrl+End'); app.type('pending')
    app.key('alt+f', 'u'); app.wait_title('Supersede With')
    app.type('Now.md'); app.key('Return')
    wait_for(lambda: ((v/'Was.md').read_bytes() == b'---\nsuperseded_by: "[[Now]]"\n---\nold\npending'
                      and (v/'Now.md').read_bytes() == b'---\nsupersedes: "[[Was]]"\n---\nnew\n'),
             what='reciprocal metadata and pending text')
    assert (v/'Now.md').read_bytes() == b'---\nsupersedes: "[[Was]]"\n---\nnew\n'


def test_properties_alias_click_saves_and_reopens_owner(x, vault):
    v, _ = vault
    _note(v, 'Owner.md', '---\naliases: [Unique Phrase]\n---\nbody\n')
    app = gui(x, v, 'Owner.md'); app.focus(title('Owner'))
    app.key('ctrl+End'); app.type('edit')
    app.wait_title(title('Owner', modified=True))
    app.key('ctrl+e'); settle(1)
    wait_for(lambda: app.shot(title('Owner', modified=True)).find(BLUE, 12), what='linked alias property')
    px, py = link_point(app, title('Owner', modified=True))
    app.click(title('Owner', modified=True), px, py)
    app.wait_title(title('Owner'))
    assert (v/'Owner.md').read_text().endswith('body\nedit')


@pytest.mark.parametrize('action', ['move', 'archive', 'supersede'])
def test_organization_refuses_conflicted_unsaved_buffer(x, vault, action):
    v, _ = vault
    _note(v, 'Conflict.md', 'original\n'); _note(v, 'Replacement.md', 'replacement\n')
    inspect = enable(x)
    app = gui(x, v, 'Conflict.md'); app.focus(title('Conflict'))
    app.key('ctrl+End'); app.type('MY EDIT')
    app.wait_title(title('Conflict', modified=True))
    _external(v/'Conflict.md', 'external\n'); settle(RELOAD)
    before = tree_digest(v)
    if action == 'move':
        app.key('F6'); app.wait_title('Move Note'); app.type('Projects'); app.key('Return')
    elif action == 'archive':
        app.key('alt+f', 'a')
    else:
        app.key('alt+f', 'u'); app.wait_title('Supersede With'); app.type('Replacement.md'); app.key('Return')
    app.wait_title(title('Conflict', modified=True)); settle(1)
    assert tree_digest(v) == before
    wait_for(lambda: any('MY EDIT' in w['text'] for w in snapshot(inspect)[0]), what='unsaved buffer preserved')
    message = action.capitalize() + ' refused: Changed on disk; not saved'
    wait_for(lambda: any(w['text'] == message for w in snapshot(inspect)[0]), what='action save refusal visible')
