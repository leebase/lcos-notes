"""U10 owner acceptance: concrete examples independent of product parser."""
import json
import shutil
from pathlib import Path

from harness import cli, cli_json, tree_digest


def put(v, name, data):
    p = v / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data.encode())


def result(*args):
    p = cli(*args, check=False)
    assert p.returncode == 0, (p.returncode, p.stderr.decode())
    return json.loads(p.stdout)


def test_alias_precedence_ambiguity_rename_and_mentions(tmp_path):
    v = tmp_path / 'v'; v.mkdir()
    line = '[[First idea]] and First idea. `First idea` First ideas First dream.'
    put(v, 'Source.md', line + '\n')
    put(v, 'Alpha.md', '---\naliases: [First idea, First dream, FIRST IDEA, Shared, Café, manual.pdf]\n---\nAlpha\n')
    put(v, 'Beta.md', '---\nalias: Shared\n---\nBeta\n')
    put(v, 'Firsthand.md', 'competitor\n')
    put(v, 'Taken.md', 'real name\n')
    put(v, 'Other.md', '---\nalias: Taken\n---\n')
    (v/'manual.pdf').write_bytes(b'attachment')
    assert result('aliases', v) == [
        *[{'alias': a, 'path':'Alpha.md'} for a in ('First idea', 'First dream', 'Shared', 'Café', 'manual.pdf')],
        {'alias':'Shared', 'path':'Beta.md'}, {'alias':'Taken', 'path':'Other.md'}]
    assert result('resolve', v, 'Source.md', 'First idea')['via'] == 'alias'
    assert result('resolve', v, 'Source.md', 'Cafe\u0301')['resolved'] == 'Alpha.md'
    assert result('resolve', v, 'Source.md', 'Taken') == {'target':'Taken', 'heading':None, 'alias':None, 'resolved':'Taken.md'}
    assert result('resolve', v, 'Source.md', 'Shared')['resolved'] is None
    assert result('resolve', v, 'Source.md', 'folder/First idea')['resolved'] is None
    assert result('resolve', v, 'Source.md', 'manual.pdf')['resolved'] == 'manual.pdf'
    before = tree_digest(v)
    assert result('create', v, 'First idea') == {'path':'Alpha.md', 'created':False}
    assert tree_digest(v) == before
    assert result('switch', v, 'First') == ['Alpha.md', 'Firsthand.md']
    assert result('mentions', v, 'Alpha.md') == [
        {'source':'Source.md','line':1,'col':20,'text':line},
        {'source':'Source.md','line':1,'col':line.index('First dream')+1,'text':line}]
    source = (v / 'Source.md').read_bytes()
    result('rename', v, 'Alpha.md', 'Folder/Alpha')
    assert (v / 'Source.md').read_bytes() == source
    assert result('resolve', v, 'Source.md', 'First idea')['resolved'] == 'Folder/Alpha.md'


def test_properties_and_headings_exact(tmp_path):
    v = tmp_path / 'v'; v.mkdir()
    put(v, 'Doc.md', '---\nstatus: old\ntags: [one, "two words"]\nsource:\n  - first\n  - second\nstatus: active\nmap: {x: y}\n---\nbody\n')
    props = result('props', v, 'Doc.md')
    assert list(props) == ['tags','source','status','map']
    assert props == {'tags':['one','two words'], 'source':['first','second'], 'status':'active', 'map':' {x: y}'}
    put(v, 'Raw.md', '---\nraw: outer\n  nested: yes\nempty:\nquoted: "two words"\ncomma: ["a,b", c]\nitems: []\n---\n')
    assert result('props', v, 'Raw.md') == {'raw':' outer\n  nested: yes','empty':'','quoted':'two words', 'comma':['"a','b"','c'], 'items':[]}
    put(v, 'Empty.md', '---\n---\nbody\n')
    assert result('props', v, 'Empty.md') == {}


