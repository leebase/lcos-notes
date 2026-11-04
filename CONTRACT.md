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

## U7: GitHub-flavored Markdown, task checkboxes, reloading changed files

U7 adds these to U1–U6; everything above stays in force except where a rule below replaces
it. The project version is `0.7.0` (wherever U6 names `0.6.0` as the project or package
version, read `0.7.0`; the metainfo keeps its earlier release entries and adds 0.7.0).

### Parser

- The Markdown parser is the system cmark-gfm (`libcmark-gfm` and
  `libcmark-gfm-extensions`, pkg-config version >= 0.29.0; the reference and the supported
  LCOS build use 0.29.0.gfm.13, Devuan Excalibur's). It replaces cmark everywhere U3–U6
  say "cmark": the program no longer links `libcmark`. Every parse attaches exactly the
  `table`, `tasklist` and `strikethrough` extensions with the option
  `CMARK_OPT_STRIKETHROUGH_DOUBLE_TILDE` and no other option (no autolinks, footnotes or
  tag filter). Wikilink placeholders, frontmatter removal and every U3–U6 rendering rule
  are unchanged; a document with no table, task item or `~~` renders exactly as in U6.
- Because wikilinks are replaced by placeholders before parsing, a `|` inside a wikilink
  (`[[Note|alias]]`) never splits a table cell.

### Rendering the extensions

These extend U3's block and inline rules (`text`, `spans`, `links`, `blocks`):

- **Strikethrough.** `~~text~~` → its content, span `strike`. A single `~` is literal.
- **Task items.** An item is a task item exactly when cmark-gfm's `tasklist` extension
  makes it one (for example `- [ ] a`, `* [x] b`, `3. [X] c`; in 0.29.0.gfm.13 not inside
  a block quote). Its *marker* is the first `[` on the item's start line at or after the
  item's start column (cmark byte column), with the next two characters. The item is
  *checked* when the character after that `[` is `x` or `X` — not cmark-gfm's own checked
  flag, which 0.29.0.gfm.13 also sets when `[x]` occurs later on the line.
  - In a bullet list the item prefix is `☐ ` (U+2610 and a space) when unchecked or `☑ `
    (U+2611 and a space) when checked, instead of `• `. In an ordered list it is `N. ☐ `
    or `N) ☑ ` (U3's number and delimiter, then the box). Indentation of later lines uses
    the prefix's code point count, as in U3.
  - Span `task` covers the box character. For a checked item, span `done` covers the
    rendering of the item's first child block (after the prefix).
- **Tables.** A table renders as one line per row: the header row, then a rule line, then
  each body row, joined by `\n`. Every row has the header's number of cells (cmark-gfm adds
  empty cells and drops extra ones). A cell's text is its inlines rendered by U3's inline
  rules. Column *width* is the largest cell text length in that column (code points), at
  least 1. Each cell is padded with spaces to the width by its column's alignment: right
  (`--:`) pads on the left; center (`:-:`) puts half the padding (rounded down) on the
  left and the rest on the right; left or none pads on the right. Cells are joined by
  ` │ ` (space, U+2502, space). The rule line is, per column, width × `─` (U+2500), joined
  by `─┼─` (U+2500 U+253C U+2500). Spans and links inside a cell move with its text.
  Span `th` covers each header cell's text (not its padding); span `table` covers the
  whole table.
- **blocks.** A table is listed like any block, and so is each table row (the header row
  and each body row; the rule line has none); a row's `offset` is the start of its line in
  `text`. Table cells are not listed. U6's rule still drops an entry whose `line` equals
  the previous entry's `line`. Task items are list items (offset at the prefix start).
- `tasks VAULT NOTE` (CLI) lists the note's task items in document order as
  `[{"line", "col", "checked", "offset"}]`: `line` and `col` are the 1-based line of the
  note's file and code point column of the marker's `[`; `checked` as defined above;
  `offset` is the code point offset of the box character in the rendered `text`. A note
  that is not valid UTF-8 is exit 2 `refused: <reason>`.

### Reading view

- Styles: `strike` is struck through; `task` is shown in the U2 link color (#205ca8);
  `done` is struck through and dimmed; `table` is monospace; `th` is bold.
- **Toggling a task.** In reading view, Space while the caret is on a box (`offset <=
  caret < offset + 1`), or a plain left click on a box, toggles that task: in the buffer the
  character after the marker's `[` becomes `x` if it was a space, or a space if it was `x`
  or `X`; nothing else in the buffer changes. Then the note is saved exactly as Ctrl+S
  saves it (U1, including the `Changed on disk; not saved` refusal, which keeps the
  toggled buffer). The reading view shows the new rendering with the caret at the same
  offset and keeps keyboard focus. This is the one edit reading view makes; every other
  U3 read-only rule stands. Space elsewhere in reading view does nothing.

### Reloading files changed on disk

"Changed by another program" means any change to the vault on disk not made by this app
instance; the app's own saves, creations and renames never count and never trigger
anything below.

- **The open note.** When the open note's file is changed by another program and the
  buffer has no unsaved changes, the app reloads it within 2 seconds: the buffer becomes
  the file's new text, unmodified, and Undo cannot bring back the old text. The editor
  caret keeps its line and column (1-based, code points), clamped to the last line and that
  line's length; in reading view the reading caret is placed from it by U4's rule. The
  statusbar shows `Reloaded: changed on disk`. A file that is no longer valid UTF-8 is not
  loaded: the buffer is kept and the statusbar shows the U1 open refusal.
- With unsaved changes the buffer is kept and the statusbar shows
  `Changed on disk; your unsaved edits are kept`. **File > Reload from Disk**
  (Ctrl+Shift+R) replaces the buffer with the file's text (unmodified, no confirmation,
  caret kept as above), whether or not the buffer was modified; it is how a user leaves the
  U1 `Changed on disk; not saved` state.
- When the open note's file is deleted or renamed by another program, the buffer is kept
  and becomes modified, and the statusbar shows `Deleted on disk`. Ctrl+S then writes it
  back at its path (U1's changed-on-disk check now expects no file there, so it refuses
  only if a file has appeared at that path since).
- **The vault.** When another program creates, deletes, renames or changes a note,
  attachment or folder in the vault, within 2 seconds the notes tree, the Tags tab, the
  Backlinks pane and the Unlinked mentions list show the new state, as they would after
  reopening the vault. The Tags tab keeps its state by U6's rules, and the notes tree keeps
  its expanded folders and selection the same way (a folder or file row that still exists
  stays expanded or selected).

### Install and package

The build dependencies name the `-dev` packages of cmark-gfm and its extensions
(`libcmark-gfm-dev`, `libcmark-gfm-extensions-dev` on Debian-family hosts) instead of
cmark's. The package's `Depends`, still from `dpkg-shlibdeps`, therefore names the
cmark-gfm libraries (on Devuan Excalibur `libcmark-gfm0.29.0.gfm.13` and
`libcmark-gfm-extensions0.29.0.gfm.13`) and no longer `libcmark0.30.2`.

### User documentation

README.md states `Version 0.7.0.` and names the libraries `apt` fetches (the two cmark-gfm
libraries) and the new build dependencies. DOCUMENTATION.md begins
`This guide covers version 0.7.0.` and documents tables, task lists and toggling them in
reading view (Space or click), strikethrough, reloading changed files, File > Reload from
Disk (Ctrl+Shift+R) and the `tasks` command; its "Not supported yet" list drops what U7
delivers and mentions that task items inside block quotes are not recognized. The CLI man
page documents `tasks`.

## U8: embeds, highlights and callouts

U8 adds these to U1–U7; everything above stays in force except where a rule below replaces
it. The project version is `0.8.0` (wherever U7 names `0.7.0` as the project or package
version). No new runtime library is added (images are loaded with GdkPixbuf, which GTK
already brings). Designs: SECOND-BRAIN.md D1, D2 and D4.

### Highlights

A highlight is Obsidian's `==text==`. It is found on cmark's tree, after parsing (U3 rule
1), never inside literal text:

- Take every maximal run of consecutive `text` nodes that are siblings (children of the
  same paragraph, heading, table cell, emphasis, strong, link, image or strikethrough
  node). Concatenate their literals into one string S (placeholders included; each is one
  character). A soft break, line break, code span, raw HTML or any other inline node ends
  a run, so a highlight never crosses one.
- Scan S from left to right. At a position i where S has `==`, an opening delimiter needs a
  character at i+2 that is neither whitespace (`g_unichar_isspace`) nor `=`. Its closing
  delimiter is the first `==` at a position j ≥ i+3 whose preceding character (j−1) is
  not whitespace. If there is one, S[i+2, j) is a highlight and scanning continues at j+2;
  otherwise the scan continues at i+1. Highlights never nest, and a backslash does not
  escape `=` here (cmark has already removed it).
- The delimiters are not rendered. The highlight's text renders by rule 3 (placeholders
  become links) with the span `highlight` over it.

