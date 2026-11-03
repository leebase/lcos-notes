# U1 contract: vault, editor, wikilinks, quick switcher

This is the finite supported scope for the first unit. Anything not listed here is
out of scope for U1; out-of-scope input is refused or ignored as stated, never guessed.
The frozen tests in `tests/` are the oracle for this contract.

## Product and stack

- A native notes app for LCOS (a Devuan-based desktop: XFCE, xfwm4, Clearlooks themes,
  X11 only) that runs equally on other X11 desktops. Development host: Linux Mint 22.3.
- C++17, Meson (>= 0.56), gtkmm-3.0 (>= 3.24), gtksourceviewmm-3.0 (>= 3.18). cmark is linked from
  U3. No other third-party runtime libraries. No WebKit,
  Electron, Qt, Python at runtime, network access, accounts, telemetry or AI features.
- Window-manager title bars only: never `set_titlebar`, never a `Gtk::HeaderBar`, no
  client-side decorations. `GDK_BACKEND=x11` is set at startup if it is unset.
- Classic layout: menubar (File, Edit, View, Go, Help), a notes tree on the left, the editor
  in the middle, a statusbar at the bottom showing `Ln N, Col M`. Follows the GTK theme; the
  editor area may use a fixed light background with a dark caret, as other LCOS apps do.
- License Apache-2.0 (relicensed from GPL-3.0-or-later on 2026-11-01). Copyright 2026 Lee Harrington. App id `com.leebase.LcosNotes`.

## Build

`meson setup <dir> && meson compile -C <dir>` from the repository root produces two
executables at the top of `<dir>`:

- `lcos-notes` — the GUI.
- `lcos-notes-cli` — a command-line view of the same core library the GUI uses. The GUI
  must not reimplement any rule below separately; both link one core.

## Vault

A vault is a directory. Notes are regular files ending in `.md` (lower case) anywhere under
it. Skipped entirely: any file or directory whose name starts with `.` (this covers
`.obsidian/`, `.trash/`, `.git/`), and symlinks (not followed, not listed). Vault-relative
paths use `/` and never start with `/` or `./`. Sorting is by byte order of the
vault-relative path.

The app never creates, modifies or deletes anything inside a dot-directory of the vault,
and never writes any file into the vault other than notes the user saves or creates.
Settings (last vault) live under `$XDG_CONFIG_HOME/lcos-notes/` (default
`~/.config/lcos-notes/`).

## Wikilinks

A wikilink is `[[inner]]` on one line, where `inner` is non-empty and contains no `[`, `]`
or newline. `![[inner]]` is the same link with `embed: true`. Not links:

- anything inside a fenced code block (a line whose first non-space characters are three or
  more backticks or tildes opens a fence; a line starting with a fence of the same character
  at least as long closes it; an unclosed fence runs to end of file);
- anything inside an inline code span (a run of N backticks up to the next run of exactly N
  backticks on the same line; an unmatched run is literal text).

`inner` is split as: `alias` = text after the first `|`; then from the remaining text,
`heading` = text after the first `#`; `target` = what is left. Each part is trimmed of
spaces. Missing parts are `null`. A heading that starts with `^` is a block reference and is
reported as-is (U1 does not jump to blocks).

Positions: `line` is 1-based; `col` is the 1-based Unicode code point column of the first
character of the link (`!` for embeds, else the first `[`).

## Resolution

Given a vault, the source note (vault-relative) and a link's `target`:

1. Empty target means the source note itself.
2. Strip one trailing `.md` (case-insensitive) from the target, then resolve it as a note
   (steps 3–5). Only if no note matches and the target's final segment has an extension
   (text after its last `.`, 1–5 ASCII letters or digits) is it an attachment link: it then
   resolves to a non-hidden, non-symlink regular file that is not a note, matched by the same
   path rules and tie-breaking applied to the full file name, else unresolved. So
   `[[Report.2025]]` opens `Report.2025.md` when that note exists. The GUI does not open
   attachments in U1.
3. Comparison is case-insensitive using Unicode case folding (`g_utf8_casefold` of both
   sides, NFC not applied).
4. Target with `/`: candidates are notes whose path without `.md` equals the target, else
   notes whose path without `.md` ends with `/` + target (whole segments only).
   Target without `/`: candidates are notes whose file name without `.md` equals the target.
5. Tie-break among several candidates: a note in the same directory as the source wins;
   otherwise the fewest path segments; then byte order of the vault-relative path.
6. No candidate: unresolved.

## Creating a note from a link or the quick switcher

The new note's path is the target (trimmed, one trailing `.md` stripped) plus `.md`,
relative to the vault root; a `/` in the target creates intermediate directories. Refused
(no file or directory created, exit status 2, one line `refused: <reason>` on stderr for
the CLI; a statusbar message in the GUI): empty target, absolute path, any segment that is
`.`, `..` or starts with `.`, any of the characters `* " \ < > : | ? #` or `^`, or a
control character. If the target already resolves to a note (resolution rules above, with
the source directory taken as the vault root, so case is ignored), nothing is created or
touched and that note is opened instead. New notes are empty (0 bytes).

## Quick switcher ranking

