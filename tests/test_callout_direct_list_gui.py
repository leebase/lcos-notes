"""D563: a list item whose first child is a callout has a marker prefix."""
import pytest
from harness import title, wait_for
from test_gui import gui, settle, vault, x, assert_only_changed
from test_u4_gui import _note
from polish_inspect import enable, widget, lines
from test_polish_gui import COLORS, color_is


@pytest.mark.parametrize('marker,indent,folded', [('- ', '  ', False), ('3) ', '   ', True)])
def test_direct_list_marker_callout_title(x, vault, marker, indent, folded):
    v, before = vault
    _note(v, 'Direct.md', 'Lead plain\n\n' + marker + '> [!note]' + ('-' if folded else '') +
          ' Direct title\n' + indent + '> Direct body\n\nAfter plain\n')
    ins = enable(x)
    app = gui(x, v, 'Direct.md');app.focus(title('Direct'));app.key('ctrl+e');settle(.7)
    def check(closed):
        body = widget(ins, lambda w:w['cls'].endswith('GtkTextView') and w['text'].startswith('Lead plain') and '> [!' not in w['text'], 'direct callout reading')
        wait_for(lambda:('Direct body' not in widget(ins, lambda w:w['id']==body['id'], 'same body')['text'])==closed, what='direct fold state')
        rows=[r for r in lines(ins) if r['id']==body['id'] and not r['text'].startswith('\n')]
        heading=next(r for r in rows if r['text'].endswith('Direct title'))
        shot=app.shot(title('Direct'));px=body['x']+body['w']-24
        assert color_is(shot.pixel(px,heading['y']+heading['h']//2),COLORS['note']), 'title after actual list marker must fill column'
        if not closed:
            content=next(r for r in rows if r['text'].strip(' ')=='Direct body')
            assert color_is(shot.pixel(px,content['y']+content['h']//2),COLORS['note'])
        for text in ['Lead plain','After plain']:
            row=next(r for r in rows if r['text']==text)
            assert not color_is(shot.pixel(px,row['y']+row['h']//2),COLORS['note'])
        return heading
    heading=check(folded)
    if folded:
        app.click(title('Direct'),heading['x']+50,heading['y']+heading['h']//2);settle(.3);heading=check(False)
        app.click(title('Direct'),heading['x']+50,heading['y']+heading['h']//2);settle(.3);check(True)
    assert_only_changed(v,before,{'Direct.md'})