CLI: `highlights VAULT NOTE` → `[{"start", "end", "text"}]`, one entry per `highlight`
span of the note's rendering, in order (embedded content included), with `text` the
rendered text of the span. A note that is not valid UTF-8 is exit 2 `refused: <reason>`.

### Callouts

A block quote is a *callout* when its first child is a paragraph whose *head* (its inline
children before its first soft or line break, all of them if there is none), rendered by
rule 3 into the text H, matches `^\[!([A-Za-z0-9_-]+)\]([+-]?)(?:[ \t]+(.*))?$` (Python
`re.fullmatch` semantics on H) with no span or link of the head starting before the end of
the match's group 2. Then:

- TYPE is group 1; the *kind* is TYPE in ASCII lower case if it is one of `note`, `tip`,
  `warning`, `danger`, `question`, `quote`, and `note` otherwise. The title T is group 3
  with its spans and links (shifted); when group 3 is absent or empty, T is TYPE with its
  first character in ASCII upper case and the rest in ASCII lower case, with no spans.
- The *body* is the rest of the first paragraph (its inline children after the first
  break, which is dropped, rendered by rule 3) as one block, if not empty, followed by
  the block quote's other children; body blocks are joined by `\n\n` as in a block quote.
- The callout renders as T, then `\n` and the body if the body is not empty. Spans:
  `callout-<kind>` over the whole callout, `callout-title` over T, and, when group 2 is
  `-`, `folded` from the end of T to the end of the callout (when the body is not empty).
  A callout has no `quote` span.