Query and names are compared after Unicode case folding. A note matches if the query's
characters appear in order (subsequence) in its vault-relative path without `.md`. Empty
query matches every note. Order: (a) file name without `.md` equals the query, (b) file name
starts with the query, (c) file name contains the query as a substring, (d) other matches;
within a group, fewer path segments first, then byte order of the path. At most 50 results.

## CLI (`lcos-notes-cli`)

All output is UTF-8 JSON on stdout followed by a newline; exit 0 on success.

- `notes VAULT` → array of vault-relative note paths, sorted.
- `links VAULT NOTE` → array of objects `{"raw", "target", "heading", "alias", "embed",
  "line", "col", "resolved"}` in document order; `raw` is the full link text including
  brackets and `!`; `resolved` is the vault-relative path or `null`.
- `resolve VAULT SOURCE INNER` → `{"target", "heading", "alias", "resolved"}` for one link
  inner text (no brackets).
- `switch VAULT QUERY` → array of vault-relative note paths in ranking order.
- `create VAULT TARGET` → `{"path": <vault-relative>, "created": true|false}`; refusal is exit
  2 as above.

A VAULT that is not a directory, or a NOTE/SOURCE that is not an existing note in the vault,
is exit 2 with `refused: <reason>`.

## GUI behavior

- `lcos-notes --vault DIR [NOTE]` opens that vault, and NOTE (vault-relative) if given.
  Without `--vault` it opens the last vault, else asks for a folder.
- Title: `<file name without .md> — Notes`, with ` *` after the name while there are unsaved
  changes (`Ideas * — Notes`). With no note open: `<vault directory name> — Notes`.
- Ctrl+S saves the current note. Saving writes exactly the buffer text (no added or removed
  trailing newline, `\r\n` preserved) through a temporary file in the same directory and an
  atomic rename. Saving an unmodified note does not write. If the file changed on disk
  since it was loaded or last saved, saving does not overwrite it; the statusbar says
  `Changed on disk; not saved` and the buffer keeps the user's text.
- Opening a note places the caret at the start of the note (except when following a heading,
  below) and puts keyboard focus in the editor.
- Loading a note is never an undoable action: every opened note starts with an empty undo
  history, so Undo can never blank a note or bring back another note's text.
- Opening another note, and closing the window, first save the current note if it has
  unsaved changes. If that save is refused because the file changed on disk, the user's text
  is never silently dropped: opening another note does not happen (the current note stays
  open with the statusbar message), and closing the window shows a modal dialog asking
  whether to discard the changes, with Discard and Cancel; Escape or Cancel keeps the window
  open.
- The caret is on a link when it lies after the link's first character and no later than
  just before its last character (for `[[A]]` at line start: caret columns 2 to 5).
- Alt+Enter follows the link under the caret; Ctrl+click follows the clicked link. Following
  opens the resolved note, placing the caret at the start of the heading line when a heading
  is given and found (the first line that is an ATX heading `#`..`######` whose text equals
  the heading after case folding), else at the start of the note. Following an unresolved
  link creates the note (rules above) and opens it. An embed is followed like a link.
  Attachment links show `Not a note: <path>` in the statusbar.
- Ctrl+O opens the quick switcher: a small dialog with a text entry and a result list ranked
  as above; focus starts in the entry and the list updates as the user types. Enter opens
  the selected (initially the first) result; Enter with no results
  creates a note named by the query (rules above) and opens it. The dialog closes on Enter
  in every case (including a refused switch) and on Escape; Escape changes nothing else.
- The notes tree lists vault folders and notes (hidden entries skipped) and refreshes after
  a note is created. Activating a note opens it.

## U2: highlighting, backlinks, search, tags, rename

U2 adds these to U1; everything above stays in force. Notes that are not valid UTF-8 are
ignored by every U2 command (never searched, never modified, contribute no links or tags).

### Tags

Inline tags, outside fenced code blocks and inline code spans (U1 rules) and outside
frontmatter: a `#` that is at the start of a line or preceded by a space or tab, followed by
a maximal run of tag characters — Unicode letters and digits (`g_unichar_isalnum`), `_`,
`-` and `/`. The run is the tag; it must be non-empty and contain at least one character
that is not an ASCII digit (`#123` is not a tag, `#y2025` is). `# Heading` is not a tag.

Frontmatter: if a note's first line is exactly `---`, frontmatter runs to the next line
that is exactly `---` or `...` (lines compared without a trailing `\r`); without such a
line there is no frontmatter. In it, a line that starts (column 1) with `tags:` declares
tags: a flow list `tags: [a, b]`, a scalar `tags: a, b c` (split on commas and whitespace),
or, when nothing follows the colon, the following lines of the form `  - a` (any
indentation, `- ` then the item) up to the first line that is not such an item. Items are
trimmed, one pair of surrounding `"` or `'` quotes and one leading `#` are removed, and an
item is kept only if it is a valid tag by the inline rule. Other YAML forms are ignored.

Tags compare by Unicode case folding. A tag's display form is its first occurrence in the
vault: notes in byte order, frontmatter before body, then position.

### Search

Search finds every non-overlapping occurrence of the query in every note, left to right,
case-insensitively by per-code-point lower-casing (`g_unichar_tolower`), over the whole
text (frontmatter and code included). Lines split on `\n`; a trailing `\r` is not part of
the line. The query is used as typed (not trimmed) and must not be empty. Results are
ordered by note path (byte order), line, column, and capped at 500.

