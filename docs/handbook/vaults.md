# Work with vaults

A vault is a folder, including its subfolders. LCOS Notes discovers lower-case `.md` files as notes; images and other files are attachments. Hidden files and folders and symbolic links are skipped during traversal. Supported `.obsidian` configuration files are an explicit read-only exception, described in [daily notes](daily-notes.md) and [templates](templates.md).

To open a particular vault, start `lcos-notes --vault /path/to/folder`. To open a specific note at launch, add its vault-relative path, for example `lcos-notes --vault ~/Notes Home.md`. Without arguments the app uses the last vault or asks for a folder. The last-vault choice is stored in the user's configuration directory outside the vault.

Use Notes on the left to browse. Opening another note or closing the window saves the current note first. If a conflict prevents that save, switching notes is cancelled; closing asks whether to discard the unsaved edits. Choose Cancel to keep the window and your edits. A ` *` in the title marks unsaved edits. **Ctrl+S** saves explicitly. Files retain their existing line-ending convention and final newline behavior; a note must be valid UTF-8 to edit. An unchanged note is not rewritten.

A save uses a temporary file and rename. Keep independent copies of your vault, especially before large renames or moves. If another program changes the open file, the app reloads clean content but protects a dirty buffer from being overwritten; see [Troubleshooting](troubleshooting.md).

LCOS Notes reads only selected Obsidian settings and does not write `.obsidian` or add hidden application metadata. It does create or change ordinary files when you request note creation, capture or organization. See [Coming from Obsidian](obsidian-users.md).
