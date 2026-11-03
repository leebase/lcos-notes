# LCOS Notes

A native, offline Markdown notes app for LCOS and other X11 desktops, compatible
with Obsidian-style vaults.

Your notes stay ordinary `.md` files in an ordinary folder. LCOS Notes adds
`[[wikilinks]]`, `[Markdown links](note.md)`, block references, backlinks, tags, search, a quick switcher, safe renames that
repair links, and a clean reading view with GitHub-style tables and tasks, `==highlights==`,
callouts, and embedded notes and images. It has a classic menubar, a notes tree and
the window manager's own title bar. There are no accounts, no network access, no
telemetry and no AI features.

Version 0.8.0. Apache License 2.0.

## Download and install (LCOS 1.0)

Download `lcos-notes_0.8.0_amd64.deb` from the
[latest release](https://github.com/leebase/lcos-notes/releases/latest), then:

```sh
sudo apt update
sudo apt install ./lcos-notes_0.8.0_amd64.deb
```

Run `sudo apt update` first on a fresh LCOS install: it ships without package lists,
and `apt` needs them to fetch the cmark-gfm libraries LCOS Notes uses (`libcmark-gfm0.29.0.gfm.13` and
`libcmark-gfm-extensions0.29.0.gfm.13`).

LCOS Notes then appears in the applications menu under Office. You can also start it
from a terminal:

```sh
lcos-notes                      # reopens your last vault, or asks for a folder
lcos-notes --vault ~/Notes      # opens a specific vault
```

The package is built on Devuan Excalibur, the base of LCOS 1.0, and installs
there. On other Debian-family systems, build your own package from source (below).

## Using it

[DOCUMENTATION.md](DOCUMENTATION.md) is the user guide. It covers vaults, links,
keyboard shortcuts, the reading view, backlinks, search, tags, renaming and the
command-line tool.
U6 adds parent tag counts, singular frontmatter `tag:`, prefix tag rename (`retag`),
whole-word and GLib regex search (`find --word --regex`), folder and attachment
rename, and unlinked mentions (`mentions`). The switcher offers a selectable
Create row. Newly created notes open in the editor, ready for typing.

U7 adds GFM tables, task lists and strikethrough, task toggling by Space or
click in reading view, and automatic external-change reload. Ctrl+Shift+R
reloads the open note from disk; `tasks VAULT NOTE` lists task positions.

The CLI `mdlinks` command lists Markdown note links. Name comparisons normalize to
NFC before Unicode case folding; stored paths and display text keep their bytes.

The keys you will use most:

| Key | Action |
|---|---|
| Ctrl+N | New Note dialog |
| Ctrl+Shift+E / T / M | Notes, Tags, Unlinked mentions |
| Ctrl+O | Quick switcher: open or create a note |
| Alt+Enter, Ctrl+click | Follow the link under the caret (creates missing notes) |
| Ctrl+E | Toggle the reading view |
| Ctrl+S | Save (switching notes and closing also save) |
| Ctrl+Shift+R | Reload from Disk, discarding unsaved edits |
| Ctrl+Shift+F | Search all notes |
| Ctrl+Shift+B | Jump to backlinks |
| F2 | Rename the current note or selected note, folder, attachment or tag |

## Building from source

You need a C++17 compiler, Meson (0.56 or later), Ninja, pkg-config and the
development packages for gtkmm-3.0 (3.24 or later), gtksourceviewmm-3.0 (3.18 or
later) and cmark-gfm and its extensions (0.29.0 or later). On Devuan, Debian, Ubuntu or Mint:

```sh
sudo apt install build-essential meson ninja-build pkg-config \
    libgtkmm-3.0-dev libgtksourceviewmm-3.0-dev libcmark-gfm-dev libcmark-gfm-extensions-dev
meson setup build
meson compile -C build
./build/lcos-notes --vault /path/to/vault
```

To install system-wide, use `meson setup build --prefix=/usr`, then
`meson compile -C build` and `sudo meson install -C build`.

To build a `.deb` for the machine you are on (no root needed; `dpkg-dev` required):

```sh
packaging/build-deb.sh ~/out      # writes ~/out/lcos-notes_0.8.0_<arch>.deb
```

## Tests

`tests/` holds the acceptance suite: core rules through the command-line tool, GUI
behavior driven under Xvfb with xfwm4, and packaging checks. Run
`python3 tests/oracle.py acceptance` from the repository root. This needs pytest,
Xvfb, xfwm4, dbus and the X11/XTest development headers. [CONTRACT.md](CONTRACT.md)
is the exact specification the tests check.

## License

Copyright 2026 Lee Harrington. Licensed under the Apache License, Version 2.0; see
[LICENSE](LICENSE). App id `com.leebase.LcosNotes`.

LCOS Notes is an independent project for the LCOS desktop. It is not affiliated
with Obsidian.

Unsupported: Markdown links with titles or reference syntax, following images
and non-local links, attachment viewing, transclusion, NFC search,
settings dialogs, daily notes, graph view, multiple
windows, GFM autolinks and footnotes, package publishing and signing.