### Backlinks

The backlinks of note N are all links (embeds included) in other notes whose resolution
(U1 rules, from that other note) is N. Links in N itself are not backlinks of N. Order:
source path (byte order), line, column.

### Rename

Renaming note OLD to target NEW (a target as for creation: trimmed, one trailing `.md`
removed, `.md` appended) moves the file and rewrites links so that this invariant holds:

- every link that resolved before the rename resolves afterwards to the same file, where
  OLD now means the renamed note (links inside the renamed note itself included, evaluated
  from its new path);
- every link that was unresolved before is left byte-identical (it may now resolve);
- only links that would otherwise break the first rule are rewritten; all other bytes of
  every note stay identical, including line endings; notes without rewritten links are not
  written at all.

A rewritten link keeps its `!`, heading and alias and is written in canonical form
`[[T#heading|alias]]` (heading and alias only when present, no extra spaces). T is the
target file's name without `.md` (for attachments, the full file name) if that resolves to
the intended file from that source; otherwise its full vault-relative path (without `.md`
for notes) if that does; otherwise the rename is refused. Intermediate directories are
created; emptied directories are left in place.

Refused (exit status 2, `refused: <reason>`, nothing on disk changes): OLD is not a note;
NEW is refused by the creation rules; NEW's path equals, after case folding, the path of a
note other than OLD, or exactly the path of any other existing file or directory; or a link
cannot be kept pointing at its file (above). A case-only rename of OLD is allowed. Changed
notes are written with the U1 atomic-save method.

### CLI additions

- `tags VAULT` → array of `{"tag", "count"}`: display form without `#`, and the number of
  notes containing it; ordered by folded tag (byte order), then display form.
- `tagged VAULT TAG` → array of note paths (sorted) containing TAG or any tag nested under it
  (`TAG/...`), compared after folding; a leading `#` in TAG is ignored. An invalid TAG is
  exit 2 `refused: <reason>`.
- `find VAULT QUERY` → array of `{"path", "line", "col", "text"}`; `col` is the 1-based code
  point column of the match, `text` the whole line. An empty QUERY is exit 2.
- `backlinks VAULT NOTE` → array of `{"source", "line", "col", "raw"}`.
- `rename VAULT OLD NEW` → `{"from": OLD, "to": <new path>, "updated": [<paths, sorted, of
  notes whose bytes changed, by their final paths>]}`.

### GUI additions

- The editor uses GtkSourceView's installed `markdown` language. Wikilinks (outside code)
  are additionally underlined: resolved links in a link color, unresolved links in a
  visibly different color. Styling follows edits (refreshed at most 300 ms after typing
  stops) and uses the same core parsing and resolution.
- The notes tree selection always shows the open note (parents expanded).
- A Backlinks pane on the right lists the open note's backlinks as `source path (line N)`
  with the line's text, refreshed whenever a note is opened, saved, created or renamed.
  Ctrl+Shift+B focuses the list with the first row selected; Enter or a double-click opens
  the source note with the caret at the start of that link.
- Ctrl+Shift+F opens a Search dialog (entry with focus, live result list as
  `path:line: text`). Enter opens the selected (initially the first) result with the caret
  at the start of the match and focus in the editor; with no results Enter just closes.
  Escape closes. The dialog always closes on Enter.
- A Tags tab beside the notes tree lists tags as `tag (count)`; expanding a tag shows its
  notes (`tagged` rule); activating a note opens it.
- F2 (and File > Rename…) opens a Rename dialog with the open note's path without `.md`,
  selected. Enter saves the open note first (a refused save refuses the rename), then
  renames by the rules above and reopens the note at its new path with the caret at the
  same position; title, tree, tags and backlinks refresh. A refused rename shows
  `Rename refused: <reason>` in the statusbar and changes nothing. Escape cancels.

## U3: reading view, packaging, backlinks pane

U3 adds these to U1 and U2; everything above stays in force. cmark (>= 0.30, the system
`libcmark`, CommonMark only, parse options 0) is now a required runtime library; nothing
else is added. The project version is `0.3.0` (Meson project, About dialog, package).

### Reading view rendering

Rendering a note's text produces a plain `text` (no trailing newline), style `spans` and
`links`. All offsets are 0-based Unicode code point offsets into `text`; ranges are
`[start, end)`.

1. Wikilinks are found with the U1 rules. Before Markdown parsing, each wikilink's raw text
   is replaced by one placeholder character that cmark treats as an ordinary
   (non-punctuation, non-space) character. Then frontmatter (U2 definition) is removed:
   rendering starts after its closing line. The rest is parsed by cmark.