def test_supersede_preserves_unrelated_bytes_and_prevalidates(tmp_path):
    v = tmp_path / 'v'; v.mkdir()
    old = '---\r\ntitle: old\r\nsuperseded_by: "[[Prior]]"\r\n---\r\nbody\r\n'
    new = '---\nkind: current\n---\nnew body\n'
    put(v, 'Old.md', old); put(v, 'Dir/New.md', new)
    assert result('supersede', v, 'Old.md', 'Dir/New.md') == {'old':'Old.md', 'new':'Dir/New.md'}
    assert (v/'Old.md').read_bytes() == b'---\r\ntitle: old\r\nsuperseded_by: "[[Dir/New]]"\r\n---\r\nbody\r\n'
    assert (v/'Dir/New.md').read_bytes() == b'---\nkind: current\nsupersedes: "[[Old]]"\n---\nnew body\n'
    put(v, 'Bad.md', '---\nsupersedes: one\nsupersedes: two\n---\n')
    before = tree_digest(v)
    p = cli('supersede', v, 'Old.md', 'Bad.md', check=False)
    assert p.returncode == 2 and p.stderr.startswith(b'refused:')
    assert tree_digest(v) == before
    p = cli('supersede', v, 'Old.md', 'Old.md', check=False)
    assert p.returncode == 2 and tree_digest(v) == before


def test_folder_chief_fixture_and_dot_hygiene(tmp_path):
    v = tmp_path / 'brain'
    shutil.copytree(Path(__file__).parent / 'fixtures/folder-chief', v)
    for name in ('.sqlite-mem', '.obsidian'):
        (v/name).mkdir(); (v/name/'sentinel').write_bytes(b'untouched')
    before = tree_digest(v)
    note = 'notes/decisions/2026-09-29-example.md'
    assert result('props', v, note)['sources'] == ['conversation']
    assert result('resolve', v, note, 'Example Context')['resolved'] == 'Example Context.md'
    rendered = cli_json('render', v, note)
    assert 'Synthetic example' in rendered['text']
    assert tree_digest(v) == before


def test_supersession_references_survive_relocation_and_collision(tmp_path):
    v = tmp_path / 'v'; v.mkdir()
    put(v, 'Old.md', '---\nsuperseded_by: "[[Target]]"\nother: untouched\n---\nOld\n')
    put(v, 'Target.md', '---\nsupersedes: "[[Old]]"\n---\nTarget\n')
    put(v, 'Dest/Target.md', 'collision\n')
    before = tree_digest(v)
    p = cli('rename', v, 'Target.md', 'Dest/Target', check=False)
    assert p.returncode == 2 and tree_digest(v) == before
    result('rename', v, 'Target.md', 'Dest/New')
    assert (v/'Old.md').read_bytes() == b'---\nsuperseded_by: "[[New]]"\nother: untouched\n---\nOld\n'
    assert result('resolve', v, 'Old.md', 'New')['resolved'] == 'Dest/New.md'
    assert (v/'Dest/New.md').read_bytes() == b'---\nsupersedes: "[[Old]]"\n---\nTarget\n'


def test_u10_user_docs_and_metadata():
    root = Path(__file__).resolve().parents[1]
    readme = (root/'README.md').read_text()
    guide = (root/'DOCUMENTATION.md').read_text()
    assert 'Version 1.0.0.' in readme
    assert 'Folder Chief' in readme and 'brain/' in readme and '.sqlite-mem/' in readme
    assert 'This guide covers version 1.0.0.' in guide
    man = (root/'man/lcos-notes-cli.1').read_text() if (root/'man/lcos-notes-cli.1').exists() else (root/'data/lcos-notes-cli.1').read_text()
    for word in ('aliases', 'headings', 'props', 'supersede'):
        assert word in guide and word in man


def test_headings_extract_setext_and_ignore_fences(tmp_path):
    v = tmp_path / 'v'; v.mkdir()
    put(v, 'Doc.md', '---\nstatus: active\n---\n# **One** ##\n\nTwo *here*\n--------\n```\n# hidden\n```\n')
    assert result('headings', v, 'Doc.md') == [{'level': 1, 'text': 'One', 'line': 4}, {'level': 2, 'text': 'Two here', 'line': 6}]


def test_supersede_block_lists_and_newline_shapes(tmp_path):
    v = tmp_path/'v'; v.mkdir()
    put(v, 'Old.md', '---\r\nsuperseded_by:\r\n  - "[[A]]"\r\n  - "[[B]]"\r\nother: yes\r\n---\r\nold\r\n')
    put(v, 'New.md', '---\nsupersedes:\n  - "[[A]]"\n  - "[[B]]"\nother: yes\n---\nnew\n')
    result('supersede', v, 'Old.md', 'New.md')
    assert (v/'Old.md').read_bytes() == b'---\r\nsuperseded_by: "[[New]]"\r\nother: yes\r\n---\r\nold\r\n'
    assert (v/'New.md').read_bytes() == b'---\nsupersedes: "[[Old]]"\nother: yes\n---\nnew\n'
    put(v, 'Bare.md', 'crlf\r\nbody')
    put(v, 'Empty.md', '')
    result('supersede', v, 'Bare.md', 'Empty.md')
    assert (v/'Bare.md').read_bytes() == b'---\r\nsuperseded_by: "[[Empty]]"\r\n---\r\ncrlf\r\nbody'
    assert (v/'Empty.md').read_bytes() == b'---\nsupersedes: "[[Bare]]"\n---\n'


