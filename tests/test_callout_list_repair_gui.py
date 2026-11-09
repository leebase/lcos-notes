"""D563: native regression for the independently found list/title interaction."""
import pytest
from harness import title, wait_for
from test_gui import gui, settle, vault, x, assert_only_changed
from test_u4_gui import _note
from polish_inspect import enable, widget, lines
from test_polish_gui import COLORS, color_is


CASES = [('ul', 'note', False), ('ol', 'tip', False),
         ('ul', 'warning', True), ('ol', 'danger', True),
         ('top', 'question', False), ('top', 'quote', True)]


@pytest.mark.parametrize('context,kind,folded', CASES)
def test_callout_title_body_and_fold_inside_outside_lists(x, vault, context, kind, folded):
    v, before = vault
    prefix = {'ul': '- list item\n\n', 'ol': '1. list item\n\n', 'top': ''}[context]
    indent = {'ul': '  ', 'ol': '   ', 'top': ''}[context]
    box = (indent + '> [!' + kind + ']' + ('-' if folded else '') + ' ProbeTitle\n' +
           indent + '> ProbeBody\n')
    _note(v, 'Repair.md', 'Lead plain\n\n' + prefix + box + '\nAfter plain\n')
    inspect = enable(x)
    app = gui(x, v, 'Repair.md')
    app.focus(title('Repair'))
    app.key('ctrl+e')
    settle(.7)

    def body():
        return widget(inspect, lambda w: w['cls'].endswith('GtkTextView') and
                      w['text'].startswith('Lead plain') and '> [!' not in w['text'], 'reading body')

    def row(text):
        wait_for(lambda: any(r['id'] == body()['id'] and r['text'].strip(' ') == text
                             for r in lines(inspect)), what='reading row ' + text)
        return next(r for r in lines(inspect) if r['id'] == body()['id'] and r['text'].strip(' ') == text)

    def verify(is_folded):
        wait_for(lambda: ('ProbeBody' not in body()['text']) == is_folded, what='actual fold visibility')
        b = body()
        heading = row('ProbeTitle')
        if context != 'top':
            assert heading['text'].startswith('  '), 'preserve actual list indentation'
        shot = app.shot(title('Repair'))
        px = min(shot.w - 1, b['x'] + b['w'] - 24)
        assert color_is(shot.pixel(px, heading['y'] + heading['h']//2), COLORS[kind]), 'title must fill column even after list indent'
        if not is_folded:
            content = row('ProbeBody')
            assert color_is(shot.pixel(px, content['y'] + content['h']//2), COLORS[kind]), 'body must retain same tint'
        for text in ['Lead plain', 'After plain'] + (['list item'] if context == 'ul' else []):
            if text == 'list item':
                continue  # List marker text is checked below without assuming its glyph.
            r = row(text)
            assert not color_is(shot.pixel(px, r['y'] + r['h']//2), COLORS[kind]), 'ordinary paragraph must stay untinted'
        if context != 'top':
            r = next(r for r in lines(inspect) if r['id'] == b['id'] and 'list item' in r['text'] and not r['text'].startswith('\n'))
            assert not color_is(shot.pixel(px, r['y'] + r['h']//2), COLORS[kind]), 'preceding list item must stay untinted'
        return heading

    heading = verify(folded)
    if folded:
        app.click(title('Repair'), heading['x'] + 45, heading['y'] + heading['h']//2)
        settle(.4)
        heading = verify(False)
        app.click(title('Repair'), heading['x'] + 45, heading['y'] + heading['h']//2)
        settle(.4)
        verify(True)
    assert_only_changed(v, before, {'Repair.md'})