2. Blocks are rendered in document order and joined by one blank line (`\n\n`). Inside a
   block quote, child blocks are joined the same way. Inside a list item, child blocks are
   joined by `\n` when cmark marks the list tight and by `\n\n` when it is loose.
   - Paragraph: its inlines. Heading: its inlines, span `h1`..`h6` by level.
   - Code block (fenced or indented): its literal minus one trailing `\n`, span `codeblock`.
   - HTML block: its literal minus one trailing `\n`, shown as text, never interpreted.
   - Thematic break: 20 × U+2500 (`─`), span `rule`.
   - Block quote: its children, span `quote` over the whole rendered quote.
   - List: items joined by a single `\n` (no blank line between items, tight or loose).
     The item prefix is `• ` (U+2022 and a space) for a bullet list, or `N. ` / `N) `
     for an ordered list, using the list's own delimiter and N = list start + item index.
     The item's rendered children get the prefix on their first line, and every later line
     that is not empty is indented by as many spaces as the prefix has code points
     (so nested lists indent under their parent's text). Spans and links move with their
     text; a span or link that starts at a line start starts after the indentation.
3. Inlines: text as is; soft break → one space; hard break → `\n`; inline code → its
   literal, span `code`; raw HTML → its literal as text; emphasis → its content, span
   `em`; strong → span `strong`; a Markdown link or image → its content (for an image, the
   alt text), span `url` (not followable in U3).
4. A placeholder in text becomes the link's display text with span `link` (resolved) or
   `unresolved`, and an entry in `links`. Display text: the alias if non-empty; else, if
   the heading is non-empty, `target > heading` (just `heading` when the target is
   empty); else the target if non-empty; else the source note's file name without `.md`.
   A placeholder inside literal text (inline code, code block, HTML, rule 2 and 3) shows
   the link's raw text and is not a link. Placeholders cmark drops (inside a Markdown
   link's destination or title) produce nothing.
5. `spans` are sorted by (start, end, style), duplicates removed, empty spans omitted.
   `links` are in rendered order: `{"start", "end", "raw", "resolved"}` where `resolved`
   is the U1 resolution from the note (vault-relative path or `null`).

The rendering rules are the core's; the GUI uses the core's result as is.

CLI: `render VAULT NOTE` → `{"text", "spans": [{"start", "end", "style"}], "links": [...]}` for
the note's file contents. A note that is not valid UTF-8 is exit 2 `refused: <reason>`.

### Reading view in the GUI

- Ctrl+E (and View > Reading View) toggles between the editor and a reading view of the
  open note. The reading view is a read-only text view showing the rendered text of the
  current buffer (unsaved edits included) with the styles applied (headings larger and
  bold, `em` italic, `strong` bold, `code`/`codeblock` monospace on a tinted background,
  `quote` indented and dimmed, `url` and `link` underlined in the U2 link color,
  `unresolved` in the U2 unresolved color, `rule` dimmed). It follows the GTK theme the
  same way the editor does.
- Switching to reading view puts keyboard focus in it with a visible caret at the start
  of the text. Typing, pasting, Ctrl+S, Undo and Redo never change the buffer or the
  file while reading. Switching back restores the editor with its caret where it was.
- The mode is sticky: opening any note (tree, switcher, backlinks, search, link
  following, rename) keeps the current mode. In reading view the newly opened note is
  shown rendered, caret at the start of the text, and the editor caret is placed by the
  U1/U2 rules for that action, so switching back shows it there.
- The caret is on a rendered link when `start <= caret offset < end`. Enter or Alt+Enter
  on a link, or a plain left click on it, follows it exactly as Alt+Enter does in the
  editor (U1: save first, heading caret, create if unresolved, attachment message). Enter
  elsewhere does nothing.
- The title, statusbar position text, Backlinks pane and notes tree behave as in the
  editor; the statusbar shows `Reading` while in reading view.

### Backlinks pane

The Backlinks list has two columns, `Source` (`path (line N)`) and `Text` (the line's
text), both resizable by dragging the column header edge; the divider between editor and
pane can be dragged; the pane's initial width is at least 300 px. Keyboard behavior and
contents are unchanged from U2.

### Install and package

- `meson install` (with `--prefix=/usr`) installs exactly: `bin/lcos-notes`,
  `bin/lcos-notes-cli`, `share/applications/com.leebase.LcosNotes.desktop`,
  `share/metainfo/com.leebase.LcosNotes.metainfo.xml`,
  `share/icons/hicolor/scalable/apps/com.leebase.LcosNotes.svg`,
  `share/man/man1/lcos-notes.1` and `share/man/man1/lcos-notes-cli.1`.
- Desktop entry: `Type=Application`, `Name=LCOS Notes`, a `Comment`, `Exec=lcos-notes`,
  `Icon=com.leebase.LcosNotes`, `Terminal=false`, `Categories` containing `Office` and
  `TextEditor`. The icon is an original SVG in a flat 90s style (no gradients required,
  readable at 16 px and 48 px), contains no raster images and no text.
- AppStream metainfo: component type `desktop-application`, id `com.leebase.LcosNotes`,
  `metadata_license` `CC0-1.0`, `project_license` `Apache-2.0`, a `launchable` of
  type `desktop-id` naming the desktop file, homepage URL `https://leebase.com/`, an empty
  `content_rating` of type `oars-1.1`, a release entry for 0.3.0, and it passes `appstreamcli validate --no-net`.
- Man pages are roff pages starting with `.TH` describing options and commands.
- `packaging/build-deb.sh OUTDIR` builds `OUTDIR/lcos-notes_0.3.0_<arch>.deb` (arch from
  `dpkg --print-architecture`) on any Debian-family host that has the build dependencies
  (a C++17 compiler, meson, ninja, pkg-config, gzip, dpkg-dev, and the `-dev` packages of
  gtkmm-3.0, gtksourceviewmm-3.0 and cmark), without network access, root, fakeroot or
  debhelper, and without writing anything inside the source tree (all build and staging
  directories are temporary and removed). It configures a release build with prefix
  `/usr`, installs with `DESTDIR`, strips the binaries, gzips the man pages (`-9n`), adds
  `usr/share/doc/lcos-notes/copyright` (machine-readable DEP-5, `Copyright: 2026 Lee
  Harrington`, `License: Apache-2.0`), computes `Depends` with `dpkg-shlibdeps` on the host,
  and builds with `dpkg-deb --root-owner-group`. The package contains exactly the
  installed files above (man pages as `.1.gz`) plus the copyright file; directories
  0755, binaries 0755, other files 0644.
- Control fields: `Package: lcos-notes`, `Version: 0.3.0`, `Architecture: <arch>`,
  `Maintainer: Lee Harrington <lee@leebase.com>`, `Section: editors`,
  `Priority: optional`, `Installed-Size`, `Depends` (from dpkg-shlibdeps), and a
  `Description` with a one-line synopsis and an extended description.
- Built on a host, the package installs with `apt install ./lcos-notes_0.3.0_<arch>.deb`
  on that host's distribution release (the supported deployment path for LCOS is building
  on Devuan Excalibur, its base).

