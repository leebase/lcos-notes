#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Lee Harrington
set -eu
if [ "$#" -ne 1 ]; then
    echo "usage: $0 OUTDIR" >&2
    exit 2
fi
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
requested_out=$(realpath -m -- "$1")
case "$requested_out/" in
    "$source_dir/"*) echo "OUTDIR must be outside the source tree" >&2; exit 2 ;;
esac
mkdir -p -- "$requested_out"
out_dir=$(CDPATH= cd -- "$requested_out" && pwd -P)
# All generated state, including dpkg metadata, stays outside the source tree.
temp_base=/tmp
if [ -n "${TMPDIR:-}" ] && [ -d "$TMPDIR" ]; then
    resolved_tmp=$(CDPATH= cd -- "$TMPDIR" && pwd -P)
    case "$resolved_tmp/" in
        "$source_dir/"*) ;;
        *) temp_base=$resolved_tmp ;;
    esac
fi
work=$(mktemp -d "$temp_base/lcos-notes-deb.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT HUP INT TERM
# Subprocesses such as dpkg-deb also allocate temporary files. Keep their
# scratch space here even when the caller's TMPDIR points into the sources.
TMPDIR=$work
export TMPDIR
meson setup "$work/build" "$source_dir" --buildtype=release --prefix=/usr --wrap-mode=nodownload
meson compile -C "$work/build"
DESTDIR="$work/stage" meson install -C "$work/build" --no-rebuild
stage="$work/stage"
strip --strip-all "$stage/usr/bin/lcos-notes" "$stage/usr/bin/lcos-notes-cli"
for page in "$stage"/usr/share/man/man1/*.1; do gzip -9n "$page"; done
mkdir -p "$stage/usr/share/doc/lcos-notes" "$stage/DEBIAN" "$work/debian"
cp "$source_dir/packaging/copyright" "$stage/usr/share/doc/lcos-notes/copyright"
# dpkg-shlibdeps needs source control metadata, not a Debian source checkout.
cat > "$work/debian/control" <<'CONTROL'
Source: lcos-notes
Section: editors
Priority: optional
Maintainer: Lee Harrington <lee@leebase.com>
Standards-Version: 4.6.2

Package: lcos-notes
Architecture: any
Description: Local Markdown notes
 An offline editor and reading view.
CONTROL
# Use the host's linker paths and package shlibs/symbols databases. No fixed
# architecture, library version, development prefix or downloaded metadata.
depends=$(cd "$work" && dpkg-shlibdeps -O -e"$stage/usr/bin/lcos-notes" -e"$stage/usr/bin/lcos-notes-cli")
depends=${depends#shlibs:Depends=}
arch=$(dpkg --print-architecture)
size=$(du -sk "$stage/usr" | cut -f1)
cat > "$stage/DEBIAN/control" <<CONTROL
Package: lcos-notes
Version: 1.0.0
Architecture: $arch
Maintainer: Lee Harrington <lee@leebase.com>
Section: editors
Priority: optional
Installed-Size: $size
Depends: $depends
Description: Offline Markdown notes for LCOS and X11 desktops
 A native GTK editor with wikilinks, search, tags, backlinks and a styled
 reading view. Notes remain ordinary files in a local folder vault.
CONTROL
find "$stage" -type d -exec chmod 0755 {} +
find "$stage" -type f -exec chmod 0644 {} +
chmod 0755 "$stage/usr/bin/lcos-notes" "$stage/usr/bin/lcos-notes-cli"
dpkg-deb --root-owner-group --build "$stage" "$out_dir/lcos-notes_1.0.0_${arch}.deb"
