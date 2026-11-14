"""Caller-owned native vault acceptance; see VAULT-MANAGEMENT.md.

Observe real GTK widgets, send normal XTest input, and verify bytes/config.
No application hooks, prescribed vault shortcuts, or implementation imports.
"""
import base64
import os
import re
import subprocess
import time
from pathlib import Path

import pytest
from harness import ROOT, build, tree_digest, wait_for, work_dir
from test_gui import x  # noqa: F401


def observe(x):
    so = work_dir() / 'vault-inspect.so'
    if not so.exists():
        flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gtk+-3.0'], text=True).split()
        subprocess.run(['cc', '-shared', '-fPIC', '-o', str(so), str(ROOT / 'tests/vault_inspect.c'), *flags], check=True)
    x.env['LD_PRELOAD'] = str(so)
    x.env['VAULT_INSPECT_FILE'] = str(x.home / 'vault.snapshot')
    return x.home / 'vault.snapshot'


def snap(path):
    widgets, rows = [], []
    if not path.exists():
        return widgets, rows
    dec = lambda s: base64.b64decode(s).decode()
    for line in path.read_text().splitlines():
        f = line.split('\t')
        if f[0] == 'W':
            widgets.append(dict(window=dec(f[1]), cls=dec(f[2]), x=int(f[3]), y=int(f[4]),
                                w=int(f[5]), h=int(f[6]), text=dec(f[7])))
        elif f[0] == 'R':
            rows.append(dict(window=dec(f[1]), row=dec(f[2]), values=[dec(v) for v in f[3:]]))
    return widgets, rows


def find(inspect, predicate, what):
    wait_for(lambda: any(predicate(w) for w in snap(inspect)[0]), timeout=4, what=what)
    return next(w for w in snap(inspect)[0] if predicate(w))


def main(app):
    # Normal title may include the path; dialog names are fixed by the contract.
    windows = [w for w in app.windows() if 'Notes' in w['title'] and w['title'] not in ('New Note',)]
    assert windows, f'normal Notes window missing: {app.windows()}'
    return windows[0]