## U4: fit and finish

U4 changes these rules; everything above stays in force except where a rule below replaces
it. The project version is `0.4.0` (Meson project, About dialog, package file name and
control `Version`); wherever U3 names `0.3.0` as the project or package version, read
`0.4.0`. The AppStream metainfo keeps its 0.3.0 release entry and adds one for 0.4.0.

### Window size

The main window's initial size fits the monitor work area it opens on. The client size is
1100×650 when the work area is at least 1200×780. On a smaller work area, at least
800×600, both dimensions shrink so that the whole window, title bar and frame included,
lies inside the work area, and the client area is never smaller than 640×480. On a
1024×768 work area the editor is at least 300 px wide and the Backlinks pane keeps its
initial width of at least 300 px.

### Reading view

- The reading view has 12 px left and right text margins (the quote indent comes on top
  of the left margin).
- Only a plain left click (no Shift, Ctrl or Alt held) on a rendered link follows it.
  Shift+click extends the selection to the click point and moves the caret there, as in
  any GTK text view. Ctrl+click and Alt+click never follow.
- The reading caret follows the editor's place. `blocks VAULT NOTE` (CLI) lists the
  rendered note's top-level blocks (the children of cmark's document node) in document
  order as `[{"line", "offset"}]`: `line` is cmark's start line of the block plus the
  number of frontmatter lines removed, so it is a 1-based line of the note's file;
  `offset` is the code point offset in the rendered `text` where that block's rendering
  starts. A note that is not valid UTF-8 is exit 2 `refused: <reason>`. Entering reading
  view (Ctrl+E) places the reading caret at the `offset` of the last block whose `line` is
  less than or equal to the editor caret's line (1-based), or at 0 if there is none, and
  scrolls the reading view so the caret is visible. Opening a note while in reading view
  places the reading caret the same way from the editor caret that the U1/U2/U3 rules
  placed for that action (for example the heading line when following a heading). This
  replaces U3's "caret at the start of the text". Leaving reading view still restores the
  editor caret where it was.

### Rename keeps the caret on the same text

After a rename (F2), the editor caret stays before the same character of the open note's
text. A rewritten link in the open note that ends at or before the caret moves the caret by
its change in length; a caret strictly inside a rewritten link (after its first character
and before its end) is placed at the start of the rewritten link; links after the caret do
not move it. This replaces U2's "with the caret at the same position".

### Search stays within a line

A search match lies within one line's text, which (as in U2) excludes the line's `\n` and
a final `\r` (the `\r` immediately before the `\n`, or the last character of the file).
A query containing `\n` therefore matches nothing, and a `\r` in a query can match only a
`\r` inside a line's text. Everything else in U2's search rules is unchanged.

### Package build directory

`packaging/build-deb.sh` creates its temporary directory under `$TMPDIR` when `TMPDIR`
is set, non-empty, names an existing directory and is outside the source tree; otherwise
under `/tmp`. All other U3 packaging rules are unchanged.

## U5: Markdown links, block references, NFC names

U5 adds these to U1–U4; everything above stays in force except where a rule below replaces
it. The project version is `0.5.0` (wherever U4 names `0.4.0` as the project or package
version, read `0.5.0`; the metainfo keeps its earlier release entries and adds 0.5.0).

### Markdown note links

A Markdown note link is `[TEXT](DEST)` on one line where every character is prose (the
mask U1/U2 use for wikilinks and tags: outside fenced code blocks and matched inline code
spans), no character overlaps a wikilink, and:

- the `[` is not preceded by `!` (images are never note links) or by `\`;
- `TEXT` contains no `[`, `]`, `\r` or newline (it may be empty);
- `DEST` is either `<` + characters other than `<`, `>`, `\r` and newline + `>`, or a
  non-empty run of characters other than space, tab, `(`, `)`, `<`, `\r` and newline;
  nothing else may appear between `(` and `)` (a link title makes it not a note link);
- `DEST` is local: it does not start with a URI scheme (`[A-Za-z][A-Za-z0-9+.-]*:`) or `//`;
- `DEST` (without its `<>`) is split at its first `#` into `PATH` and `HEADING`; each is
  percent-decoded (`%XX` with two hex digits becomes that byte; a `%` not followed by two
  hex digits stays literal; `+` is not special) and the results must be valid UTF-8, else
  it is not a note link. `PATH` may be empty only when there is a `#` (a link to a heading
  in the same note). `HEADING` is trimmed of spaces; a `#` with nothing after it gives an
  empty heading, which is treated like no heading when following.

