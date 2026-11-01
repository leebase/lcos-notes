# LCOS Notes user guide

This guide covers version 0.5.0. The exact rules behind each feature are in
[CONTRACT.md](CONTRACT.md).

## Vaults and notes

A **vault** is any folder. Every file ending in `.md` (lower case) anywhere inside it
is a **note**. Other files, such as images and PDFs, are **attachments**. Hidden files
and folders (names starting with `.`, such as `.obsidian/`, `.trash/` and `.git/`) and
symbolic links are ignored completely. An existing Obsidian vault works as it is:
LCOS Notes never writes into `.obsidian/` and never adds files of its own to the vault.

Notes are plain UTF-8 text. LCOS Notes saves exactly what you typed: it keeps
Windows line endings (CRLF) if the file had them, and adds or removes no final
newline. A note that is not valid UTF-8 can't be edited and is skipped by search,
tags, backlinks and rename.

The only setting LCOS Notes stores is the last vault you opened, in
`~/.config/lcos-notes/last-vault`.

## Starting

```sh
lcos-notes                          # last vault, or a folder chooser the first time
lcos-notes --vault ~/Notes          # a specific vault
lcos-notes --vault ~/Notes Home.md  # a vault and a note (path inside the vault)
```

The window has a menubar (File, Edit, View, Go, Help), the **Notes** and **Tags**
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

## Quick switcher (Ctrl+O)

Type part of a note's name or path. The characters only need to appear in order, so
`prjalp` finds `Projects/Alpha`. Exact names rank first, then names that start with
what you typed, then names that contain it. **Up/Down** pick a result, **Enter**
opens it, and **Escape** cancels. If nothing matches, **Enter** creates a note with
the name you typed.

## Reading view (Ctrl+E)

**Ctrl+E**, or View > Reading View, switches between the editor and a formatted,
read-only view of the note, including unsaved edits. Headings, bold, italic, code,
quotes, lists and divider lines are formatted; frontmatter is hidden.

- The view opens at the paragraph your editor caret was in.
- **Enter** on a link, or a plain **left click** on it, follows it (as Alt+Enter
  does). **Shift+click** selects text instead.
- The mode sticks: notes you open stay in reading view until you press Ctrl+E again.
  Switching back puts the editor caret where it was.
- Typing, pasting, Ctrl+S and Undo do nothing while reading.

## Backlinks (Ctrl+Shift+B)

The pane on the right lists every link from other notes to the open note, as
`path (line N)` with that line's text. **Ctrl+Shift+B** moves focus there, and
**Enter** or a double-click opens the linking note with the caret on the link. You
can resize the columns and drag the pane's divider.

## Search (Ctrl+Shift+F)

Type to search all notes. Search is case-insensitive and finds text anywhere,
including code and frontmatter. A match never spans two lines. Results show as
`path:line: text`; **Enter** opens the selected one with the caret on the match.
Results stop at 500.

## Tags

A tag is `#word` at the start of a line or after a space: letters, digits, `_`, `-`
and `/` for nesting (`#project/alpha`). It must contain at least one non-digit, so
`#2025` is not a tag. Tags in code don't count. Frontmatter tags work too:

```yaml
---
tags: [project, inbox]
---
```

The **Tags** tab lists every tag with the number of notes using it. Expand a tag to
see its notes (nested tags included) and activate a note to open it. Tags are
case-insensitive after NFC normalization.

## Renaming (F2)

**F2**, or File > Rename…, renames or moves the open note. Type a new name or path,
such as `Archive/Old Ideas`, and press Enter. LCOS Notes then:

- saves the note and moves it, creating folders as needed;
- rewrites every link in the vault that would otherwise break, keeping its heading,
  shown text and embed marker. Links that were already broken are left alone, and
  notes that need no change are not touched;
- keeps your caret on the same text.

A rename is refused, and nothing changes, if the new name is already taken or a
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
lcos-notes-cli find      VAULT QUERY
lcos-notes-cli backlinks VAULT NOTE
lcos-notes-cli rename    VAULT NOTE NEWNAME
lcos-notes-cli render    VAULT NOTE            # reading-view text, styles, links
lcos-notes-cli blocks    VAULT NOTE            # reading-view block positions
```

`man lcos-notes` and `man lcos-notes-cli` have the same reference offline.

## Not supported yet

These are not supported yet:
- Markdown links with titles and reference-style note links;
- tables, task lists and strikethrough in the reading view;
- showing embedded notes and images;
- reloading notes changed by other programs;
- renaming folders;
- a settings dialog, daily notes, a graph view and multiple windows.

Several of these are in active development.
