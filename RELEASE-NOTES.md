# LCOS Notes acceptance and release notes

## 1.0.0 — November 8, 2026

Lee accepted U10 organization and the four agreed 1.0-polish improvements.
The release integrates that accepted implementation and updated documentation,
with consistent 1.0.0 application, package, About and AppStream versions.
Download the rebuilt LCOS package and checksums from the
[1.0.0 release](https://github.com/leebase/lcos-notes/releases/tag/v1.0.0).
The previous [0.9.0 release](https://github.com/leebase/lcos-notes/releases/tag/v0.9.0)
remains available.

### Capture retained from U9

Daily notes and navigation, templates, timestamp note names, and a separate quick
capture window/CLI remain supported. Supported Obsidian configuration is read
without writing hidden vault directories.

### Organization accepted in U10

Aliases participate in link resolution and Quick Switcher; Outline follows
headings; Properties show supported frontmatter. Move and Archive save pending
edits and preserve supported links. Supersede records reciprocal properties and
shows a replacement banner, retaining the original note. Save-conflict refusal,
collision handling and hidden-directory protections remain in force.

### Four agreed polish improvements

- Callout backgrounds fill the reading column, including nested/mixed-list titles,
  with folding, links and ordinary neighboring paragraphs preserved.
- Highlights span inline formatting while preserving bold, italic, code and links;
  code delimiters and source/block boundaries retain their rules.
- U9 source is reformatted without a behavior change.
- New Note's hint and Template labels align left without changing template/capture behavior.

### Acceptance evidence

| Layer | Accepted evidence |
|---|---|
| Engineering | 838/838 tests and qualified independent final review |
| Installed platform | Exact reviewed source built on Devuan and passed 59 installed LCOS regression/polish checks |
| Desktop product | Five checks passed, including actual live P3 after installing the optional CJK fonts for Lee's account |
| Preservation | U9 preserved, U10 accepted, unchanged reviewed Notes binary and both hidden synthetic sentinels preserved |

The CJK check initially displayed a 732B box. The stock image lacked a font for
猫. Installing verified Noto CJK fonts for the user fixed the glyph in the unchanged
binary. This was an environment-font correction, not an app repair. System-wide
package installation was not required for the successful per-user verification.

### Documented limitations

- A folded callout can leave an extra tinted blank row beneath the title.
- Deliberately extreme unmatched-highlight input has recorded latency; see the
  [user guide](DOCUMENTATION.md#known-limits-and-future-scope) for the measured case.
- Mouse-only reliability through Mac Screen Sharing remains unverified.
- Exact filename ranking ahead of aliases and clearer feedback for ambiguous
  Properties aliases remain separate possible polish, not U10 defects.
- Supersede saves each note atomically, not the pair as a transaction.

Optional font policy: LCOS Notes uses installed system fonts. For Chinese, Japanese and Korean coverage, install fonts-noto-cjk.

U11/U12 are after 1.0. M5 semantic recall remains Lee-gated. The native Mac app is
parked. An apt repository and package signing are not supplied.

## 0.9.0 — published capture release

Daily notes, templates, timestamp names and quick capture. This existing public
release remains available; its historical QA and downloads are preserved.