Scanning is left to right; a recognized link's characters are not scanned again; after a
`[` that does not start a link, scanning continues at the next character.
`mdlinks VAULT NOTE` (CLI) lists them in document order as
`{"raw", "text", "path", "heading", "line", "col", "resolved"}` (`heading` `null` when there
is no `#`; `line`/`col` as for wikilinks; `resolved` as below). `links` still lists only
wikilinks, unchanged.

Resolution of `PATH` from source note S (directory D):

1. Empty `PATH`: S itself.
2. A leading `/` is removed and the rest is taken from the vault root only (step 4).
3. Relative: join D and `PATH`, collapse `.`, `..` and empty segments; if that would leave the
   vault, skip to step 4. Candidates, in order: the joined path; the joined path + `.md`
   when it does not already end in `.md` (case-insensitive).
4. From the vault root: `PATH` itself, then `PATH` + `.md` (same condition), with `.`,
   `..` and empty segments collapsed; a path that would leave the vault has no candidate.
5. The first candidate that names a vault file (non-hidden, non-symlink regular file; a
   note or an attachment) wins. Names are compared case-insensitively after NFC (below);
   among several files matching one candidate, an exact byte match wins, then byte order.
6. No candidate: unresolved.

Markdown note links behave like wikilinks everywhere else:

- **Following** (Alt+Enter, Ctrl+click, reading-view Enter/click): as U1, with HEADING as
  the heading; the caret is on a Markdown link by the U1 rule over its `raw`. Following an
  unresolved one creates the note, by the U1 creation rules, at the step-3 joined path when
  that stays inside the vault and otherwise at the step-4 path (one trailing `.md`
  stripped, `.md` appended), and opens it. Attachment links show `Not a note: <path>`.
- **Highlighting** in the editor: the U2 link colors over the whole `raw`.
- **Backlinks** (U2) include them, with `raw` being the Markdown source.
- **Rename** (U2) keeps the invariant for them too. A rewritten Markdown link keeps `TEXT`,
  its `#HEADING` (re-encoded) and its `<...>` form if it had one; its new `PATH` is the
  relative path from the source's (new) directory to the file (`../` as needed; with a
  leading `/` and the vault path instead when the old `PATH` started with `/`), with `.md`
  kept if the old `PATH` ended in `.md` (case-insensitive) or the file is not a note, and
  dropped otherwise. `%` is always encoded, and `#` in the path; outside `<...>` also
  space, `(`, `)`, `<` and `>` (as `%20` etc., upper-case hex). Nothing else is encoded. If the
  rewritten link would not resolve to the intended file, the rename is refused (U2).
- **Reading view** (U3 rule 1): each Markdown note link is replaced by a placeholder
  before parsing, like a wikilink. Display text: `TEXT` as written if non-empty (no
  Markdown inside it is interpreted), else the file name of the resolved file without
  `.md`, else `PATH`'s last segment without `.md`, else the source note's name. Images and
  non-local links still render as U3 `url` spans and are not followable.

### Block references

A link whose heading starts with `^` (`[[N#^id]]`, `[x](N.md#^id)`) is a block reference
to the id after the `^` (trimmed). Following it places the caret at the start of the first
line of the target note, outside fenced code blocks, whose text (without a trailing `\r`
and trailing spaces or tabs) ends with a space or tab followed by `^id`, compared
case-insensitively, where id is one or more ASCII letters, digits or `-`. If there is no
such line, the caret goes to the start of the note. In reading view the reading caret then
follows U4's block rule from that line.

### NFC names

Everywhere names or paths are compared after case folding (resolution, creation's
"already resolves", quick switcher ranking, rename collision checks, tags), both sides are
first normalized to NFC (`g_utf8_normalize` with `G_NORMALIZE_NFC`) and then case folded,
so a note saved by macOS in decomposed form resolves and ranks like its composed name.
Paths written to disk keep the bytes the user or link gave them. Search (U2/U4) and
display text are unchanged.

## U6: tags, search options, folder and attachment rename, unlinked mentions

U6 adds these to U1–U5; everything above stays in force except where a rule below replaces
it. The project version is `0.6.0` (wherever U5 names `0.5.0` as the project or package
version, read `0.6.0`; the metainfo keeps its earlier release entries and adds 0.6.0).

### Tags

- Frontmatter: a line starting (column 1) with `tag:` declares tags exactly as `tags:`
  does (all three forms). Other YAML forms stay ignored.
