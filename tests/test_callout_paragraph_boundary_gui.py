"""Paragraph ownership survives zero/one/many list prefixes; no marker grammar."""
import pytest
from harness import cli_json, title, wait_for
from test_gui import gui, settle, vault, x, assert_only_changed
from test_u4_gui import BLUE, _link_point, _note
from polish_inspect import enable, widget, lines
from test_polish_gui import COLORS, color_is


# First two sources are the actual independent-review counterexamples.
CASES = [
    ('- - ', '    ', '• • ', 'note', 'Nested first title', 'Nested body', False, False),
    ('- 1. ', '     ', '• 1. ', 'warning', 'Mixed chain title', 'Mixed body', False, False),
    ('- 1. ', '     ', '• 1. ', 'warning', 'Mixed chain title', 'Mixed body', True, False),
    ('- 2) - ', '       ', '• 2) • ', 'tip', 'Boundary é猫', 'go', True, True),
]


@pytest.mark.parametrize('marker,pad,prefix,kind,heading,body_text,folded,linked', CASES)
def test_callout_paragraph_ownership(x, vault, marker, pad, prefix, kind, heading,
                                    body_text, folded, linked):
    v, before = vault
    content = '[[Target|go]]' if linked else body_text
    source = ('Lead plain\n\n' + marker + '> [!' + kind + ']' + ('-' if folded else '') +
              ' ' + heading + '\n' + pad + '> ' + content + '\n\nAfter plain\n')
    _note(v, 'Boundary.md', source)
    if linked:
        _note(v, 'Target.md', 'Target destination\n')

    # Literal expected text constrains semantic offsets separately from GUI paint.
    text = 'Lead plain\n\n' + prefix + heading + '\n' + pad + body_text + '\n\nAfter plain'
    start = len('Lead plain\n\n' + prefix)
    title_end = start + len(heading)
    end = text.index('\n\nAfter plain')
    rendered = cli_json('render', v, 'Boundary.md')
    assert rendered['text'] == text
    spans = {(s['start'], s['end'], s['style']) for s in rendered['spans']}
    assert (start, title_end, 'callout-title') in spans
    assert (start, end, 'callout-' + kind) in spans
    assert [(s['start'], s['end']) for s in rendered['spans'] if s['style'] == 'folded'] == (
        [(title_end, end)] if folded else [])
    if linked:
        assert len(rendered['links']) == 1
        link = rendered['links'][0]
        assert (link['start'], link['end'], link['resolved']) == (
            text.index('go'), text.index('go') + 2, 'Target.md')
    else:
        assert rendered['links'] == []

    ins = enable(x)
    app = gui(x, v, 'Boundary.md')
    app.focus(title('Boundary')); app.key('ctrl+e'); settle(.7)

    def check(closed):
        reading = widget(ins, lambda w: w['cls'].endswith('GtkTextView') and
                         w['text'].startswith('Lead plain') and '> [!' not in w['text'], 'reading')
        wait_for(lambda: (body_text not in widget(ins, lambda w: w['id'] == reading['id'],
                                                'same reading')['text']) == closed,
                 what='actual body visibility')
        rows = [r for r in lines(ins) if r['id'] == reading['id'] and not r['text'].startswith('\n')]
        head = next(r for r in rows if r['text'] == prefix + heading)
        shot = app.shot(title('Boundary'))
        for px in (reading['x'] + reading['w']//2, reading['x'] + reading['w'] - 24):
            assert color_is(shot.pixel(px, head['y'] + head['h']//2), COLORS[kind]), 'owned title paragraph must fill column'
            if not closed:
                row = next(r for r in rows if r['text'] == pad + body_text)
                assert color_is(shot.pixel(px, row['y'] + row['h']//2), COLORS[kind])
            for normal in ('Lead plain', 'After plain'):
                row = next(r for r in rows if r['text'] == normal)
                assert not color_is(shot.pixel(px, row['y'] + row['h']//2), COLORS[kind]), 'neighbor must stay untinted'
        return head

    head = check(folded)
    if folded:
        app.click(title('Boundary'), head['x'] + 80, head['y'] + head['h']//2); settle(.3)
        head = check(False)
        app.click(title('Boundary'), head['x'] + 80, head['y'] + head['h']//2); settle(.3)
        head = check(True)
    if linked:
        app.click(title('Boundary'), head['x'] + 80, head['y'] + head['h']//2); settle(.3)
        check(False)
        px, py = _link_point(app, 'Boundary', BLUE)
        app.click(title('Boundary'), px, py)
        app.wait_title(title('Target'))
    assert cli_json('render', v, 'Boundary.md') == rendered
    assert_only_changed(v, before, {'Boundary.md', 'Target.md'} if linked else {'Boundary.md'})
