# LCOS Notes user guide

This guide covers version 1.0.0. It includes the accepted U10 organization
and four agreed polish improvements. Download the LCOS package and checksums from
the [1.0.0 release](https://github.com/leebase/lcos-notes/releases/tag/v1.0.0).

For a guided introduction and task-based help, read the [LCOS Notes handbook](https://nginx.leebasehome.com/lcos-notes/) or its [Markdown source](docs/handbook/index.md).

## First session

1. Use the correct package for the version you intend to try; see [installation](README.md#download-and-install-lcos-10).
2. Start with a separate folder containing a few synthetic Markdown notes. Choose
   that folder at startup or use `lcos-notes --vault /path/to/test-notes`.
3. Create a note with Ctrl+N, save with Ctrl+S, and write a `[[link]]` to another note.
4. Use Ctrl+E to read it. Use Ctrl+O to switch notes, Ctrl+Shift+F to search content,
   and Ctrl+D to open today's daily note.
5. Before using Move, Archive or Supersede on valuable notes, keep an independent
   backup. These operations change ordinary vault files; an atomic save is not a backup.

## Optional language fonts

LCOS Notes uses installed system fonts. For Chinese, Japanese and Korean coverage, install fonts-noto-cjk.

On Devuan/LCOS, an administrator can install the optional package:

```sh
sudo apt update
sudo apt install --no-install-recommends fonts-noto-cjk
fc-cache -f
```

Close and reopen Notes after adding fonts. This is optional operating-system
coverage, not a mandatory Notes dependency. If administrative installation is not
available, regular fonts from the same package can be installed for your account
under `~/.local/share/fonts/`, followed by `fc-cache -f`. The live LCOS acceptance
check used this standard per-user route without changing Notes or the system
package database. Do not run these Linux package commands on macOS.

To check for a font covering 猫 (U+732B):

```sh
fc-list ':charset=732b' family
```

An empty result means no installed font advertises that glyph. `fc-match sans`
alone does not prove coverage. A box labeled 732B can indicate missing system font
coverage even when the note's UTF-8 text and other characters are intact.

## Vaults and notes

A **vault** is any folder. Every file ending in `.md` (lower case) anywhere inside it
is a **note**. Other files, such as images and PDFs, are **attachments**. Hidden files
and folders (names starting with `.`, such as `.obsidian/`, `.trash/` and `.git/`) and
symbolic links are excluded from note traversal. Supported hidden configuration
files are read explicitly as described under daily notes and templates. An existing Obsidian vault works as it is:
LCOS Notes never writes into `.obsidian/` or adds hidden application metadata to the vault.
User-requested note creation and capture still create ordinary Markdown files.

Notes are plain UTF-8 text. LCOS Notes saves exactly what you typed: it keeps
Windows line endings (CRLF) if the file had them, and adds or removes no final
newline. A note that is not valid UTF-8 can't be edited and is skipped by search,
tags, backlinks and rename.

The last opened vault is stored under `$XDG_CONFIG_HOME/lcos-notes/last-vault`
(default `~/.config/lcos-notes/last-vault`). Capture remembers its target under
`$XDG_STATE_HOME/lcos-notes/` (default `~/.local/state/lcos-notes/`), keyed by vault.
The app reads supported Obsidian daily-note/template/timestamp settings without
writing those hidden files. Use an independent backup for your Markdown vault.

## Starting

```sh
lcos-notes                          # last vault, or a folder chooser the first time
lcos-notes --vault ~/Notes          # a specific vault
lcos-notes --vault ~/Notes Home.md  # a vault and a note (path inside the vault)
```

The window has a menubar (File, Edit, View, Go, Help), the **Notes**, **Tags** and **Outline**
tabs on the left, the editor in the middle, **Backlinks** on the right and a
statusbar showing `Ln N, Col M`. The title shows the note's name, with ` *` while it
has unsaved changes. The window sizes itself to fit your screen; 1024×768 works.

## Editing and saving

- **Ctrl+S** saves. Opening another note and closing the window also save first.
- Saving is safe. The note is written to a temporary file next to it and then
  atomically renamed into place, so a crash never leaves a half-written note. An
  unchanged note is never rewritten.
- If a note was changed on disk by another program since you opened it, LCOS Notes
  will not overwrite it. The statusbar says `Changed on disk; not saved`, your text
  stays in the editor, and closing the window asks whether to discard your changes.
- Undo and redo work within the note you are editing. Opening a note starts a fresh
  undo history, so Undo can never bring back another note's text.

## Links

Write a link to another note as `[[Note name]]`:

| You write | Meaning |
|---|---|
| `[[Ideas]]` | the note named `Ideas.md`, wherever it is in the vault |
| `[[Projects/Alpha]]` | a note by (partial) path |
| `[[Ideas#Plan]]` | a heading inside a note |
| `[[Ideas\|shown text]]` | a link that shows different text in the reading view |
| `[[#Plan]]` | a heading in the current note |
| `![[diagram.png]]` | an embed; it is followed like a link |

Names match case-insensitively after Unicode NFC normalization. When several notes share a name, the one in the
same folder wins, then the one with the shortest path. Links inside code (fenced
blocks and `inline code`) are not links.

In the editor, links are underlined: **blue** when the note exists, **rust red**
when it doesn't yet. To follow a link:

- **Alt+Enter** with the caret inside the link, or **Ctrl+click** on it.
- Following a link to a heading puts the caret on that heading.
- Following a link to a note that doesn't exist creates it (empty) and opens it,
  creating folders as needed.
- Links to attachments show `Not a note: <path>` in the statusbar.

Markdown note links also work: `[plan](Projects/Alpha.md#Plan)`,
`[block](Alpha.md#%5Eid)` and `[same note](#Heading)`. Destinations can use percent
escapes (UTF-8 bytes); `+` stays literal. Use `<...>` around a destination containing
spaces, for example `[plan](<My Plan.md>)`. Titles, reference-style links, images,
URI schemes and `//` destinations are not followable note links.

Markdown paths try the source folder first and then the vault root, trying the
path as written and then with `.md` appended. A leading `/` uses only the vault
root. `.` and `..` segments are collapsed; a path cannot escape the vault. If a
Markdown link is missing, following creates the note at that relative path (or
the root path when the relative path would leave the vault), using the ordinary
note-name restrictions. Backlinks and highlighting include both kinds of links.

A heading beginning with `^` is a block reference: `[[Ideas#^item-1]]` jumps to
the first line ending with ` ^item-1` (or a tab before the marker), ignoring
trailing spaces/tabs and fenced code. IDs contain ASCII letters, digits and `-`,
matched case-insensitively. A missing heading or block opens the note at its start.

In reading view Markdown link text is displayed literally. Empty text uses the
resolved filename without `.md`, then the path's last segment, then the current
note's name. Rename preserves resolved destinations for both link forms; Markdown
rewrites keep their text, heading, angle brackets and extension preference, using
a path relative to the source (or a root path for a formerly root-based link).
Percent signs and path hashes are escaped; outside angle brackets, spaces and
parentheses/angle brackets are escaped too. Unresolved links keep their exact bytes.
Search still compares the original text without NFC normalization.

## New Note (Ctrl+N)

File > New Note… (Ctrl+N) opens a dialog with a name or vault path, such as
Projects/Idea. Create (or Enter) saves the current note first; Cancel or Escape
leaves it alone. An existing name opens that note. Unsafe paths are refused.
Every newly created note, including one created by following a missing link or
using the switcher, leaves reading view and focuses the editor at the end, ready
to type. Opening an existing note keeps the current mode.

## Quick switcher (Ctrl+O)

Type part of a note's name or path. The characters only need to appear in order, so
`prjalp` finds `Projects/Alpha`. Exact names rank first, then names that start with
what you typed, then names that contain it. **Up/Down** pick a result, **Enter**
opens it, and **Escape** cancels. If nothing matches, **Enter** creates a note with
the name you typed. A hint above the entry points to Ctrl+Shift+F for content
search. A nonempty query that is not already a note adds a final selectable
`Create "QUERY"` row, even when other notes match.

## Reading view (Ctrl+E)

**Ctrl+E**, or View > Reading View, switches between the editor and a formatted,
read-only view of the note, including unsaved edits. Headings, bold, italic, code,
quotes, lists and divider lines are formatted; frontmatter is hidden.

- The view opens at the block or list item your editor caret was in, including
  nested lists and quotes. Trailing paragraph block IDs such as ` ^item-1` are hidden.
- View > Reading View is checked while reading mode is on.
- **Enter** on a link, or a plain **left click** on it, follows it (as Alt+Enter
  does). **Shift+click** selects text instead.
- The mode sticks for existing notes: notes you open stay in reading view until you press Ctrl+E again.
  Switching back puts the editor caret where it was.
- Typing, pasting, Ctrl+S and Undo do nothing while reading.

## Backlinks (Ctrl+Shift+B)

The pane on the right lists every link from other notes to the open note, as
`path (line N)` with that line's text. **Ctrl+Shift+B** moves focus there, and
**Enter** or a double-click opens the linking note with the caret on the link. You
can resize the columns and drag the pane's divider.

### Unlinked mentions (Ctrl+Shift+M)

Below Backlinks, Unlinked mentions lists whole-word occurrences of the open
note's filename without `.md` in other notes. Matching ignores case using
per-character lowering. It excludes frontmatter, fenced/inline code and both
note-link syntaxes, including notes that also contain an actual link. Enter or
double-click opens the source with the caret at the mention; Ctrl+Shift+M focuses
the first row.

## Search (Ctrl+Shift+F)

Type to search all notes. Search is case-insensitive and finds text anywhere,
including code and frontmatter. A match never spans two lines. Results show as
`path:line: text`; **Enter** opens the selected one with the caret on the match.
Results stop at 500. Regular expression (Alt+R) uses case-insensitive GLib/PCRE
syntax, per line; empty matches are skipped. Whole word (Alt+W) requires both
boundaries to be outside letters, digits and underscores. A rejected candidate
retries one character after its start; accepted matches do not overlap.
Options reset to off each time the dialog opens. Invalid regex syntax clears the
results and shows `Invalid expression`. CLI: `find VAULT QUERY [--regex] [--word]`;
options follow QUERY in either order.

## Tags

A tag is `#word` at the start of a line or after a space: letters, digits, `_`, `-`
and `/` for nesting (`#project/alpha`). It must contain at least one non-digit, so
`#2025` is not a tag. Tags in code don't count. Frontmatter tags work too:

```yaml
---
tags: [project, inbox]
---
```

Both `tag:` and `tags:` accept flow lists, comma/whitespace-separated scalars,
or indented `- item` lists. The **Tags** tab lists every tag and implicit ancestor
with the number of notes containing it or any descendant. Display spelling uses
the first explicit occurrence in vault/document order; an implicit ancestor uses
the first descendant's prefix. Expand a tag to
see its notes (nested tags included) and activate a note to open it. Tags are
case-insensitive after NFC normalization. Expansion and selection survive refreshes
when the same tag or note under that tag remains.

F2 on a tag row opens Rename Tag. It saves first, replaces every matching prefix
in inline and frontmatter tags, preserves quotes, punctuation, code and other
bytes, reloads changed open text and preserves the caret. Focus returns to the
editor or reading view. CLI: `retag VAULT OLD NEW` (optional leading `#`).
Both tags must be valid; OLD must occur; NEW cannot be nested under OLD. Merges
upward or into another tag are allowed. Refusals write nothing.

## Sidebar keyboard access

Ctrl+Shift+E shows Notes and selects the open note (first row if none).
Ctrl+Shift+T shows Tags and selects its first row. Arrows navigate; Enter
activates or expands a row; F2 renames the selected row.

## Outline and note organization

Ctrl+Shift+O opens the Outline and selects its first heading. Enter or a
double-click jumps to that source heading in the editor or reading view. The
outline follows edits. F6 opens Move Note: enter a vault-relative destination
folder, or leave it empty for the root. File > Archive Note moves the note under
`Archive/`, retaining its original path. Both commands save pending changes first
and refuse collisions. Escape cancels the Move dialog.

Move and Archive save pending editor changes before relocating. If the file was
changed externally, they refuse the operation and keep your pending buffer;
explicit Reload from Disk discards it. Archive refuses an already archived note.
Supported links are updated to continue resolving to the moved document; collisions
and unsafe paths are refused rather than overwritten.

File > Supersede With… accepts an existing vault-relative note path and writes
reciprocal `superseded_by` and `supersedes` properties. Each document is saved
atomically, but the pair is not a transaction; a failure on the second save may
leave the first changed. Reading view shows parsed properties above the body;
resolved supersession references appear as links above the table. Tags and aliases
in the table can be followed, subject to normal navigation and save safeguards.
A note's real name wins over an alias during link resolution. Ambiguous Properties
aliases do not guess a destination. Quick Switcher also displays alias results as
`alias → path`; an alias row can currently appear before an exact filename, so check
the destination before activating a result.

## Renaming (F2)

**F2**, or File > Rename…, renames or moves the open note. Type a new name or path,
such as `Archive/Old Ideas`, and press Enter. LCOS Notes then:

- saves the note and moves it, creating folders as needed;
- rewrites every link in the vault that would otherwise break, keeping its heading,
  shown text and embed marker. Links that were already broken are left alone, and
  notes that need no change are not touched;
- keeps your caret on the same text.

The Notes tree includes attachments after notes. F2 with tree focus renames the
selected note, folder or attachment; folder destinations are complete directory
paths and attachment destinations include any desired extension (or none).
Every file under a moved folder moves with it, and links in both syntaxes retain
their resolved file. The open note reloads at its final path with its caret on
the same text and focus restored. Every rename dialog has Cancel and Rename;
Rename is the default, and Escape cancels.

A folder cannot move inside itself. Existing destinations, hidden or unsafe
paths, symlinks under the source folder and invalid UTF-8 notes under it are
refused. Extensionless attachment destinations are allowed when every link can
still resolve correctly. A rename is refused, and nothing changes, if the new name is already taken or a
link could not be kept pointing at the right note. The statusbar explains why.

## Command-line tool

`lcos-notes-cli` uses the same engine as the app. Each command prints one JSON
value. Errors print `refused: <reason>` and exit with status 2.

```sh
lcos-notes-cli notes     VAULT                 # all notes
lcos-notes-cli links     VAULT NOTE            # wikilinks in a note, resolved
lcos-notes-cli mdlinks   VAULT NOTE            # Markdown note links, resolved
lcos-notes-cli resolve   VAULT NOTE 'Ideas#Plan|text'
lcos-notes-cli switch    VAULT QUERY           # quick-switcher results
lcos-notes-cli create    VAULT 'Inbox/Today'
lcos-notes-cli tags      VAULT
lcos-notes-cli tagged    VAULT TAG
lcos-notes-cli retag     VAULT OLD NEW
lcos-notes-cli mentions  VAULT NOTE
lcos-notes-cli find      VAULT QUERY [--regex] [--word]
lcos-notes-cli backlinks VAULT NOTE
lcos-notes-cli rename    VAULT OLD NEW
lcos-notes-cli render    VAULT NOTE            # reading-view text, styles, links
lcos-notes-cli blocks    VAULT NOTE            # reading-view block positions
lcos-notes-cli tasks     VAULT NOTE            # task markers and reading-view offsets
lcos-notes-cli highlights VAULT NOTE           # rendered highlight ranges
```

`man lcos-notes` and `man lcos-notes-cli` have the same reference offline.

## Not supported yet

These are not supported yet:
- Markdown links with titles and reference-style note links;
- following images or non-local links, and NFC normalization in search;
- task items inside block quotes (not recognized by the supported parser);
- Markdown image embeds (`![alt](file.png)`), PDF embeds and viewing other attachments;
- callout aliases such as `info` or `todo`, and highlights coloured in the editor;
- a settings dialog, a graph view and multiple windows.

An apt repository and package signing are not provided.

The Go menu exposes Quick Switcher, Follow Link, Search Notes, Backlinks, Notes,
Tags, Outline and Unlinked Mentions, with their keyboard shortcuts.


## Tables, tasks and strikethrough

GitHub-flavored Markdown tables render with aligned, padded columns and a bold
header in reading view. `~~text~~` renders with strikethrough; single tildes stay
literal. Task lists use `- [ ]` for open items and `- [x]` (or `[X]`) for completed
items; ordered lists also support tasks. Task items inside a block quote are not
recognized by the supported parser.

In reading view, put the caret on a task box and press Space, or click the box,
to toggle it. Only the marker character changes. The whole buffer is then saved
as with Ctrl+S, including any unsaved edits. If saving is refused because the file
changed on disk, the toggled buffer stays available. Space elsewhere does nothing.
The CLI command `tasks VAULT NOTE` reports each task's source line, code point
column, checked state and reading-view box offset.

## Files changed by another program

A clean open note reloads within two seconds after an external change. The editor
caret keeps its line and column, clamped to the new text; reloading clears Undo.
Reading view follows the editor position. Unsaved edits are kept instead, with a
status message. File > Reload from Disk (Ctrl+Shift+R) explicitly replaces the
buffer with the file's text, discarding unsaved edits without confirmation.
Invalid UTF-8 is refused and the buffer is kept.

If the open file is deleted or renamed externally, its buffer becomes modified
and the status says `Deleted on disk`. Ctrl+S restores it at the original path,
unless another file has appeared there. External changes also refresh Notes,
Tags, Backlinks and Unlinked mentions within two seconds, preserving existing
folder expansion, selection and Tags state. The app's own writes do not trigger
external reloads.

## Highlights

In reading view, `==text==` shows the text on a yellow background and hides the
`==` marks. Highlights work in paragraphs, list items, table cells, headings and callouts,
and can contain links, bold, italic, strikethrough and inline code: `==a **b** c==`
highlights the whole phrase while retaining bold. Inline code retains its code style
but never supplies highlight delimiters. Highlights do not cross source line breaks,
raw HTML or paragraph boundaries. `==` followed by a
space, or a closing `==` preceded by one, does not count, so `== spaced ==`, a lone
`==` and `====` stay as written.

- **Edit > Highlight** (Ctrl+Shift+H), in the editor: with text selected, wraps it
  in `==`; if the selection is already wrapped, removes them. With no selection it
  inserts `====` and puts the caret in the middle. Each use is one Undo step. It does
  nothing in reading view.
- **View > Highlights…** (Ctrl+Shift+Y) lists the open note's highlights in order.
  Double-click a row, or select it and press Enter, to switch to reading view at
  that highlight. A note without highlights shows "No highlights in this note".
  Escape closes the dialog.
- `lcos-notes-cli highlights VAULT NOTE` prints the highlights as JSON
  (`start`, `end` and `text` in the reading-view text).

## Callouts

A block quote whose first line is `[!type]`, optionally followed by a title, is a
callout:

```markdown
> [!warning] Back up first
> Renaming a folder rewrites links in every note.
```

The title is bold and the callout is tinted by type: `note` blue, `tip` green,
`warning` amber, `danger` red, `question` purple and `quote` grey. Any other type
uses the note colour. Without a title, the type is the title (`[!tip]` shows "Tip").

- `[!tip]-` starts **folded**: only the title shows. Click the title to open or
  close the body. Folding is a view state only: it never changes the file, and it
  resets when the note is re-rendered.
- `[!tip]+` starts open (the same as no sign).
- Nested quotes and lists inside a callout keep their formatting.
- The tint fills the available reading column and follows window resizing. It stays
  within the callout, preserving nested colors, folding and ordinary paragraphs.
- Titles retain their tint when callouts occur inside nested or mixed-marker lists.
- A folded callout can leave an extra tinted blank row below its title. This
  disclosed appearance limitation is retained in the accepted candidate.

## Embeds

A paragraph that contains nothing but one embed shows the embedded content in
reading view, indented:

| Source | Shows |
|---|---|
| `![[Note]]` | the whole note (frontmatter hidden) |
| `![[Note#Heading]]` | that heading and everything up to the next heading of the same or higher level |
| `![[Note#^block-id]]` | the block ending in ` ^block-id` |
| `![[photo.png]]` | the image, at its own size |

- Links inside embedded content work and resolve from the embedded note's folder.
  Highlights, callouts, tables and task boxes are formatted as usual. Task boxes
  inside an embed are not clickable: tick them in the note itself.
- Embeds update automatically when an embedded note changes on disk.
- Images: `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp` and `.webp`. A file that can't be
  loaded shows `[image: path]` in the unresolved-link colour.
- An embed that points at a missing note, heading or block, an empty or non-UTF-8
  note, any other kind of file (such as a PDF), a note already being embedded (a
  loop), or content past the embed depth limit (three levels) shows as an ordinary link instead.
- An embed sharing its paragraph with other text, such as `see ![[Note]] here`,
  stays a link.
- The editor always shows the plain `![[...]]` source.
- `lcos-notes-cli render` lists embedded images in an `images` array
  (`offset` in the text and vault-relative `path`).

## Daily notes, templates and capture

Daily notes use `.obsidian/daily-notes.json`: `folder` defaults to the vault root, `format` to `YYYY-MM-DD`, and `template` selects an optional template. Ctrl+D opens today's note; Alt+Left and Alt+Right visit existing earlier and later daily notes. The CLI commands `daily VAULT [DATE] [--create]` and `dailies VAULT` provide the same operations.

Templates use `.obsidian/templates.json`; the `folder` defaults to `Templates`, and `dateFormat` and `timeFormat` control `{{date}}` and `{{time}}`. Templates also support `{{title}}` and explicit date or time formats such as `{{date:YYYY-MM-DD}}`. Choose one in the New Note drop-down or use Insert Template with Ctrl+Shift+I. The CLI provides `templates VAULT`, `template VAULT TEMPLATE TITLE`, and `create VAULT TARGET --template TEMPLATE`.

Timestamp names use `.obsidian/zk-prefixer.json` (`folder` and `format`); choose Timestamp Name in New Note or run `unique VAULT`.

Run `lcos-notes --capture` to open the capture window and bind that command to a keyboard shortcut in the desktop's keyboard settings. Choose today's note or Inbox; `lcos-notes-cli capture VAULT TEXT [--inbox]` provides the CLI equivalent. Captures into an open note with unsaved edits are appended to the buffer while preserving those edits.

Set `LCOS_NOTES_NOW` to a local `YYYY-MM-DDTHH:MM:SS` value to override the clock.

The CLI provides `props VAULT NOTE` for supported frontmatter fields,
`aliases VAULT` for declared aliases, and `headings VAULT NOTE` for the
Markdown outline. `supersede VAULT OLD NEW` adds reciprocal supersession
properties after validating both notes. Each changed note is saved atomically;
the two saves do not form a single transaction.


## Known limits and future scope

An extreme synthetic 80 KB note with 20,000 unmatched highlight markers showed
about 2.0 seconds of packaged reading-view latency versus about 1.1 seconds in
accepted U10; ordinary 80 KB text was about 0.28 seconds in both. These are recorded
measurements, not a response-time guarantee for every computer or note. No further
highlight optimization is included in this candidate.

Mouse-only reliability through Mac Screen Sharing remains unverified. Some input
paths can focus a control without activating it; Return or Space on the focused
control can help establish what actually happened. The live P3 retest used native
libvirt input and does not certify another input path.

Ranked search, related notes, a task dashboard/query blocks and vault health are
U11 work after 1.0. Graph/resurfacing features are U12, also after 1.0. Semantic
recall M5 requires Lee's decision. The native Mac app is parked. None is silently
included in this release boundary. [Retained scope](RELEASE-NOTES.md#documented-limitations).