- Parent tags: `tags` also lists every ancestor of a nested tag (`a/b/c` lists `a/b` and
  `a`) even if it never occurs on its own. A tag's `count` is the number of notes that
  contain it or any tag nested under it (`a` counts notes with `a`, `a/b`, `a/b/c`...).
  An ancestor that never occurs on its own takes its display form from the display form
  of the first tag (by U2's display order) nested under it, cut at that level. Ordering
  is unchanged (folded tag, then display form). The GUI Tags tab shows the same list.
- Renaming a tag: `retag VAULT OLD NEW` (a leading `#` is ignored in both; both must be
  valid tags) rewrites, in every note, every inline occurrence and every frontmatter item
  whose tag equals OLD or is nested under it (compared after folding), replacing the OLD
  prefix by NEW and keeping the rest (`#old/x` → `#new/x`). Only the tag text changes:
  `#`, quotes, list punctuation and all other bytes are kept; notes without a change are
  not written; changed notes use the U1 atomic save. Output
  `{"from": OLD, "to": NEW, "updated": [paths, sorted]}` (OLD and NEW without a leading `#`,
  as given otherwise). Refused (exit 2, nothing
  written): OLD or NEW invalid, OLD occurs nowhere, or NEW is nested under OLD.
- GUI: F2 while the Tags tab has focus on a tag row opens a Rename Tag dialog with the
  tag's display form selected; Enter saves the open note first (a refused save refuses
  the rename), renames, reloads the open note if it changed (caret kept as U4's rename
  rule would, using the rewritten tags), refreshes the Tags tab and puts keyboard focus
  back in the editor (or reading view). A refusal shows
  `Rename refused: <reason>` in the statusbar. Escape cancels.

### Search options

- `find VAULT QUERY [--regex] [--word]` (options in any order after QUERY). `--regex`:
  QUERY is a GLib regular expression (PCRE syntax) matched case-insensitively against each
  line's text (U4 lines); an invalid expression is exit 2 `refused: <reason>`; empty matches
  are skipped; matches are non-overlapping, left to right. `--word`: a match counts only if
  the character before it and the character after it (if any) are not letters, digits or
  `_` (`g_unichar_isalnum`); a rejected candidate consumes nothing and the next attempt
  starts one character after its start (plain or regex). Accepted matches do not overlap;
  the next attempt starts at the end of an accepted match (one character later for an
  empty regex match, which is itself never reported). Columns, ordering and the 500 cap are
  as in U2, and options never change the plain-query rules (case-insensitive by
  per-code-point lowering, U4 line bounds).
- GUI: the Search dialog has two check buttons, `Regular expression` (Alt+R) and
  `Whole word` (Alt+W), off when the dialog opens; toggling them updates the results. An
  invalid expression shows no results and the dialog's statusbar-like label
  `Invalid expression`.

### Renaming folders and attachments

- `rename VAULT OLD NEW` also accepts OLD naming a non-hidden directory or an attachment
  (a non-note vault file). For a directory, NEW is the new directory path (creation's
  segment rules, no `.md` handling) and every file under OLD moves with it; for an
  attachment, NEW is its new vault path including any extension (it may have none;
  Q291). The U2 rename invariant
  holds for every moved file (links that resolved to a moved file resolve to its new
  path; unresolved links stay byte-identical; only links that would break are rewritten,
  in their own syntax: U2 for wikilinks, U5 for Markdown links). Refused as in U2, plus:
  NEW inside OLD, NEW exists (after folding, for any path), OLD is the vault root, or any
  file under OLD is a symlink or not UTF-8 when it is a note. Output as U2 with `updated`
  listing changed notes by their final paths.
- GUI: the notes tree also lists attachments (non-note vault files) under their folders,
  after the notes. Activating an attachment shows `Not a note: <path>`. F2 while the tree
  has focus renames the selected row (note, folder or attachment) through the same dialog
  (prefilled with its path without `.md` for notes, the full path otherwise). Enter saves
  the open note first (a refused save refuses the rename), renames, refreshes tree, tags
  and backlinks, and reopens the open note at its final path (it may have moved or had
  links rewritten) with the caret kept by U4's rule and keyboard focus back in the editor
  (or reading view); a refusal shows
  `Rename refused: <reason>` and changes nothing.

### Keyboard access to the sidebar

- Ctrl+Shift+E shows the Notes tab and focuses the notes tree with the open note's row
  selected (the first row when no note is open). Ctrl+Shift+T shows the Tags tab and focuses
  the tag list with the first row selected. Arrow keys move the selection; Enter activates
  the selected row as a double-click does; F2 renames as above.

### Unlinked mentions

- `mentions VAULT NOTE` lists occurrences of NOTE's file name without `.md` in other
  notes' prose (U2 mask, outside frontmatter, not inside a wikilink or Markdown note link),
  matched case-insensitively (U2 search lowering, per code point) as a whole word (the
  `--word` rule), in every other note that is valid UTF-8, whether or not it also links to
  NOTE. Occurrences are found left to right without overlap; a candidate that is rejected
  (not a whole word, or not all prose) consumes nothing and the search goes on one
  character after its start. `text` is the line's text
  (U4). Output `[{"source", "line", "col", "text"}]` ordered by source path (byte order),
  line, column. NOTE must be a note (exit 2 otherwise); a NOTE that is not UTF-8 has none.
- GUI: under the Backlinks list, a second list `Unlinked mentions` (same columns)
  refreshed with the backlinks; Enter or double-click opens the source at the mention.
  Ctrl+Shift+M focuses it with the first row selected.

