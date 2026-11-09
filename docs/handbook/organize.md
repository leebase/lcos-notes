# Organize and maintain notes

Before reorganizing valuable notes, make an independent backup. These commands operate on ordinary vault files and can update links in other notes. Save-conflict and collision checks can refuse an operation; read the status bar if nothing moves.

**Rename:** Select a note, folder or attachment in the Notes tree and press **F2**. Enter the new name or complete vault-relative path and choose Rename. With the editor focused, F2 renames the open note. Folder moves include their contents. Supported links are rewritten to preserve their resolved destinations; unsafe paths, existing destinations and cases where links cannot be preserved are refused. F2 on a selected tag instead opens Rename Tag, which updates matching tag prefixes throughout supported note text.

**Move:** Open a note, press **F6** and enter a destination **folder**, such as `Projects/Garden`, or leave it empty for the vault root. The existing filename is retained. Pending edits save first; a collision or external change can prevent the move. Supported links are adjusted.

**Archive:** Choose **File > Archive Note**. The current note moves under `Archive/` with its previous relative path retained: `Projects/Garden.md` becomes `Archive/Projects/Garden.md`. An already archived note and a destination collision are refused. Archive is a move.

**Supersede:** Open the older note, choose **File > Supersede With…**, and enter the vault-relative path of an existing replacement. The original stays in place. Reciprocal properties identify the replacement and the older note, with a banner in Reading view. Each file is saved separately; the two saves are not a single transaction. If the action reports failure, inspect both notes and restore or correct their metadata as needed.

For save conflicts and external edits, follow [Troubleshooting](troubleshooting.md). For the meaning of properties, see [Properties and aliases](properties.md).