- `blocks` entries are made as for a block quote: the first paragraph's entry is at the
  callout's start, and each other child has its own entry.
- U6's block-ID rule applies to the first paragraph's last part: the title when the
  paragraph has no break, otherwise the rest of the paragraph.

Any other block quote renders as before.

### Embeds

A paragraph whose inline content is exactly one placeholder (cmark gives one `text` node
whose literal, without leading or trailing whitespace, is that one character) for a U1
wikilink with `embed: true` is an *embed paragraph*. Markdown images and embeds that share
a paragraph with other text are not embed paragraphs; they render as before. An embed
paragraph renders by the first rule that applies:

1. The link is unresolved, or resolves to a file that is neither a note nor an image →
   as before (rule 4).
2. It resolves to an image, a file whose name ends in `.png`, `.jpg`, `.jpeg`, `.gif`,
   `.bmp` or `.webp` (ASCII case-insensitive) → one U+FFFC character with the span
   `image`, and an entry `{"offset", "path"}` (its offset in `text`, the vault-relative
   path) in the render's `images` array. It adds no `links` entry.
3. It resolves to a note N that is on the *embed stack* (the note being rendered, plus
   every note whose embedding is being rendered around this paragraph), or the paragraph
   is inside content embedded three levels deep → as before (rule 4).