### Usability (from testing 0.5.0 on a real LCOS 1.0 install)

- **New Note.** The File menu's first item is `New Note… (Ctrl+N)`. Ctrl+N works in the
  editor and in reading view. It opens a modal `New Note` dialog with the label
  `Name or path, for example Projects/Idea`, an entry, and `Cancel` and `Create` buttons;
  `Create` is the default (Enter), Escape cancels. Create saves the open note first (a
  refused save refuses the creation and keeps the dialog's text out of the vault), then
  treats the text exactly as the quick switcher's create does (U1): if it already resolves
  to a note, that note opens and nothing is created; a refusal shows the U1 creation
  refusal in the statusbar.
- **Quick switcher.** Above the entry a label reads
  `Open a note by name or path. Ctrl+Shift+F searches note contents.` When the query is
  not empty and does not already resolve to a note (U1's creation check), the result list
  ends with one extra row `Create "QUERY"` (QUERY as typed). It is selectable like any
  row; activating it creates and opens the note exactly as U1's Enter-with-no-match does.
  With no matching notes it is the only row and is selected, so Enter still creates.
  Enter on a matching note still opens that note.
- **New notes open for writing.** Whenever the app creates a note (New Note, the
  switcher's create, following a link to a missing note from the editor or from reading
  view), it leaves reading view if it was on (the mode stays off for later notes, U4),
  puts the editor caret at the end of the new note and gives the editor keyboard focus,
  so typing goes straight into the note. Opening an existing note keeps U4's sticky mode.
- **Menus show every command.** The Go menu lists `Quick Switcher (Ctrl+O)`,
  `Follow Link (Alt+Enter)`, `Search Notes… (Ctrl+Shift+F)`, `Backlinks (Ctrl+Shift+B)`,
  `Notes (Ctrl+Shift+E)`, `Tags (Ctrl+Shift+T)` and `Unlinked Mentions (Ctrl+Shift+M)`,
  each doing what its key does. The View menu's `Reading View (Ctrl+E)` is a check item
  that is checked exactly while reading view is on.
- **Dialog buttons.** Every rename dialog (note, tree row, tag) has `Cancel` and `Rename`
  buttons; `Rename` is the default (Enter) and Escape cancels, as before.
- **The Tags tab keeps its state.** When the Tags tab is refreshed (opening, saving,
  creating or renaming notes, retag), every tag row that was expanded and whose tag still
  exists (compared after folding) stays expanded, and the selected row stays selected if
  the same tag row, or the same note row under the same tag, still exists.
- **A tag rename keeps the renamed rows' state** (from Lee's 0.6.0 retest, B11). After
  a tag rename from the Tags tab, a row that was expanded or selected and whose tag was OLD
  or nested under OLD (compared after folding) counts as the row of the tag with the OLD
  prefix replaced by NEW (`old/x` becomes `new/x`), so it stays expanded, or selected,
  when that tag exists after the rename. All other rows keep their state by the rule above,
  and the rename still puts keyboard focus back in the editor (or reading view).
- **Reading-view positions reach list items.** This replaces U4's definition of `blocks`
  (the reading-caret rule itself is unchanged: the last block whose `line` is less than or
  equal to the editor caret's line). `blocks VAULT NOTE` lists, in pre-order of cmark's
  tree, every block node except the document and list nodes: top-level blocks, list items
  at any depth, and the blocks inside list items and block quotes. Each entry's `line` is
  the node's cmark start line plus the frontmatter lines removed, and `offset` is where the
  node's rendering starts in `text`: for a list item, the start of its prefix (`• `,
  `N. `, `N) `); for a block inside an item, after the prefix or indentation. An entry
  whose `line` equals the previous entry's `line` is dropped. So following a backlink
  that points into a list lands on that list item in reading view.
- **Block IDs are hidden in reading view.** When a paragraph's last inline is text that
  ends with one or more spaces or tabs, `^` and one or more ASCII letters, digits or `-`
  (a U5 block id), that ending is not rendered: `text` ends before it and spans and links
  end at or before the new end. Everything else in the paragraph renders as before.

### User documentation

- README.md states `Version 0.6.0.` and its LCOS install steps run `sudo apt update`
  before `sudo apt install ./lcos-notes_0.6.0_amd64.deb` (a fresh LCOS 1.0 install has no
  package lists). DOCUMENTATION.md begins `This guide covers version 0.6.0.` and documents
  every U6 feature: `retag`, `find` `--regex`/`--word`, folder and attachment rename,
  `mentions`, the sidebar keys Ctrl+Shift+E/T/M, the Search dialog's `Regular expression`
  and `Whole word` options and the `Unlinked mentions` list; its "Not supported yet" list
  drops what U6 delivers, and it describes New Note (Ctrl+N) and the switcher's
  `Create` row. The CLI man page documents `retag`, `mentions` and the `find` options.

## Out of scope (tracked in `BACKLOG.md`)

Markdown links with titles, reference-style links, NFC in search (U5 covers inline
Markdown note links, block references and NFC names), file watching, attachments viewing, settings dialog,
daily notes, graph view, multiple windows. Also out of scope from U3: following images and non-local links, embedding
(transcluding) notes, GitHub-flavored Markdown extensions (tables, task lists,
strikethrough), rendering attachments, repository publishing and signing of packages.
