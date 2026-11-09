# Find what you need

Choose a tool based on what you remember:

1. **Name or path:** press **Ctrl+O** for Quick Switcher. Type part of the name or path; characters can match in order without being adjacent. Use arrows and Enter to open a result. If there is no match, Enter can create the typed name. A selectable Create row can also appear alongside matches. Check the destination of an alias row before opening it.
2. **Words in a note:** press **Ctrl+Shift+F**. Search is case-insensitive, includes code and frontmatter, and looks within individual lines. Select a `path:line` result and press Enter to open it at the match. Results stop at 500, so narrow a broad query.
3. **Category:** add an inline tag such as `#project/garden` or a frontmatter tag, then press **Ctrl+Shift+T**. Expand a tag to see notes including descendants. Tags ignore case; code is excluded. A tag must contain at least one non-digit and can use letters, digits, `_`, `-` and `/`.
4. **Heading in the current note:** press **Ctrl+Shift+O**, select an Outline row and press Enter to jump there. The outline follows your edits.

Search defaults to literal text. In its dialog **Alt+R** enables a case-insensitive regular expression, and **Alt+W** enables whole-word boundaries. Options reset each time the dialog opens. An invalid expression displays `Invalid expression`; fix it or turn regex off. Search does not span lines or support Obsidian query operators. To find notes referring to the current one, use [backlinks and mentions](links.md). To organize a tag, see [Organize](organize.md).
