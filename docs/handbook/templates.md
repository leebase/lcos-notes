# Make and use templates

A template is an ordinary note whose text can be copied into another note. By default, place template notes in the vault's `Templates/` folder. Create `Templates/Meeting.md` with:

```markdown
# {{title}}

Date: {{date}}
Time: {{time}}

## Purpose

## Decisions

## Next steps
```

To create a note from it, press **Ctrl+N**, enter a new name, select Meeting in the Template drop-down and choose Create. The resulting new file contains the expanded text. If the named note already exists, it opens untouched. To insert the same template into an open note, switch to the editor, put the caret where the text belongs, press **Ctrl+Shift+I**, select it and press Enter. A selection is replaced. Insertion is one undo step and does not merge frontmatter.

`{{title}}` uses the destination filename without `.md`. `{{date}}` and `{{time}}` use the current clock and default formats `YYYY-MM-DD` and `HH:mm`. An explicit example is `{{date:YYYY-MM-DD}}`. Supported tokens are `YYYY`, `YY`, `MMMM`, `MMM`, `MM`, `M`, `DDDD`, `DD`, `D`, `dddd`, `ddd`, `HH`, `H`, `mm` and `ss`; month and weekday names are English. Brackets enclose literal text. Unsupported formats remain unexpanded.

Existing `.obsidian/templates.json` can specify `folder`, `dateFormat` and `timeFormat`. The app reads but does not write it; users may edit it manually. Templates are regular searchable notes. There is no Templater scripting. In New Note, **Timestamp Name** generates a name, defaulting to `YYYYMMDDHHmm` and adding a suffix on collision. See [daily notes](daily-notes.md) and [capture](capture.md).
