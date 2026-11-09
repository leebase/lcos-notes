# Capture an idea

Capture records a thought quickly, then lets you organize it when you have time. Open a capture window for an explicit vault:

```sh
lcos-notes --capture --vault ~/Notes
```

Type the thought, choose **Today's note** or **Inbox**, and press **Ctrl+Enter** or click Capture. **Alt+T** and **Alt+I** select the destination; Escape cancels. Inbox means `Inbox.md` at the vault root. Today's note is created if needed. The destination choice is remembered per vault after a successful capture.

For a terminal capture, supply the vault and text explicitly:

```sh
lcos-notes-cli capture ~/Notes 'Try basil in the sunny corner' --inbox
```

Each submission appends a list item with a time such as `- 14:30 Try basil`. A multi-line submission has one timestamp on its first line; subsequent lines are indented. Empty or whitespace-only text writes nothing: the CLI reports a refusal, while the capture window waits for text. If a recognized capture is appended to an open note with unsaved edits, Notes adds it to the buffer and preserves those edits; save normally.

For quick access, bind `lcos-notes --capture` to a desktop keyboard shortcut. It uses the last vault; if none is recorded, it prints `refused: no vault` and exits without opening a window. Open a vault in Notes once first, or add `--vault ~/Notes` to always use that folder. Capture does not change the last-vault choice.

Try this everyday routine:

1. Capture a rough thought to Inbox without deciding its final structure.
2. Later, open Inbox with **Ctrl+O**. Turn a useful item into a note with **Ctrl+N**, giving it a recognizable name. Save it.
3. Add a link from the relevant project note, such as `[[Garden plan]]`, and tag or move the new note if that helps you find it.
4. Edit the Inbox entry to record that you processed it, then save. Search or Backlinks will help you rediscover the connection.

See [Daily notes](daily-notes.md), [Finding](finding.md) and [Organize](organize.md). Capture uses your vault files; keep independent backups.