4. N's file is not valid UTF-8 → as before (rule 4).
5. Otherwise N's text is parsed exactly like a note being rendered (its own links,
   placeholders and frontmatter removal, U1–U7 rules) and a part of its document is
   selected:
   - no heading (absent or empty after trimming): all of N's top-level blocks;
   - a heading starting with `^` (a U5 block reference): find the line L by the U5
     block-reference rule; the part is the last node, in the pre-order of U6's `blocks`
     (every block node except the document and list nodes), whose start line ≤ L ≤ end
     line (cmark's end line);
   - any other heading: find the line L by U1's heading rule (the first ATX heading line
     whose text equals the heading after case folding); the part is the top-level
     heading node that starts on L and every top-level block after it up to, not
     including, the next top-level heading node of the same or a lower level number.
   If no part is found (no such line, or the line is not where such a node starts), or
   the selected part renders to an empty text, the paragraph renders as before (rule 4).
   Otherwise the paragraph renders as the part's blocks, rendered from N (links resolve
   from N; the source name for empty targets is N's), joined by `\n\n`, with N pushed on
   the embed stack and one more level of depth, and the span `embed` over the result.
   Embedded content adds no `blocks` entries (the embed paragraph keeps its own) and no
   `tasks` entries, and its `task` spans are dropped (its boxes and `done` spans stay).
   Its links, spans and images are kept.

`render` gains `"images": [{"offset", "path"}, ...]` (in rendered order; `[]` when there
are none) after `links`. `blocks`, `tasks` and `highlights` use the same rendering.

### Reading view

- Styles: `highlight` has the background #FFE066. A callout has a background by kind: note
  #E3EEFB, tip #E2F5E7, warning #FFF1D6, danger #FBE2E2, question #EFE6FA, quote #EEEEEE;
  `callout-title` is bold. `embed` has a left margin of 24 px more than its surroundings.
  These replace the theme's colors only where they apply.
- An `image` character shows the image file, loaded with GdkPixbuf, scaled down (never
  up), keeping its aspect ratio, to fit the reading view's width inside its margins. A file
  GdkPixbuf cannot load shows `[image: <path>]` in the U2 unresolved color instead. The
  image counts as one character, so every rendered offset is unchanged.
- `folded` text is hidden. A plain left click on a folded callout's title (one that puts
  the reading caret at an offset from the title's start to its end, inclusive) shows its
  body, and a second such click hides it again. The folded state is not saved; re-rendering (opening
  a note, saving, a change on disk) folds it again.
- Links in embedded content are followed like any reading-view link.
- When any note in the vault changes on disk (U7), the reading view re-renders within 2
  seconds, so embedded content follows its source, keeping the reading caret's offset
  (clamped to the new text).

### Editing highlights

- Edit > Highlight (Ctrl+Shift+H), in the editor: with a selection, if the two characters
  before it and the two after it are both `==`, they are removed (unwrap); otherwise `==`
  is inserted before and after it (wrap). Afterwards the same text is selected. With no
  selection, `====` is inserted and the caret placed between the two pairs. Each use is one
  undo step. In reading view it does nothing.
- View > Highlights… (Ctrl+Shift+Y) opens a modal `Highlights` dialog listing the open
  note's highlights (`highlights` rule, the current buffer) as one row each, showing its
  text; the first row is selected. With no highlights the list is empty and a label reads
  `No highlights in this note`. Enter or a double-click on a row closes the dialog, turns
  reading view on if it was off, and places the reading caret at the highlight's `start`
  with keyboard focus in the reading view. Escape closes it.

### User documentation

README.md states `Version 0.8.0.`; DOCUMENTATION.md begins `This guide covers version
0.8.0.` and documents highlights (including Edit > Highlight and View > Highlights…),
callouts (types, titles, folding), embeds of notes, headings, blocks and images (the depth
limit and cycles render as links), and the `highlights` command; its "Not supported yet"
list drops what U8 delivers and mentions Markdown image embeds (`![alt](file.png)`) and
PDF embeds. The CLI man page documents `highlights` and the `images` field of `render`.

## U9: daily notes, templates, quick capture, timestamp names