def click(app, widget):
    window = main(app)
    geometry = app.geometry(window['title'])['client']
    app.s.xdrive('click', window['id'], widget['x'] + widget['w']//2 - geometry[0],
                 widget['y'] + widget['h']//2 - geometry[1])
    time.sleep(.25)


def normalized(text):
    return text.replace('_', '').replace('...', '…')


def menu(app, inspect, action):
    app.s.xdrive('activate', main(app)['id'])
    app.key('alt+f')
    target = find(inspect, lambda w: 'MenuItem' in w['cls'] and normalized(w['text']).startswith(action),
                  'File menu item ' + action)
    click(app, target)
    app.wait_title(action.rstrip('…'))


def button(app, inspect, window, label):
    w = find(inspect, lambda w: w['window'] == window and 'Button' in w['cls']
             and normalized(w['text']) == label, window + ' button ' + label)
    click(app, w)


def type_text(app, text):
    # xdrive intentionally types ASCII. GTK's normal Unicode input method covers UTF-8 paths.
    ascii_part = ''
    for ch in text:
        if ord(ch) < 128:
            ascii_part += ch
        else:
            if ascii_part:
                app.type(ascii_part); ascii_part = ''
            app.key('ctrl+shift+u'); app.type(format(ord(ch), 'x')); app.key('Return')
    if ascii_part:
        app.type(ascii_part)


def start(x, vault, note='Shared.md'):
    inspect = observe(x)
    app = x.launch([str(build() / 'lcos-notes'), '--vault', str(vault), *([note] if note else [])])
    wait_for(lambda: app.windows(), what='normal app startup')
    app.s.xdrive('activate', main(app)['id'])
    find(inspect, lambda w: is_editor(w), 'mapped editor')
    return app, inspect


def pair(tmp_path):
    a, b = tmp_path / 'A', tmp_path / 'B'
    for v, body in [(a, 'A SENTINEL\n'), (b, 'B SENTINEL\n')]:
        v.mkdir(); (v/'Shared.md').write_text(body)
        (v/'.obsidian').mkdir(); (v/'.obsidian/preferences.json').write_text('{"root":"'+v.name+'"}')
    (a/'Only A.md').write_text('A ONLY\n'); (b/'Only B.md').write_text('B ONLY\n')
    return a, b


def config(x):
    root = x.home/'.config/lcos-notes'
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def last(x):
    return (x.home/'.config/lcos-notes/last-vault').read_text().strip()


def is_editor(widget):
    return any(kind in widget['cls'] for kind in ('TextView', 'SourceView'))


def editor(inspect, text):
    return any(is_editor(w) and w['text'] == text for w in snap(inspect)[0])


def edit(app, inspect, text):
    w = find(inspect, lambda w: is_editor(w) and 'SENTINEL' in w['text'], 'sentinel editor')
    click(app, w); app.key('ctrl+a')
    for index, segment in enumerate(text.split('\n')):
        if index:
            app.key('Return')
        if segment:
            app.type(segment)
    wait_for(lambda: editor(inspect, text), what='unsaved editor text')
    wait_for(lambda: '*' in main(app)['title'], what='dirty editor marker')
    assert '*' in main(app)['title'], 'editing must mark the note dirty'


def open_vault(app, inspect, destination):
    menu(app, inspect, 'Open Vault…')
    app.focus('Open Vault'); app.key('ctrl+l'); type_text(app, str(destination)); app.key('Return')
    time.sleep(.5)
    if any(w['title'] == 'Open Vault' for w in app.windows()):
        candidates = [w for w in snap(inspect)[0] if w['window'] == 'Open Vault' and 'Button' in w['cls']
                      and normalized(w['text']) in ('Open', 'Select')]
        if candidates:
            click(app, candidates[-1])
    time.sleep(.6)


def switched(x, app, inspect, vault):
    wait_for(lambda: last(x) == str(vault.resolve()), what='selected vault config')
    wait_for(lambda: len(app.windows()) == 1, what='one normal window after switching')
    wait_for(lambda: any(str(vault.resolve()) in w['text'] or str(vault.resolve()) in w['window']
                         for w in snap(inspect)[0]), what='visible absolute current-vault path')
    assert not any(is_editor(w) and 'SENTINEL' in w['text'] for w in snap(inspect)[0]), 'old note must close'


def quick(app, inspect, query, expected):
    app.key('ctrl+o'); time.sleep(.35); app.type(query); time.sleep(.3); app.key('Return')
    wait_for(lambda: editor(inspect, expected), what='quick-switcher selected-root note')


def new_vault(app, inspect, path):
    menu(app, inspect, 'New Vault…')
    entry = find(inspect, lambda w: w['window'] == 'New Vault' and w['cls'].endswith('Entry'), 'new vault path entry')
    click(app, entry); app.key('ctrl+a', 'BackSpace'); type_text(app, str(path)); button(app, inspect, 'New Vault', 'Create')
    time.sleep(.4)


def dismiss(app):
    for _ in range(4):
        if len(app.windows()) == 1:
            return
        app.key('Escape')


def error_visible(inspect):
    # Paths include pytest test names such as persistence_failure: those are not warnings.
    # Read meaningful labels with complete words, removing path-shaped tokens first.
    messages = [re.sub(r'/[^\s]+', '[path]', w['text']) for w in snap(inspect)[0]
                if 'Label' in w['cls']]
    pattern = (r'\b(error|cannot|invalid|refused|failure|failed|could not|unable|'
               r'does not exist|already exists|changed on disk|permission denied|'
               r'not saved|must be absolute|empty|not writable|not readable|not a directory)\b')
    return any(re.search(pattern, message, re.I) for message in messages)


def select_recent(app, inspect, index):
    listing = find(inspect, lambda w: w['window'] == 'Recent Vaults'
                   and any(kind in w['cls'] for kind in ('TreeView', 'ListBox', 'IconView')),
                   'keyboard-selectable recent vault list')
    click(app, listing); app.key('Home', *(['Down'] * index))


def recent_paths(app, inspect):
    menu(app, inspect, 'Recent Vaults…')
    wait_for(lambda: any(r['window'] == 'Recent Vaults' for r in snap(inspect)[1]) or
             any(w['window'] == 'Recent Vaults' and 'Label' in w['cls'] and w['text'].startswith('/')
                 for w in snap(inspect)[0]), what='recent vault list')
    paths = []
    for row in snap(inspect)[1]:
        if row['window'] == 'Recent Vaults':
            paths.extend(v for v in row['values'] if v.startswith('/'))
    if not paths:
        paths = [w['text'] for w in sorted(snap(inspect)[0], key=lambda w: w['y'])
                 if w['window'] == 'Recent Vaults' and 'Label' in w['cls'] and w['text'].startswith('/')]
    return paths


def test_switch_isolates_equal_names_and_old_watcher_events(x, tmp_path):
    a,b = pair(tmp_path); before_a, before_b = tree_digest(a), tree_digest(b)
    app,ins = start(x,a); open_vault(app,ins,b); switched(x,app,ins,b)
    quick(app,ins,'Shared','B SENTINEL\n')
    # Exercise stale monitor delivery after a same-named B note is open.
    (a/'Shared.md').write_text('LATE OLD EVENT\n'); (a/'Late A.md').write_text('old vault only\n')
    time.sleep(1.2)
    assert editor(ins,'B SENTINEL\n')
    app.key('ctrl+Home'); app.type('B EDIT '); app.key('ctrl+s')
    wait_for(lambda: (b/'Shared.md').read_text() == 'B EDIT B SENTINEL\n', what='B save')
    assert (a/'Shared.md').read_text() == 'LATE OLD EVENT\n'
    app.key('ctrl+o'); time.sleep(.4)
    assert not any('Late A' in v or 'Only A' in v for r in snap(ins)[1] for v in r['values'])
    app.key('Escape')
    assert (a/'.obsidian/preferences.json').read_bytes() == b'{"root":"A"}'
    assert (b/'.obsidian/preferences.json').read_bytes() == b'{"root":"B"}'
    assert set(tree_digest(a)) == set(before_a) | {'Late A.md'}
    after_b=tree_digest(b)
    assert {p for p in before_b if before_b[p] != after_b[p]} == {'Shared.md'}


def test_switch_saves_dirty_source_without_writing_destination(x,tmp_path):
    a,b=pair(tmp_path); before=tree_digest(b); app,ins=start(x,a)
    edit(app,ins,'MY UNSAVED EDIT\n'); open_vault(app,ins,b); switched(x,app,ins,b)
    assert (a/'Shared.md').read_text() == 'MY UNSAVED EDIT\n'
    assert tree_digest(b) == before
    quick(app,ins,'Shared','B SENTINEL\n')
    app.key('ctrl+z'); time.sleep(.3)
    assert editor(ins,'B SENTINEL\n'), 'source undo history must not survive'


def test_external_change_refuses_switch_and_retains_dirty_text(x,tmp_path):
    a,b=pair(tmp_path); app,ins=start(x,a); edit(app,ins,'KEEP THIS UNSAVED\n')
    (a/'Shared.md').write_text('EXTERNAL AUTHOR\n'); os.utime(a/'Shared.md',(time.time()+5,)*2)
    before=config(x); open_vault(app,ins,b)
    assert error_visible(ins); dismiss(app)
    assert last(x)==str(a); assert config(x)==before
    assert editor(ins,'KEEP THIS UNSAVED\n')
    assert (a/'Shared.md').read_text()=='EXTERNAL AUTHOR\n'
    assert (b/'Shared.md').read_text()=='B SENTINEL\n'


def test_cancel_and_same_canonical_vault_preserve_dirty_editor(x,tmp_path):
    a,b=pair(tmp_path); app,ins=start(x,a); edit(app,ins,'STILL DIRTY\n'); before=config(x)
    menu(app,ins,'Open Vault…'); app.key('Escape')
    assert editor(ins,'STILL DIRTY\n'); assert config(x)==before
    alias=tmp_path/'alias'; alias.symlink_to(a,target_is_directory=True)
    open_vault(app,ins,alias)
    assert editor(ins,'STILL DIRTY\n'); assert config(x)==before
    assert (a/'Shared.md').read_text()=='A SENTINEL\n'
    assert '*' in main(app)['title'], 'same-root open must preserve dirty state'


@pytest.mark.parametrize('kind',['missing','unreadable'])
def test_invalid_open_retains_vault_text_and_config(x,tmp_path,kind):
    a,b=pair(tmp_path); target=tmp_path/'missing'
    if kind=='unreadable':
        target.mkdir(); target.chmod(0)
    app,ins=start(x,a); edit(app,ins,'RETAIN INVALID OPEN\n'); before=config(x)
    try:
        open_vault(app,ins,target)
        assert error_visible(ins); dismiss(app)
        assert editor(ins,'RETAIN INVALID OPEN\n'); assert config(x)==before; assert last(x)==str(a)
    finally:
        if target.exists(): target.chmod(0o755)


def test_create_utf8_plain_folder_then_note_and_reopen(x,tmp_path):
    a,b=pair(tmp_path); target=tmp_path/'Project café'; app,ins=start(x,a)
    new_vault(app,ins,target); switched(x,app,ins,target)
    assert list(target.iterdir())==[], 'new vault must be an empty ordinary folder'
    app.key('ctrl+n'); app.wait_title('New Note'); app.type('Fresh'); app.key('Return')
    wait_for(lambda: (target/'Fresh.md').exists(), what='note created inside new vault')
    app.type('NEW VAULT NOTE'); app.key('ctrl+s')
    wait_for(lambda: (target/'Fresh.md').read_text()=='NEW VAULT NOTE', what='new vault note saved')
    open_vault(app,ins,a); switched(x,app,ins,a)
    open_vault(app,ins,target); switched(x,app,ins,target)
    quick(app,ins,'Fresh','NEW VAULT NOTE')
    assert set(p.name for p in target.iterdir()) == {'Fresh.md'}


def test_create_invalid_and_colliding_paths_leave_everything_unchanged(x,tmp_path):
    a,b=pair(tmp_path); ordinary=tmp_path/'file'; ordinary.write_text('UNRELATED')
    symlink=tmp_path/'link'; symlink.symlink_to(b,target_is_directory=True)
    dangling=tmp_path/'dangling'; dangling.symlink_to(tmp_path/'absent',target_is_directory=True)
    paths=['','relative-vault','/',str(b),str(ordinary),str(symlink),str(dangling),str(tmp_path/'missing-parent/leaf')]
    app,ins=start(x,a); edit(app,ins,'KEEP DURING REFUSALS\n')
    original=config(x); before=tree_digest(tmp_path)
    for path in paths:
        new_vault(app,ins,path)
        assert error_visible(ins), 'useful refusal required for '+repr(path)
        dismiss(app)
        assert editor(ins,'KEEP DURING REFUSALS\n'), path
        assert config(x)==original, path
        assert tree_digest(tmp_path)==before, path
    assert not (ROOT/'relative-vault').exists()


def test_create_cancel_does_not_save_dirty_note_or_make_directory(x,tmp_path):
    a,b=pair(tmp_path); app,ins=start(x,a); edit(app,ins,'CANCELLED CREATE\n'); original=config(x)
    target=tmp_path/'never-created'; menu(app,ins,'New Vault…')
    app.type(str(target)); button(app,ins,'New Vault','Cancel')
    assert not target.exists(); assert config(x)==original; assert editor(ins,'CANCELLED CREATE\n')
    assert (a/'Shared.md').read_text()=='A SENTINEL\n'


def test_create_save_failure_leaves_no_new_directory(x,tmp_path):
    a,b=pair(tmp_path); target=tmp_path/'must-not-exist'; app,ins=start(x,a)
    edit(app,ins,'UNSAVED CONFLICT\n'); (a/'Shared.md').write_text('EXTERNAL\n')
    os.utime(a/'Shared.md',(time.time()+5,)*2); original=config(x)
    new_vault(app,ins,target)
    assert error_visible(ins); dismiss(app)
    assert not target.exists(); assert config(x)==original
    assert editor(ins,'UNSAVED CONFLICT\n'); assert (a/'Shared.md').read_text()=='EXTERNAL\n'


def test_recents_mru_dedup_persistence_and_no_argument_restart(x,tmp_path):
    a,b=pair(tmp_path); c=tmp_path/'C'; c.mkdir(); app,ins=start(x,a)
    assert recent_paths(app,ins)==[str(a)]
    button(app,ins,'Recent Vaults','Cancel')
    for dest in [b,c,b]: open_vault(app,ins,dest); switched(x,app,ins,dest)
    assert recent_paths(app,ins)==[str(b),str(c),str(a)]
    button(app,ins,'Recent Vaults','Cancel')
    app.close(main(app)['title'])
    app=x.launch([str(build()/'lcos-notes')]); wait_for(lambda: app.windows(),what='restart')
    assert last(x)==str(b)
    assert recent_paths(app,ins)==[str(b),str(c),str(a)]
    select_recent(app,ins,1); button(app,ins,'Recent Vaults','Open'); switched(x,app,ins,c)
    assert recent_paths(app,ins)==[str(c),str(b),str(a)]
    button(app,ins,'Recent Vaults','Cancel')
    assert not any(p.name in ('last-vault','recent-vaults') for v in (a,b,c) for p in v.rglob('*'))


def test_recents_cancel_and_stale_entry_preserve_survivors(x,tmp_path):
    a,b=pair(tmp_path); app,ins=start(x,a); open_vault(app,ins,b); switched(x,app,ins,b)
    quick(app,ins,'Shared','B SENTINEL\n'); edit(app,ins,'UNSAVED RECENTS\n'); original=config(x)
    assert recent_paths(app,ins)==[str(b),str(a)]
    button(app,ins,'Recent Vaults','Cancel')
    assert editor(ins,'UNSAVED RECENTS\n'); assert config(x)==original
    for p in a.rglob('*'):
        if p.is_file(): p.unlink()
    (a/'.obsidian').rmdir(); a.rmdir()
    paths=recent_paths(app,ins)
    if str(a) in paths:
        select_recent(app,ins,1); button(app,ins,'Recent Vaults','Open')
        assert error_visible(ins); dismiss(app)
    else:
        button(app,ins,'Recent Vaults','Cancel')
    assert last(x)==str(b); assert editor(ins,'UNSAVED RECENTS\n')
    assert str(b) in recent_paths(app,ins)
    button(app,ins,'Recent Vaults','Cancel')


def test_observer_drives_existing_native_file_menu_control(x,tmp_path):
    a,b=pair(tmp_path); app,ins=start(x,a)
    menu(app,ins,'New Note…'); button(app,ins,'New Note','Cancel')
    assert editor(ins,'A SENTINEL\n')


def test_recents_keeps_only_ten_most_recent_successful_startups(x,tmp_path):
    inspect=observe(x); roots=[]
    for number in range(12):
        root=tmp_path/('Vault '+str(number)); root.mkdir(); roots.append(root)
        app=x.launch([str(build()/'lcos-notes'),'--vault',str(root)])
        wait_for(lambda: app.windows(),what='explicit vault startup')
        wait_for(lambda: last(x)==str(root),what='startup recorded')
        if number<11:
            app.close(main(app)['title'])
    assert recent_paths(app,inspect)==[str(p) for p in reversed(roots[-10:])]
    button(app,inspect,'Recent Vaults','Cancel')
    assert all(list(p.iterdir())==[] for p in roots), 'history belongs outside every vault'


def test_config_persistence_failure_warns_and_preserves_notes_and_valid_config(x,tmp_path):
    a,b=pair(tmp_path); app,ins=start(x,a); edit(app,ins,'KEEP THROUGH CONFIG FAILURE\n')
    original=config(x); directory=x.home/'.config/lcos-notes'
    files=[p for p in directory.rglob('*') if p.is_file()]
    modes={p:p.stat().st_mode & 0o777 for p in files}
    for p in files: p.chmod(0o400)
    directory.chmod(0o500)
    try:
        open_vault(app,ins,b)
        assert app.proc.poll() is None
        assert error_visible(ins), 'persistence I/O failure must produce a visible warning'
        assert config(x)==original, 'valid previous selection/history must survive failed persistence'
        assert (b/'Shared.md').read_text()=='B SENTINEL\n'
        # Both refusing the switch and switching with a warning satisfy the contract.
        assert editor(ins,'KEEP THROUGH CONFIG FAILURE\n') or (a/'Shared.md').read_text()=='KEEP THROUGH CONFIG FAILURE\n'
    finally:
        directory.chmod(0o700)
        for p,mode in modes.items():
            if p.exists(): p.chmod(mode)


def test_legacy_last_vault_alias_is_canonical_and_deduplicated(x,tmp_path):
    a,b=pair(tmp_path)
    alias=tmp_path/'Project Alias'; alias.symlink_to(a,target_is_directory=True)
    directory=x.home/'.config/lcos-notes'; directory.mkdir(parents=True)
    (directory/'last-vault').write_text(str(alias)+'\n')
    app,ins=start(x,a)
    assert last(x)==str(a.resolve())
    assert recent_paths(app,ins)==[str(a.resolve())], 'legacy aliases must not duplicate the same physical vault'
    button(app,ins,'Recent Vaults','Cancel')
