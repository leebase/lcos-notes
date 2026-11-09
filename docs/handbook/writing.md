# Write and format

The editor shows Markdown source. Type text, save with **Ctrl+S**, then press **Ctrl+E** to see formatted Reading view. Press it again to edit. Try this in a practice note:

```markdown
# Project

A **bold** decision and an *emphasis*.

- [ ] Ask for a sample
- [x] Sketch the idea

==A phrase with **important** detail==

> [!tip] Next step
> Make the smallest useful test.
```

Headings, lists, quotes, code, tables, strikethrough and task boxes have formatted representations in Reading view. Clicking a task box there changes its marker and saves the whole buffer, including other unsaved edits. Tasks in block quotes are not recognized as task items; task boxes in embedded notes must be changed in the original note. See [Reading a note](reading.md).

For a highlight, use matching `==` delimiters without spaces next to the text. In the editor select text and press **Ctrl+Shift+H** to wrap or unwrap it; with no selection the shortcut inserts delimiters at the caret. Highlights can contain bold, italic, links and inline code, but do not cross source lines or blocks. **Ctrl+Shift+Y** lists highlights in the current note.

A callout starts as a block quote with `[!type]`. The six styled types are `note`, `tip`, `warning`, `danger`, `question` and `quote`; another type uses the note color. Add `-` after the marker to start folded, as in `> [!tip]- Details`, and click its title in Reading view to open it. Folding is temporary view state. A folded callout may leave a tinted blank row.

For repeatable text use [templates](templates.md). Find text across notes with [Search](finding.md), or connect ideas using [links](links.md).