U9 adds these to U1–U8; everything above stays in force. Version 0.9.0. The designs are
in SECOND-BRAIN.md (C1–C4); this section is the contract.

### The clock

Every rule below that needs "now" reads one clock: the local date and time, or, when
the environment variable `LCOS_NOTES_NOW` is set, its value, which must be exactly
`YYYY-MM-DDTHH:MM:SS` (a valid date from 1900-01-01 to 2099-12-31 and time; local time).
With an invalid value the CLI refuses every U9 command (`refused: invalid LCOS_NOTES_NOW`)
and the GUI uses the real clock.

### Date formats

A *format* is a string of tokens (a subset of moment.js, as Obsidian uses). Scanning left
to right: `[` starts a literal that runs to the next `]` (both brackets dropped, the text
between them copied); otherwise the longest token below that starts here is used, trying
them in this order: `YYYY`, `YY`, `MMMM`, `MMM`, `MM`, `M`, `DDDD`, `DD`, `D`, `dddd`, `ddd`,
`HH`, `H`, `mm`, `ss`; otherwise an ASCII letter makes the format *unsupported*, and any
other character is copied. A `[` with no later `]` makes the format unsupported. Formatting
a date and time:

| Token | Output | Token | Output |
|---|---|---|---|
| `YYYY` | year, 4 digits | `DDDD` | day of the year, 3 digits (001–366) |
| `YY` | year mod 100, 2 digits | `DD` / `D` | day of the month, 2 digits / no padding |
| `MMMM` | `January` … `December` | `dddd` | `Sunday` … `Saturday` |
| `MMM` | `Jan` … `Dec` | `ddd` | `Sun` … `Sat` |
| `MM` / `M` | month, 2 digits / no padding | `HH` / `H` | hour 0–23, 2 digits / no padding |
| `mm` | minute, 2 digits | `ss` | second, 2 digits |

Names are English. Dates are proleptic Gregorian.

### Obsidian settings

Settings are read, never written, from JSON files in the vault's `.obsidian` folder:
`daily-notes.json`, `templates.json` and `zk-prefixer.json`. A file is used only if it is a
regular file (not a symlink), valid UTF-8 and valid JSON (RFC 8259) whose top level is an
object; otherwise every key takes its default. Only string values are used (for a
repeated key, the last one); a missing key or a non-string value takes its default. A
*folder* value is trimmed of spaces and `/` at both ends; empty means the vault root.

### Daily notes

Settings (`daily-notes.json`): `folder` (default: the vault root), `format` (default
`YYYY-MM-DD`; an empty or unsupported format, or one containing `HH`, `H`, `mm` or `ss`,
uses the default) and `template` (default: none).

- The daily path for date D is P(D) = folder + `/` (when the folder is not the root) +
  the format applied to D + `.md`. A `/` from the format makes subfolders.
- The daily note for D *exists* when a note's path equals P(D) after Unicode case folding
  (the first such note in byte order is the one used).
- The template value, trimmed, with one trailing `.md` removed (ASCII case-insensitive),
  is resolved as a link target from the vault root (U1). If it is empty or unresolved,
  there is no template.
- Creating the daily note for D: P(D) without `.md` must pass U1's creation rules (else
  refused with U1's reason); intermediate folders are created; the note is written
  atomically and its text is the template expanded (Templates below) with `title` the
  file name of P(D) without `.md` and the time D at the clock's time of day, or empty
  without a template. A template that is not valid UTF-8 is refused. An existing note is
  never written.
- A note is a *daily note* with date D when D is the only date from 1900-01-01 to
  2099-12-31 whose P(D) equals the note's path after case folding. (Formats that don't
  determine a date, such as `MMMM`, make no daily notes.)

CLI:
- `daily VAULT [DATE] [--create]` → `{"path", "date", "exists", "created"}`. DATE is
  `YYYY-MM-DD`, `today` (the default), `yesterday`, `tomorrow`, or `+N` / `-N` days from
  today (N of 1–5 digits); it must be from 1900-01-01 to 2099-12-31, else refused. `path`
  is the existing note's path, else P(DATE); `date` is `YYYY-MM-DD`; `exists` is whether the
  note existed before the command; `created` is whether this command created it (only
  with `--create`).
