# Troubleshooting and recovery

**The status says “Changed on disk; your unsaved edits are kept” or “Changed on disk; not saved.”** Another program changed the open file while you had unsaved edits. The first message appears when Notes detects the change; the second appears if you try to save over it. Notes keeps your buffer and refuses to overwrite the disk version. Copy your edits somewhere safe, inspect the disk version separately, and reconcile the two before saving. **Ctrl+Shift+R** explicitly replaces the buffer from disk and discards unsaved edits **without confirmation**. Use it only after preserving any edits you need.

**The file changed elsewhere while clean.** The open note normally reloads within two seconds, retaining its approximate caret position and clearing Undo. If it was deleted or renamed externally, the status says `Deleted on disk` and the buffer becomes modified. Ctrl+S can restore it at its old path unless another file has appeared there. Check the desired destination first.

**A note is missing or cannot be edited.** Confirm you opened the intended vault and that the note ends in lower-case `.md` and is valid UTF-8. Traversal skips hidden paths and symbolic links. An invalid UTF-8 note is skipped by search and several other operations. Back up the original and repair its encoding outside Notes.

**A move, rename or archive is refused.** Read the status bar. Check for an existing destination, an unsafe path, a changed file or an already archived note. F6 expects a destination folder, not a filename. Make a backup before retrying. After a failed Supersede, inspect both notes: the two saves are separate and one may have succeeded.

**A character appears as a box.** Notes uses installed system fonts. A box for 猫 can mean missing CJK font coverage, not damaged text. On LCOS/Devuan, an administrator can install optional `fonts-noto-cjk`, run `fc-cache -f` and reopen Notes. `fc-list ':charset=732b' family` checks installed coverage for that glyph. Per-user font installation is also possible; see the [complete reference](full-reference.md).

**Reading looks odd or slow.** A folded callout can leave a tinted blank row. Extreme text with many unmatched highlight delimiters has recorded latency. Mouse-only reliability through Mac Screen Sharing is unverified; Return or Space on a focused control may help establish what happened. See [Reading](reading.md) and [Writing](writing.md).