def test_supersede_refusals_prevalidate_both_documents(tmp_path):
    cases = [b'\xff', b'---\nkey: value\n', b'---\nsuperseded_by:\n  nested: bad\n---\n',
             b'---\nsupersedes:\n  nested: bad\n---\n']
    for i, fixture in enumerate(cases):
        for side in ('Old.md', 'New.md'):
            v = tmp_path / f'v{i}-{side}'; v.mkdir()
            put(v, 'Old.md', 'old\n'); put(v, 'New.md', 'new\n')
            bad = fixture
            # An unsupported continuation matters only on the key written on this side.
            if i == 2 and side == 'New.md': bad = bad.replace(b'superseded_by:', b'supersedes:')
            if i == 3 and side == 'Old.md': bad = bad.replace(b'supersedes:', b'superseded_by:')
            (v/side).write_bytes(bad)
            for dot in ('.sqlite-mem', '.obsidian'):
                (v/dot).mkdir(); (v/dot/'sentinel').write_bytes(b'unchanged')
            before = tree_digest(v)
            p = cli('supersede', v, 'Old.md', 'New.md', check=False)
            assert p.returncode == 2 and p.stderr.startswith(b'refused:')
            assert tree_digest(v) == before
    for target in ('Missing.md', 'Folder'):
        v = tmp_path/target.replace('.', '-'); v.mkdir()
        put(v, 'Old.md', 'old\n'); (v/'Folder').mkdir()
        before = tree_digest(v)
        p = cli('supersede', v, 'Old.md', target, check=False)
        assert p.returncode == 2 and p.stderr.startswith(b'refused:') and tree_digest(v) == before


def test_folder_relocation_preserves_metadata_lists_and_unrelated_bytes(tmp_path):
    v = tmp_path/'v'; v.mkdir()
    put(v, 'Stable.md', 'stable\n')
    put(v, 'Group/Target.md', 'target\n')
    put(v, 'Group/Peer.md', 'peer\n')
    original = ('---\r\nsuperseded_by: ["[[Group/Target]]", "[[Stable]]"]\r\n'
                'supersedes:\r\n  - "[[Group/Peer]]"\r\n  - "[[Stable]]"\r\n'
                'other: untouched\r\n---\r\nBody [[Group/Target]] and [[Stable]]\r\n')
    put(v, 'Record.md', original)
    for dot in ('.sqlite-mem', '.obsidian'):
        (v/dot).mkdir(); (v/dot/'sentinel').write_bytes(b'unchanged')
    (v/'Collision').mkdir()
    before = tree_digest(v)
    p = cli('rename', v, 'Group', 'Collision', check=False)
    assert p.returncode == 2 and tree_digest(v) == before
    result('rename', v, 'Group', 'Moved')
    expected = original.replace('[[Group/Target]]', '[[Target]]').replace('[[Group/Peer]]', '[[Peer]]')
    assert (v/'Record.md').read_bytes() == expected.encode()
    assert (v/'Moved/Target.md').read_bytes() == b'target\n'
    assert (v/'Moved/Peer.md').read_bytes() == b'peer\n'
    assert result('resolve', v, 'Record.md', 'Target')['resolved'] == 'Moved/Target.md'
    assert result('resolve', v, 'Record.md', 'Peer')['resolved'] == 'Moved/Peer.md'
    assert result('resolve', v, 'Record.md', 'Stable')['resolved'] == 'Stable.md'
    assert all((v/d/'sentinel').read_bytes() == b'unchanged' for d in ('.sqlite-mem','.obsidian'))


def test_metadata_does_not_enter_render_or_block_coordinates(tmp_path):
    v = tmp_path/'v'; v.mkdir()
    put(v, 'Old.md', '---\nsuperseded_by: "[[New]]"\ntags: [work]\n---\n# Heading\n\nBody\n')
    put(v, 'New.md', 'new\n')
    assert cli_json('render', v, 'Old.md') == {'text':'Heading\n\nBody', 'spans':[{'start':0,'end':7,'style':'h1'}], 'links':[], 'images':[]}
    assert cli_json('blocks', v, 'Old.md') == [{'line':5,'offset':0}, {'line':7,'offset':9}]
