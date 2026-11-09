"""Narrow GTK snapshot for visible labels, reading geometry and tree selection."""
import base64
import os
import subprocess

from harness import work_dir, wait_for


def enable(x):
    so = work_dir() / 'polish-inspect.so'
    if not so.exists():
        flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gtk+-3.0'], text=True).split()
        source = os.path.join(os.path.dirname(__file__), 'polish_inspect.c')
        subprocess.run(['cc', '-shared', '-fPIC', '-o', str(so), source, *flags], check=True)
    path = x.home / 'widgets.snapshot'
    x.env['LD_PRELOAD'] = str(so)
    x.env['U10_INSPECT_FILE'] = str(path)
    return path


def snapshot(path):
    if not path.exists():
        return [], []
    widgets, rows = [], []
    for line in path.read_text().splitlines():
        f = line.split('\t')
        if f[0] == 'W':
            widgets.append(dict(id=f[1], cls=f[2], x=int(f[3]), y=int(f[4]), w=int(f[5]), h=int(f[6]),
                                text=base64.b64decode(f[7]).decode(), page=int(f[8]) if len(f)>8 else None))
        elif f[0] == 'ROW':
            rows.append(dict(id=f[1], selected=f[2]=='1', expanded=f[3]=='1',
                             values=[base64.b64decode(a).decode() for a in f[4:]]))
    return widgets, rows


def widget(path, predicate, what):
    wait_for(lambda: any(predicate(w) for w in snapshot(path)[0]), what=what)
    return next(w for w in snapshot(path)[0] if predicate(w))


def lines(path):
    result=[]
    if path.exists():
        for line in path.read_text().splitlines():
            f=line.split('\t')
            if f[0]=='LINE':
                result.append(dict(id=f[1],x=int(f[2]),y=int(f[3]),h=int(f[4]),text=base64.b64decode(f[5]).decode()))
    return result


def labels(path):
    result=[]
    if path.exists():
        for line in path.read_text().splitlines():
            f=line.split('\t')
            if f[0]=='LABEL':
                result.append(dict(x=int(f[1]),y=int(f[2]),w=int(f[3]),text=base64.b64decode(f[4]).decode()))
    return result
