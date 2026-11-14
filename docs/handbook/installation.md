# Install and open LCOS Notes

On LCOS 1.0, download the 1.1.0 `.deb` and checksums from the release linked on [Sources](sources.md). Choose the package for your machine and check the download against its checksum. In a terminal in the download folder, the amd64 example is:

```sh
sha256sum -c SHA256SUMS
sudo apt update
sudo apt install ./lcos-notes_1.1.0_amd64.deb
```

Keep the package and `SHA256SUMS` in the same folder. The checksum command should report `OK` for your package; resolve any mismatch before installing. `apt update` supplies package lists needed on a fresh LCOS installation, then `apt install` installs the package and its dependencies. Open **Office > LCOS Notes** in the applications menu or run `lcos-notes` in a terminal. On first launch, choose a practice folder. Later launches reopen the last vault; `lcos-notes --vault ~/Notes` selects a specific folder.

The package is built for Devuan Excalibur, the base of LCOS 1.0. On other Debian-family systems, see the [source build instructions](https://github.com/leebase/lcos-notes#building-from-source). An apt repository and package signing are not supplied. If installation fails, read the terminal message and check the package architecture and location.

## Upgrade from an earlier version

Save your notes and close every LCOS Notes window. Keep your usual independent
vault backup. Download the **1.1.0** `.deb` and `SHA256SUMS` from the
[1.1.0 release](https://github.com/leebase/lcos-notes/releases/tag/v1.1.0).
In the download folder, run:

```sh
sha256sum -c SHA256SUMS
sudo apt update
sudo apt install ./lcos-notes_1.1.0_amd64.deb
```

The checksum must report `OK`. This upgrades the existing package in place;
you do not need to uninstall the earlier version. Your vault folders and user
configuration stay in place, with no vault conversion or import required.
Reopen Notes and check **Help > About** for **1.1.0**. Open the File menu to find
**Open Vault…**, **Recent Vaults…** and **New Vault…**. See [Work with vaults](vaults.md).

LCOS Notes has no apt repository. Running `apt upgrade` alone will not fetch
this release; install the downloaded package with the command above.

The window has Notes, Tags and Outline on the left, an editor in the middle, Backlinks on the right and a status bar below. Continue with [the three-note exercise](quick-start.md). For CJK font coverage, see [Troubleshooting](troubleshooting.md).