- `dailies VAULT` → array of `{"path", "date"}` for every daily note, ordered by date and
  then path.

GUI (Go menu, after the existing items):
- `Today's Note (Ctrl+D)`, in the editor or reading view: saves the open note first, as opening another note does (a
  refused save does nothing else). Then it opens today's daily note, creating it if
  needed; a refusal shows `refused: <reason>` in the statusbar. Either way, like a new note
  (U6): it leaves reading view, puts the editor caret at the end and focuses the editor.
  Ctrl+D is handled before the editor's own bindings.
- `Previous Daily Note (Alt+Left)` and `Next Daily Note (Alt+Right)`, in the editor or
  reading view: when the open note is a daily note, open the daily note with the nearest
  earlier (later) date, as opening an existing note does (sticky reading mode, caret at
  the start). They never create a note. Otherwise the statusbar shows `Not a daily note`,
  `No earlier daily note` or `No later daily note` and nothing else happens. These keys
  are handled before the editor's own bindings.

### Templates

Settings (`templates.json`): `folder` (default `Templates`; empty after trimming also means
`Templates`), `dateFormat` (default `YYYY-MM-DD`) and `timeFormat` (default `HH:mm`); an
empty or unsupported format uses the default.

- The *templates* are the notes whose path starts with the folder + `/` after case
  folding, in byte order. They stay ordinary notes (linked, tagged, searched).
- Expanding template text for a title and a time replaces, left to right and without
  rescanning the output, every match of the Python regular expression
  `\{\{[ \t]*(title|date|time)[ \t]*(?::([^}\r\n]*))?\}\}` (the name matched ASCII
  case-insensitively): `title` without a format → the title; `date` or `time` without a
  format or with an empty one → the time in `dateFormat` or `timeFormat`; `date` or `time`
  with a supported format → the time in that format. A match that is `title` with a format,
  or has an unsupported format, is left as it is, as is every other byte (line endings
  included).

CLI:
- `templates VAULT` → array of template paths.
- `template VAULT TEMPLATE TITLE` → `{"text"}`: the note TEMPLATE (any note, valid UTF-8)
  expanded for TITLE and the clock. Nothing is written.
- `create VAULT TARGET --template TEMPLATE`: U1's create; a note it creates gets the
  template expanded for its file name without `.md` and the clock. An existing note is
  opened untouched. TEMPLATE is checked first (a missing or invalid template is refused
  and nothing is created).

