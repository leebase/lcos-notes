# LCOS Notes

A native, offline Markdown notes app for LCOS and other X11 desktops, compatible
with Obsidian-style vaults.

Your notes stay ordinary `.md` files in an ordinary folder. LCOS Notes adds
`[[wikilinks]]`, `[Markdown links](note.md)`, block references, backlinks, tags, search, a quick switcher, safe renames that
repair links, and a clean reading view with GitHub-style tables and tasks, `==highlights==`,
callouts, and embedded notes and images. It has a classic menubar, a notes tree and
the window manager's own title bar. There are no accounts, no network access, no
telemetry and no AI features.

**LCOS Notes 1.1.0 — November 13, 2026.** Version 1.1.0.
Switch projects without restarting: **File > Open Vault…**, **Recent Vaults…**
and **New Vault…** are now available, with the active vault path visible above
the workspace. Switching saves first; a failed save keeps your current vault
and edits open. Vaults remain independent. **Ctrl+O** still selects notes.

[Download 1.1.0](https://github.com/leebase/lcos-notes/releases/tag/v1.1.0) ·
[Upgrade from an earlier version](#upgrade-from-an-earlier-version) ·
[Work with vaults](docs/handbook/vaults.md) · [Release notes](RELEASE-NOTES.md).
Apache License 2.0.

## Download and install (LCOS 1.0)

Download the `.deb` and checksums from the
[1.1.0 release](https://github.com/leebase/lcos-notes/releases/tag/v1.1.0):

```sh
sudo apt update
sudo apt install ./lcos-notes_1.1.0_amd64.deb
```

Version 1.1.0 adds vault management to the existing organization, capture and
reading features. Earlier
[1.0.0 downloads](https://github.com/leebase/lcos-notes/releases/tag/v1.0.0) remain available.

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

## Upgrade from an earlier version

1. Save your notes and close LCOS Notes. Keep your usual independent vault backup.
2. Download `lcos-notes_1.1.0_amd64.deb` and `SHA256SUMS` from the
   [1.1.0 release](https://github.com/leebase/lcos-notes/releases/tag/v1.1.0).
3. In that download folder, run:

```sh
sha256sum -c SHA256SUMS
sudo apt update
sudo apt install ./lcos-notes_1.1.0_amd64.deb
```

The checksum must report `OK` for the package. Installing the newer package
upgrades the existing installation in place; you do not need to uninstall it.
Your vault folders and existing user configuration stay in place; no vault
conversion or import is required. Reopen Notes, check **Help > About** for
**1.1.0**, then use the new File-menu vault controls.

There is no LCOS Notes apt repository: `apt upgrade` alone does not download this
release. Install the downloaded `.deb` as above. The [handbook](docs/handbook/installation.md)
includes the same upgrade steps. Older downloads remain in the release history.

## Using it

Start with the [LCOS Notes handbook](https://nginx.leebasehome.com/lcos-notes/) for a three-note tutorial, task guides and searchable reference. The [handbook source](docs/handbook/index.md) is also available here.

Start with the [user guide](DOCUMENTATION.md) for daily use and the
[architecture guide](ARCHITECTURE.md) for the implementation and data boundaries.
[Release notes](RELEASE-NOTES.md) describe 1.1.0 and its
[documented limitations](RELEASE-NOTES.md#documented-limitations).

LCOS Notes also includes daily notes, templates, timestamp names and quick
capture; aliases, Properties, Outline, Move, Archive and Supersede; full-width
callouts, including nested and mixed-list cases; and highlights across inline
formatting while preserving links. New Note labels align left. The U9 implementation
was reformatted without a behavior change.

**Optional font coverage:** LCOS Notes uses installed system fonts. For Chinese,
Japanese and Korean coverage, install fonts-noto-cjk. See the [font instructions](DOCUMENTATION.md#optional-language-fonts).

The keys you will use most:

| Key | Action |
|---|---|
| Ctrl+N | New Note dialog |
| Ctrl+Shift+E / T / M / O | Notes, Tags, Unlinked mentions, Outline |
| F6 | Move the current note |
| Ctrl+D | Today’s daily note |
| Ctrl+Shift+I | Insert Template |
| Ctrl+O | Quick switcher: open or create a note |
| Alt+Enter, Ctrl+click | Follow the link under the caret (creates missing notes) |
| Ctrl+E | Toggle the reading view |
| Ctrl+S | Save (switching notes and closing also save) |
| Ctrl+Shift+R | Reload from Disk, discarding unsaved edits |
| Ctrl+Shift+F | Search all notes |
| Ctrl+Shift+B | Jump to backlinks |
| F2 | Rename the current note or selected note, folder, attachment or tag |

## Vault management

From the running app, use **File > Open Vault…** for an existing readable folder,
**Recent Vaults…** to return to a recent project, or **New Vault…** to create an
empty folder. The full active path appears above the workspace. No terminal or
restart is needed. Search and links stay within the selected vault.
See [Work with vaults](docs/handbook/vaults.md) for creation requirements and limits.

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
packaging/build-deb.sh ~/out      # writes ~/out/lcos-notes_1.1.0_<arch>.deb
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
and non-local links, opening attachments with an external viewer, NFC search,
settings dialogs, graph view, multiple
windows, GFM autolinks and footnotes, an apt repository and package signing.

## Using LCOS Notes with Folder Chief

A Folder Chief `brain/` directory can be opened as a vault. Markdown notes can
use `aliases`, `tags`, `superseded_by` and `supersedes` properties and wikilinks
for decision records. Hidden directories, including `.sqlite-mem/` and
`.obsidian/`, are skipped and never written by the vault operations.
