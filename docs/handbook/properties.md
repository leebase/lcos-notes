# Use properties and aliases

Properties are frontmatter at the very start of a note. Edit the Markdown source directly, then press **Ctrl+E** to see supported parsed properties above the note in Reading view. For example:

```yaml
---
aliases: [Herb garden, Kitchen herbs]
tags: [project/garden, planning]
---
# Garden plan
```

Save the note. Another note can now link to `[[Herb garden]]`, and the switcher can show an alias as `alias → path`. Tags can also be followed from the Properties display. Properties are not a typed spreadsheet: to change a value, return to the source editor and edit frontmatter.

A real note name takes precedence over an alias when resolving a link. If multiple notes claim the same alias, do not assume which is intended. Ambiguous aliases in the Properties display do not guess a destination. Quick Switcher can list an alias result before an exact filename, so read the selected row's path before opening it. Use a distinct filename or path when the destination must be clear.

**File > Supersede With…** records `superseded_by` on an old note and `supersedes` on an existing replacement; see [Organize](organize.md) for precautions. Supported scalar and list forms and unsupported frontmatter details are covered in the [complete reference](full-reference.md). If a property does not display as expected, inspect its delimiters and syntax in source. Related: [finding](finding.md) and [links](links.md).