GUI:
- The New Note dialog gains, below the entry, a label `_Template:` (Alt+T focuses the
  drop-down) and a drop-down whose first item is `None` (selected) followed by each
  template, shown as its path after the folder + `/`, without `.md`. Up and Down on the
  focused drop-down change the selection. Enter creates wherever the focus is in the
  dialog (unless the drop-down's list is open). Create with a template selected creates as
  `create --template` does.
- Edit > `Insert Template… (Ctrl+Shift+I)`, in the editor with a note open: with no
  templates the statusbar shows `No templates in <folder>`; otherwise a modal
  `Insert Template` dialog lists the templates (shown as above), first row selected. Enter
  or a double-click closes it and inserts the template, expanded for the open note's file
  name without `.md` and the clock, at the caret (replacing a selection) as one undo step,
  with the caret after it. Escape closes it. In reading view it does nothing.

### Timestamp names

Settings (`zk-prefixer.json`): `folder` (default: the vault root) and `format` (default
`YYYYMMDDHHmm`; empty or unsupported uses the default).

- The timestamp target is folder + `/` (when not the root) + the format applied to the
  clock. If a note's path equals that target + `.md` after case folding, `-1`, `-2`, … is
  appended: the first that is free. The target must pass U1's creation rules, else refused.
- CLI: `unique VAULT` → `{"target"}`. Nothing is written.
- GUI: the New Note dialog gains a button `Timestamp _Name` (Alt+N) that sets the entry's
  text to the timestamp target and puts the caret at its end.

### Quick capture

Capturing text X at the clock time into a note whose text is C:

- X has `\r\n` replaced by `\n`, any other `\r` removed, and then spaces, tabs and
  newlines removed from both ends. If nothing is left, it is refused
  (`nothing to capture`).
- E (the line ending) is `\r\n` if C contains `\n` and its first `\n` follows `\r`, else
  `\n`. The captured block is `- HH:mm ` + the first line, then each further line as `  ` +
  the line (an empty line stays empty), each line followed by E.
- The new text is C, then E if C is not empty and does not end with `\n`, then the block.
  It is written atomically. `line` is the 1-based line number of the block's first line.
- The *target* is today's daily note (created as `daily --create` does if missing), or with
  the Inbox choice the note `Inbox.md` at the vault root (existing after case folding, else
  created empty first). A target that is not valid UTF-8 is refused.

CLI: `capture VAULT TEXT [--inbox]` → `{"path", "line", "created"}` (`created`: the
target did not exist before).

GUI: `lcos-notes --capture [--vault DIR]` opens only a capture window titled
`Capture — Notes` for DIR, else the last vault; with neither it prints
`refused: no vault` on stderr and exits 2. It does not change the last vault. The window has
a multi-line text area (focused), radio buttons `_Today's note` and `_Inbox` (Alt+T,
Alt+I), and buttons `_Cancel` and `_Capture`. Ctrl+Enter or Capture captures into the
chosen target and exits 0; if the text is empty after trimming nothing happens; a refusal
shows `refused: <reason>` in a label and the window stays. Escape or Cancel exits 0 writing
nothing. The radio choice is remembered per vault after a successful capture, in
`$XDG_STATE_HOME/lcos-notes/<vault-id>/capture` (default `~/.local/state`; `<vault-id>` is
the SHA-256 hex of the vault's real path), and preselected next time (`Today's note` the
first time).

**Captures into an open note with unsaved edits.** In the main window, when the open note
changes on disk by another program while the buffer has unsaved changes (U7), and the new
file text is B (the text last loaded or saved), then E if B is not empty and does not end
with `\n`, then one or more *capture blocks* (each: a line `- ` + two digits + `:` + two
digits, optionally followed by a space and any text, then any lines that are empty or
start with two spaces, every line ended by E, where E is taken from the new text as
above), the blocks are appended to the end of the buffer (after E when the buffer is not
empty and does not end with `\n`), the buffer stays modified, the caret and selection stay,
the new file text becomes the text last loaded, and the statusbar shows
`Captured text added; your unsaved edits are kept`. Ctrl+S then saves normally. Any other
change follows U7.

### User documentation

README.md states `Version 0.9.0.`; DOCUMENTATION.md begins `This guide covers version
0.9.0.` and documents daily notes (settings, Ctrl+D, Alt+Left/Right, `daily`, `dailies`),
templates (folder, variables, New Note's drop-down, Insert Template, `templates`,
`template`, `create --template`), timestamp names (`unique`) and quick capture (the window,
binding `lcos-notes --capture` to a keyboard shortcut in the desktop's keyboard settings,
the Inbox choice, `capture`, captures into an open note with unsaved edits), and
`LCOS_NOTES_NOW`. Its "Not supported yet" list drops daily notes. The man pages document
`--capture` and the new CLI commands.

## Out of scope (tracked in `BACKLOG.md`)

Markdown links with titles, reference-style links, NFC in search (U5 covers inline
Markdown note links, block references and NFC names), settings dialog, graph view,
multiple windows. Also out of scope for U9: non-English month and day names, moment tokens
beyond the table, Obsidian's periodic notes (weekly, monthly), the Templater plugin's
syntax, merging a template's frontmatter into an existing note, grabbing global keys. Also out of scope: following non-local links, Markdown image embeds (`![alt](file.png)`),
PDF embeds, `==` coloring in the editor, GFM autolinks and footnotes, repository publishing and signing of packages.
