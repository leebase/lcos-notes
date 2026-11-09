# Install and open LCOS Notes

On LCOS 1.0, download the 1.0.0 `.deb` and checksums from the release linked on [Sources](sources.md). Choose the package for your machine and check the download against its checksum. In a terminal in the download folder, the amd64 example is:

```sh
sha256sum -c SHA256SUMS
sudo apt update
sudo apt install ./lcos-notes_1.0.0_amd64.deb
```

Keep the package and `SHA256SUMS` in the same folder. The checksum command should report `OK` for your package; resolve any mismatch before installing. `apt update` supplies package lists needed on a fresh LCOS installation, then `apt install` installs the package and its dependencies. Open **Office > LCOS Notes** in the applications menu or run `lcos-notes` in a terminal. On first launch, choose a practice folder. Later launches reopen the last vault; `lcos-notes --vault ~/Notes` selects a specific folder.

The package is built for Devuan Excalibur, the base of LCOS 1.0. On other Debian-family systems, see the [source build instructions](https://github.com/leebase/lcos-notes#building-from-source). An apt repository and package signing are not supplied. If installation fails, read the terminal message and check the package architecture and location.

The window has Notes, Tags and Outline on the left, an editor in the middle, Backlinks on the right and a status bar below. Continue with [the three-note exercise](quick-start.md). For CJK font coverage, see [Troubleshooting](troubleshooting.md).
