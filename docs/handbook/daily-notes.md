# Keep daily notes

Daily notes give each date a predictable home for a running log. Press **Ctrl+D** to save the current note and open today's note, creating it if needed. By default the file lives at the vault root as `YYYY-MM-DD.md`. The editor is focused at the end, ready for text. An existing daily note is opened without being overwritten by a template.

While a daily note is open, **Alt+Left** opens the nearest existing earlier daily note and **Alt+Right** the nearest existing later one. These keys do not create missing dates. If the current note is not recognized as a daily note, the status bar says so. Use **Ctrl+D** to return to today.

If you already maintain compatible configuration, LCOS Notes reads `.obsidian/daily-notes.json` for `folder`, `format` and optional `template`; it does not write the file. You may edit that JSON yourself outside the app. Unsupported, invalid or time-bearing daily formats fall back to `YYYY-MM-DD`. A format must identify a unique date for existing notes to be recognized as daily notes. A selected template is applied on creation, not merged into an existing file.

For example, start today with `# Today`, record a short decision and link it to `[[Garden plan]]`. Tomorrow open a new daily note, then visit the earlier one with Alt+Left. See [Templates](templates.md) for variables and [Capture](capture.md) for a faster way to add a thought.
