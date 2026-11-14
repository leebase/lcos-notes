# Work with vaults

A vault is a folder, including its subfolders. LCOS Notes discovers lower-case `.md` files as notes; images and other files are attachments. Hidden files and folders and symbolic links are skipped during traversal. Supported `.obsidian` configuration files are an explicit read-only exception, described in [daily notes](daily-notes.md) and [templates](templates.md).

To open a particular vault, start `lcos-notes --vault /path/to/folder`. To open a specific note at launch, add its vault-relative path, for example `lcos-notes --vault ~/Notes Home.md`. Without arguments the app uses the last vault or asks for a folder. The last-vault choice is stored in the user's configuration directory outside the vault.

Use Notes on the left to browse. Opening another note or closing the window saves the current note first. If a conflict prevents that save, switching notes is cancelled; closing asks whether to discard the unsaved edits. Choose Cancel to keep the window and your edits. A ` *` in the title marks unsaved edits. **Ctrl+S** saves explicitly. Files retain their existing line-ending convention and final newline behavior; a note must be valid UTF-8 to edit. An unchanged note is not rewritten.

A save uses a temporary file and rename. Keep independent copies of your vault, especially before large renames or moves. If another program changes the open file, the app reloads clean content but protects a dirty buffer from being overwritten; see [Troubleshooting](troubleshooting.md).

LCOS Notes reads only selected Obsidian settings and does not write `.obsidian` or add hidden application metadata. It does create or change ordinary files when you request note creation, capture or organization. See [Coming from Obsidian](obsidian-users.md).


## Switch vaults from the running app (unreleased source)

The current source includes these controls; the November 8 version 1.0.0 download
does not. Use the File menu:

- **Open Vault…** selects an existing readable folder.
- **Recent Vaults…** lists up to ten recently opened vaults, most recent first.
  Select a path and choose Open. A missing or unreadable entry may remain listed;
  opening it reports an error and keeps the current vault.
- **New Vault…** creates and opens one empty folder. Enter its complete absolute
  path, including the new name, such as `/home/alex/Notes/Project B`. The parent
  must already exist and be writable. The target must not already exist, even as
  a symbolic link. Omit a trailing slash and use an absolute path rather than `~`.
  LCOS Notes creates no starter notes or hidden metadata.

The full current path appears above the workspace. Switching saves the current
note first; if saving fails, the current vault and edits remain open. Check the
status bar for the save failure's cause. Cancelling, selecting an invalid
folder, or selecting the current vault leaves your editor unchanged. A successful
switch opens the selected vault with no note open and clears the previous vault's
editor and navigation state. **Ctrl+O** opens the note Quick Switcher within the
selected vault.

Recent paths are canonical and deduplicated. They and the last-vault choice live
in the user configuration directory outside every vault; a configuration write
failure shows a warning. Switching uses one Notes window. Vaults remain
independent: search and links operate within the selected root, with no merged
search or cross-vault link resolution. Use ordinary local UTF-8 paths, including
spaces and non-ASCII names. Paths containing newline or other control characters,
and network filesystems, are outside the supported scope.
