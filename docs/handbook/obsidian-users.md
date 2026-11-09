# Coming from Obsidian

LCOS Notes can open a folder containing an Obsidian-style vault. Start with a separate copy or synthetic vault, and keep an independent backup. Notes remain ordinary Markdown files; hidden directories and symbolic links are skipped during traversal. The app explicitly reads supported `.obsidian/daily-notes.json`, `templates.json` and `zk-prefixer.json` settings, but does not write them. You can maintain those JSON files manually.

Familiar conventions include wikilinks, aliases, frontmatter tags, daily notes, templates, callouts, highlights and standalone note or image embeds. See [Links](links.md), [Properties](properties.md), [Daily notes](daily-notes.md) and [Templates](templates.md) for the actual LCOS behavior and supported syntax. A real filename wins in link resolution, while an alias row may appear ahead of an exact filename in Quick Switcher.

The 1.0 interface has a source editor and a separate Reading view toggled by **Ctrl+E**. Source formatting remains visible while editing. There is no Obsidian Settings interface, command palette, live preview, plugin system, tabs, sync, canvas or graph. There is no PDF viewing, advanced Obsidian search language or ranked/semantic recall. Search is literal or per-line regex with an optional whole-word filter.

LCOS renders supported standalone `![[...]]` note and image embeds, with a depth limit; Markdown image syntax and PDF embeds are not supported. Six callout types have distinct colors; other types use note color. Templates support specified title/date/time variables rather than Templater scripts. Properties are edited in source, not a typed spreadsheet. These boundaries let you plan a workflow with [finding](finding.md) and [capture](capture.md) without assuming all Obsidian features transfer.
