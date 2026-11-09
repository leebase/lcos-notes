"""Native rendered geometry: full column, bounded background, live label ink."""
import pytest
import ctypes
from harness import title,wait_for
from test_gui import gui,settle,vault,x,assert_only_changed
from test_u4_gui import _note
from polish_inspect import enable,widget,lines,labels

COLORS={"note":(0xE3,0xEE,0xFB),"tip":(0xE2,0xF5,0xE7),"warning":(0xFF,0xF1,0xD6),
        "danger":(0xFB,0xE2,0xE2),"question":(0xEF,0xE6,0xFA),"quote":(0xEE,0xEE,0xEE)}


def line_for(inspect,body,text):
    wait_for(lambda:any(r['id']==body['id'] and r['text']==text for r in lines(inspect)),what='rendered line '+text)
    return next(r for r in lines(inspect) if r['id']==body['id'] and r['text']==text)


def color_is(pixel,color):
    return all(abs(a-b)<=2 for a,b in zip(pixel,color))


def check_box(app,name,inspect,color):
    body=widget(inspect,lambda w:w['cls'].endswith('GtkTextView') and w['text'].startswith('Before\n\nHint'),'reading body')
    assert body['w']>180
    shot=app.shot(title(name))
    hint=line_for(inspect,body,'Hint');after=line_for(inspect,body,'After')
    # At the far right of this actual text view, independently of text width.
    px=min(shot.w-1,body['x']+body['w']-24)
    assert color_is(shot.pixel(px,hint['y']+hint['h']//2),color),'short callout must fill reading column'
    assert not color_is(shot.pixel(px,after['y']+after['h']//2),color),'ordinary following paragraph must not be tinted'
    return body['w']


@pytest.mark.parametrize('kind',list(COLORS))
def test_callout_full_width_and_bounded_background(x,vault,kind):
    v,before=vault
    _note(v,'Box.md','Before\n\n> [!'+kind+'] Hint\n> short body\n\nAfter\n')
    inspect=enable(x);app=gui(x,v,'Box.md');app.focus(title('Box'));app.key('ctrl+e');settle(1)
    check_box(app,'Box',inspect,COLORS[kind])
    if kind=='tip':
        widths=[]
        lib=ctypes.CDLL('libX11.so.6');lib.XOpenDisplay.restype=ctypes.c_void_p
        lib.XOpenDisplay.argtypes=[ctypes.c_char_p]
        lib.XResizeWindow.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_uint,ctypes.c_uint]
        lib.XSync.argtypes=[ctypes.c_void_p,ctypes.c_int];lib.XCloseDisplay.argtypes=[ctypes.c_void_p]
        display=lib.XOpenDisplay(x.display.encode());assert display
        try:
            for target_width in (800,960):
                window=app.wait_title(title('Box'))
                lib.XResizeWindow(display,int(window['id']),target_width,600);lib.XSync(display,0)
                wait_for(lambda:app.geometry(title('Box'))['client'][2]==target_width,what='actual resized width')
                settle(0.5);widths.append(check_box(app,'Box',inspect,COLORS[kind]))
        finally:
            lib.XCloseDisplay(display)
        assert abs(widths[1]-widths[0])>=40,'test must observe real reading-column reflow' 
    assert_only_changed(v,before,{'Box.md'})


def test_nested_callout_uses_inner_color_and_restores_outer(x,vault):
    v,before=vault
    _note(v,'Nested.md','Before\n\n> [!note] Outer\n> outer body\n>\n> > [!tip] Inner\n> > inner body\n>\n> outer tail\n\nAfter\n')
    inspect=enable(x);app=gui(x,v,'Nested.md');app.focus(title('Nested'));app.key('ctrl+e');settle(1)
    body=widget(inspect,lambda w:w['cls'].endswith('GtkTextView') and 'outer tail' in w['text'],'nested reading body')
    shot=app.shot(title('Nested'));px=min(shot.w-1,body['x']+body['w']-24)
    for text,kind in [('Outer','note'),('Inner','tip'),('outer tail','note')]:
        row=line_for(inspect,body,text)
        assert color_is(shot.pixel(px,row['y']+row['h']//2),COLORS[kind]),text
    after=line_for(inspect,body,'After')
    assert not color_is(shot.pixel(px,after['y']+after['h']//2),COLORS['note'])
    assert_only_changed(v,before,{'Nested.md'})


def test_new_note_template_and_name_labels_align_left(x,vault):
    v,before=vault;inspect=enable(x);app=gui(x,v,'Home.md');app.focus(title('Home'));app.key('ctrl+n');app.wait_title('New Note');settle(0.5)
    want={'Template:','Name or path, for example Projects/Idea'}
    wait_for(lambda:want<={r['text'] for r in labels(inspect)},what='both dialog labels')
    rows=[r for r in labels(inspect) if r['text'] in want]
    assert len(rows)==2
    assert abs(rows[0]['x']-rows[1]['x'])<=4,'actual label ink must share left edge'
    app.key('Escape');assert_only_changed(v,before,set())
