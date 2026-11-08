#!/bin/bash
# Construit le paquet Ubuntu :  packaging/ubuntu/build-deb.sh [version]   ->   dist/radthal_<version>_all.deb
# Il faut : dpkg-deb, python3 avec PyYAML et Pillow.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
VERSION="${1:-$(cat "$HERE/VERSION")}"
OUT="$REPO/dist"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
SRC="$HERE/src"

install -d "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/lib/radthal" "$ROOT/usr/lib/systemd/system" \
    "$ROOT/usr/share/radthal/build/node" "$ROOT/usr/share/radthal/build/interface" "$ROOT/etc/radthal" \
    "$ROOT/usr/share/applications" "$ROOT/usr/share/doc/radthal"

sed "s/@VERSION@/$VERSION/g" "$SRC/radthal-app" > "$ROOT/usr/bin/radthal-app"
cp "$SRC/radthal-stack" "$ROOT/usr/lib/radthal/radthal-stack"
cp "$SRC/radthal.service" "$ROOT/usr/lib/systemd/system/radthal.service"
cp "$SRC/radthal.env" "$ROOT/etc/radthal/radthal.env"
cp "$SRC/org.radthal.App.desktop" "$ROOT/usr/share/applications/org.radthal.App.desktop"
for f in control conffiles postinst prerm postrm; do
    sed "s/@VERSION@/$VERSION/g" "$SRC/DEBIAN/$f" > "$ROOT/DEBIAN/$f"
done

# images toutes faites ; si elles sont introuvables, le service compile ces dossiers sur l'ordinateur
python3 "$HERE/make-compose.py" "$REPO/docker-compose.yml" "$ROOT/usr/share/radthal/docker-compose.yml"
cp "$REPO/Dockerfile" "$REPO/radthal.patch" "$ROOT/usr/share/radthal/build/node/"
cp "$REPO"/interface/Dockerfile "$REPO"/interface/launcher.py "$REPO"/interface/ui_*.py "$ROOT/usr/share/radthal/build/interface/"

python3 - "$REPO/docs/logo-radthal.png" "$ROOT/usr/share/icons/hicolor" <<'PY'
import os, sys
from PIL import Image
img = Image.open(sys.argv[1]).convert("RGBA")
for s in (48, 64, 128, 256, 512):
    d = os.path.join(sys.argv[2], "%dx%d" % (s, s), "apps")
    os.makedirs(d, exist_ok=True)
    img.resize((s, s), Image.LANCZOS).save(os.path.join(d, "radthal.png"), optimize=True)
PY

cp "$REPO/LICENSE" "$ROOT/usr/share/doc/radthal/copyright"
cat > "$ROOT/usr/share/doc/radthal/README" <<TXT
Radthal $VERSION
Application : menu "Radthal". Reglages : /etc/radthal/radthal.env (puis : sudo systemctl restart radthal).
Journal : /run/radthal/log et  journalctl -u radthal.   Etat : radthal-app --status
Tes donnees (chaine, portefeuille) sont dans le volume Docker radthal_radthal-data : desinstaller le paquet ne les supprime pas.
https://github.com/bryancarterdouglas/radthal
TXT

find "$ROOT" -type d -exec chmod 755 {} +
find "$ROOT" -type f -exec chmod 644 {} +
chmod 755 "$ROOT/usr/bin/radthal-app" "$ROOT/usr/lib/radthal/radthal-stack" \
    "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/prerm" "$ROOT/DEBIAN/postrm"
SIZE="$(du -sk --exclude=DEBIAN "$ROOT" | cut -f1)"
echo "Installed-Size: $SIZE" >> "$ROOT/DEBIAN/control"

mkdir -p "$OUT"
dpkg-deb --root-owner-group -Zxz --build "$ROOT" "$OUT/radthal_${VERSION}_all.deb" >/dev/null
echo "$OUT/radthal_${VERSION}_all.deb"
