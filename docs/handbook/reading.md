# Read a note

Press **Ctrl+E** or choose **View > Reading View** to switch between the source editor and a formatted view. Reading includes the current buffer, even unsaved changes. It opens near the block containing the editor caret; returning restores the caret. Existing notes opened while reading remain in Reading view until you switch back.

Click a note link or place the caret on it and press Enter. Shift+click selects text instead. Click a task box, or place the caret on it and press Space, to change its marker. That action saves the whole buffer; a save conflict keeps the modified buffer for recovery. Tasks inside embedded notes must be toggled in their own note.

Properties parsed from frontmatter appear above the body, and supported supersession references can link to related notes. The source frontmatter itself is hidden. Click a foldable callout title to open or close its body; the fold state resets on rendering. Notes and images embedded on their own paragraph are shown in place within the limits in [Connect notes](links.md).

Reading is read-only for ordinary typing, paste, Undo and Ctrl+S. Use **Ctrl+E** to make text changes. **Ctrl+Shift+Y** lists the current note's highlights; selecting one opens Reading view there. See [Write and format](writing.md) and [Properties](properties.md).
