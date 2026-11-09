#!/usr/bin/env python3
"""Build the LCOS Notes handbook. Build-only dependency: Python-Markdown."""
from __future__ import annotations
import argparse, hashlib, html, json, re, shutil, zipfile
from html.parser import HTMLParser
from pathlib import Path
import markdown

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'docs/handbook'
ASSETS=Path(__file__).resolve().parent
PUBLIC='https://nginx.leebasehome.com/lcos-notes/'
GIT='https://github.com/leebase/lcos-notes'
class Plain(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)

def link_target(href):
    path,mark,fragment=href.partition('#')
    if path.startswith('docs/handbook/') and path.endswith('.md'):
        return path.removeprefix('docs/handbook/')[:-3]+'.html'+(mark+fragment if mark else '')
    if path in ('README.md','../../README.md'):return 'installation.html'
    if path in ('DOCUMENTATION.md','../../DOCUMENTATION.md'):return 'full-reference.html'+(mark+fragment if mark else '')
    if path in ('ARCHITECTURE.md','CONTRACT.md','RELEASE-NOTES.md','LICENSE') or path.startswith('../../'):
        return GIT+'/blob/main/'+path.removeprefix('../../')+(mark+fragment if mark else '')
    if path.endswith('.md') and '/' not in path:return path[:-3]+'.html'+(mark+fragment if mark else '')
    return href

def render(text):
    md=markdown.Markdown(extensions=['fenced_code','tables','toc','sane_lists'],extension_configs={'toc':{'toc_depth':'2-3','permalink':False}})
    body=md.convert(text)
    body=re.sub(r'href="([^"]*)"',lambda m:'href="'+html.escape(link_target(html.unescape(m[1])),quote=True)+'"',body)
    parser=Plain();parser.feed(body)
    return body,md.toc,' '.join(' '.join(parser.parts).split())

def build(out):
    if out.exists() and any(out.iterdir()):raise SystemExit('Output must be a new or empty directory; keep prior builds intact.')
    out.mkdir(parents=True,exist_ok=True)
    pages=json.loads((SOURCE/'pages.json').read_text());slugs=[p['slug'] for p in pages]
    assert slugs[0]=='index' and len(set(slugs))==len(slugs)
    assert all(re.fullmatch(r'[a-z][a-z0-9-]*',s) for s in slugs)
    (out/'assets').mkdir();(out/'downloads').mkdir()
    for name in ['handbook.css','handbook.js']:shutil.copy2(ASSETS/name,out/'assets'/name)
    shutil.copy2(ROOT/'data/com.leebase.LcosNotes.svg',out/'assets/lcos-notes.svg')
    shutil.copy2(ROOT/'DOCUMENTATION.md',out/'downloads/lcos-notes-user-guide.md')
    search=[];inputs={};groups=list(dict.fromkeys(p['section'] for p in pages))
    for source in [SOURCE/'pages.json',ASSETS/'build.py',ASSETS/'handbook.css',ASSETS/'handbook.js',ROOT/'data/com.leebase.LcosNotes.svg']:
        inputs[source.relative_to(ROOT).as_posix()]=hashlib.sha256(source.read_bytes()).hexdigest()
    for i,p in enumerate(pages):
        slug=p['slug'];title=p['title'];src=ROOT/'DOCUMENTATION.md' if slug=='full-reference' else SOURCE/(slug+'.md')
        inputs[src.relative_to(ROOT).as_posix()]=hashlib.sha256(src.read_bytes()).hexdigest()
        body,toc,plain=render(src.read_text())
        nav=''
        for group in groups:
            nav+='<div class="nav-group"><p>'+html.escape(group)+'</p><ul>'
            for q in pages:
                if q['section']==group:
                    current=' aria-current="page"' if q['slug']==slug else ''
                    nav+='<li><a href="'+q['slug']+'.html"'+current+'>'+html.escape(q['title'])+'</a></li>'
            nav+='</ul></div>'
        previous=pages[i-1] if i else None;following=pages[i+1] if i+1<len(pages) else None
        pager='<nav class="pager" aria-label="Previous and next topics">'
        for q,label in [(previous,'Previous'),(following,'Next')]:
            pager+='<a href="'+q['slug']+'.html"><span>'+label+'</span>'+html.escape(q['title'])+'</a>' if q else '<span></span>'
        pager+='</nav>'
        download='<div class="home-actions"><a class="primary" href="quick-start.html">Start your first vault →</a><a href="'+GIT+'/releases/tag/v1.0.0">Download LCOS Notes 1.0.0</a></div>' if slug=='index' else ''
        source_path='DOCUMENTATION.md' if slug=='full-reference' else 'docs/handbook/'+slug+'.md'
        page=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · LCOS Notes handbook</title><meta name="description" content="{html.escape(p['description'],quote=True)}">
