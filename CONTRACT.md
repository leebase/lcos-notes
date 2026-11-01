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

## Out of scope (tracked in `BACKLOG.md`)

Markdown-style links
`[x](y.md)`, block-reference jumping, file watching, attachments viewing, settings dialog,
daily notes, graph view, Unicode NFC normalization, multiple windows. Also out of scope from U3: following Markdown links and images, embedding
(transcluding) notes, GitHub-flavored Markdown extensions (tables, task lists,
strikethrough), rendering attachments, repository publishing and signing of packages.
