# Connect notes

A link lets you move from one idea to another. In the editor write `[[Garden plan]]`, save, put the caret inside the link and press **Alt+Enter**, or Ctrl+click it. In Reading view a normal click follows it. Following a missing note link can create the target, so check the spelling first.

Use `[[Garden plan#Next steps]]` to jump to a heading, `[[Garden plan|the plan]]` for different displayed text, or `[[#Next steps]]` for a heading in the current note. A block reference such as `[[Garden plan#^next]]` points to a line ending in ` ^next`. A missing heading or block opens the note at its start. Links inside code are not followed.

A Markdown note link works too: `[Plan](Garden%20plan.md)` or `[Plan](<Garden plan.md>)`. Relative Markdown paths try the source folder and then the vault root; a leading `/` starts at the root. Titles, reference-style links, web destinations and Markdown images are not followable note links. Search uses source text rather than rendered link labels.

Backlinks on the right show other notes linking to the open note. Press **Ctrl+Shift+B**, select a row and press Enter to visit the source. Below them, Unlinked mentions finds whole-word mentions of the note's filename in other notes; **Ctrl+Shift+M** focuses its first result. A mention is an invitation to consider a connection, not an automatic link.

To display content within a note, put `![[Herbs]]` or `![[photo.png]]` alone in a paragraph. Reading view embeds supported notes or PNG, JPEG, GIF, BMP and WebP images. Heading and block targets work for notes. Embed nesting stops at three levels; unsupported, missing or recursive targets appear as links. Tasks inside embeds are not clickable. The editor shows the source.

Names resolve case-insensitively with Unicode normalization. When filenames repeat, the same folder and then shortest path take precedence. A real note name wins over an alias; see [properties and aliases](properties.md). For name and path changes, see [organizing](organize.md).