<link rel="canonical" href="{PUBLIC}{'' if slug=='index' else slug+'.html'}"><link rel="icon" href="assets/lcos-notes.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/handbook.css">
<script defer src="assets/search-index.js"></script><script defer src="assets/handbook.js"></script></head>
<body><a class="skip" href="#main">Skip to content</a>
<header class="topbar"><a class="brand" href="index.html"><img src="assets/lcos-notes.svg" width="32" height="32" alt=""><span>LCOS Notes <small>1.0 handbook</small></span></a>
<button class="menu-toggle" type="button" aria-expanded="false" aria-controls="sidebar">Topics</button>
<div class="search"><label class="visually-hidden" for="doc-search">Search the handbook</label><input id="doc-search" type="search" placeholder="Search the handbook…" autocomplete="off" aria-controls="search-results" aria-expanded="false"><kbd class="search-hint">Ctrl K</kbd><div id="search-results" class="search-results" hidden><p id="search-status" role="status" aria-live="polite"></p><ul></ul></div></div>
<a class="git-link" href="{GIT}/tree/main/docs/handbook">Git source ↗</a></header>
<div class="layout"><aside id="sidebar" class="sidebar"><nav aria-label="Handbook topics">{nav}</nav><div class="sidebar-footer"><a href="downloads/lcos-notes-handbook.zip">Download offline handbook</a><a href="https://nginx.leebasehome.com/docs/pages/lcos-notes.html">All LCOS Notes documentation ↗</a></div></aside>
<main id="main" tabindex="-1"><p class="eyebrow">{html.escape(p['section'])} / LCOS Notes 1.0.0</p><article>{body}</article>{download}{pager}
<footer><p>LCOS Notes 1.0.0 · Updated 9 November 2026 · Apache License 2.0</p><p><a href="{GIT}/blob/main/{source_path}">Read this page on GitHub</a> · <a href="sources.html">Sources and accuracy</a> · <a href="downloads/lcos-notes-user-guide.md" download>Complete reference (Markdown)</a></p><p>Independent documentation for LCOS Notes. Not affiliated with Obsidian.</p></footer></main>
<aside class="on-this-page" aria-label="On this page"><p>On this page</p>{toc}</aside></div><noscript><p class="no-script">All topics and links work without JavaScript. Use your browser’s Find command to search this page.</p></noscript></body></html>'''
        (out/(slug+'.html')).write_text(page)
        search.append({'title':title,'url':slug+'.html','description':p['description'],'text':plain})
    (out/'assets/search-index.js').write_text('window.LCOS_DOCS = '+json.dumps(search,ensure_ascii=True)+';\n')
    (out/'build.json').write_text(json.dumps({'product':'lcos-notes-handbook','app_version':'1.0.0','documentation_date':'2026-11-09','pages':slugs,'source_sha256':inputs},indent=2)+'\n')
    (out/'robots.txt').write_text('User-agent: *\nAllow: /lcos-notes/\n')
    # A self-contained copy works from a local file: search index is JavaScript, not a fetch.
    files=sorted(p for p in out.rglob('*') if p.is_file())
    with zipfile.ZipFile(out/'downloads/lcos-notes-handbook.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in files:
            data=p.read_bytes()
            if p.suffix=='.html':
                data=data.replace(b'<a href="downloads/lcos-notes-handbook.zip">Download offline handbook</a>',b'<span>Offline handbook</span>')
            info=zipfile.ZipInfo(p.relative_to(out).as_posix(),date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;archive.writestr(info,data)
    print(json.dumps({'result':'BUILT','pages':len(pages),'output':str(out),'offline_archive':str(out/'downloads/lcos-notes-handbook.zip')},indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args();build(args.output.resolve())
