#!/usr/bin/env bash
set -e

VERSION="1.1.0"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PKG_NAME="strop"
ARCH="all"
BUILD_DIR="${SCRIPT_DIR}/build/deb"
PKG_DIR="${BUILD_DIR}/${PKG_NAME}_${VERSION}_${ARCH}"
DEB_FILE="${SCRIPT_DIR}/${PKG_NAME}_${VERSION}_${ARCH}.deb"
TAR_FILE="${SCRIPT_DIR}/${PKG_NAME}_${VERSION}.tar.gz"
TEMP_TAR_FILE="${BUILD_DIR}/${PKG_NAME}_${VERSION}.tar.gz"

echo "Building Debian Package: ${PKG_NAME}_${VERSION}_${ARCH}.deb..."

# 1. Clean previous build directories
rm -rf "${PKG_DIR}" "${DEB_FILE}"
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/lib/strop"
mkdir -p "${PKG_DIR}/usr/bin"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/512x512/apps"
mkdir -p "${PKG_DIR}/usr/share/doc/strop"

# 2. Copy application source files
cp -r strop.py strop_keypad.py strop_keyboard.py strop_mouse.py strop_hud.py strop_studio.py strop_macro.py strop_core "${PKG_DIR}/usr/lib/strop/"
cp -r assets "${PKG_DIR}/usr/lib/strop/"
find "${PKG_DIR}/usr/lib/strop" -type d -name "__pycache__" -exec rm -rf {} +
find "${PKG_DIR}/usr/lib/strop" -type f -name "*.pyc" -delete
cp LICENSE "${PKG_DIR}/usr/share/doc/strop/copyright"
cp LICENSES.md "${PKG_DIR}/usr/share/doc/strop/"
cp README.md "${PKG_DIR}/usr/share/doc/strop/"
cp CHANGELOG.md "${PKG_DIR}/usr/share/doc/strop/"
if [ -d docs ]; then
    cp -r docs "${PKG_DIR}/usr/share/doc/strop/"
fi

# 3. Create wrapper executables in /usr/bin
cat << 'BIN_EOF' > "${PKG_DIR}/usr/bin/strop"
#!/usr/bin/env bash
exec python3 /usr/lib/strop/strop.py "$@"
BIN_EOF
chmod +x "${PKG_DIR}/usr/bin/strop"

cat << 'BIN_EOF' > "${PKG_DIR}/usr/bin/strop-keypad"
#!/usr/bin/env bash
exec python3 /usr/lib/strop/strop_keypad.py "$@"
BIN_EOF
chmod +x "${PKG_DIR}/usr/bin/strop-keypad"

cat << 'BIN_EOF' > "${PKG_DIR}/usr/bin/strop-keyboard"
#!/usr/bin/env bash
exec python3 /usr/lib/strop/strop_keyboard.py "$@"
BIN_EOF
chmod +x "${PKG_DIR}/usr/bin/strop-keyboard"

cat << 'BIN_EOF' > "${PKG_DIR}/usr/bin/strop-mouse"
#!/usr/bin/env bash
exec python3 /usr/lib/strop/strop_mouse.py "$@"
BIN_EOF
chmod +x "${PKG_DIR}/usr/bin/strop-mouse"

cat << 'BIN_EOF' > "${PKG_DIR}/usr/bin/strop-hud"
#!/usr/bin/env bash
exec python3 /usr/lib/strop/strop_hud.py "$@"
BIN_EOF
chmod +x "${PKG_DIR}/usr/bin/strop-hud"

cat << 'BIN_EOF' > "${PKG_DIR}/usr/bin/strop-macro"
#!/usr/bin/env bash
exec python3 /usr/lib/strop/strop_macro.py "$@"
BIN_EOF
chmod +x "${PKG_DIR}/usr/bin/strop-macro"


# 4. Install Desktop File & App Icon
cat << 'DESK_EOF' > "${PKG_DIR}/usr/share/applications/com.razer.strop.desktop"
[Desktop Entry]
Name=Strop
GenericName=Razer Hardware Studio & HUD
Comment=Unified Linux Peripheral Remap Studio & In-Game Overlay for Razer Devices
Exec=strop
Icon=strop
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=true
StartupWMClass=com.razer.strop
DESK_EOF



# Install multi-resolution icons for all dock and launcher scales
mkdir -p "${PKG_DIR}/usr/share/pixmaps"

cp assets/strop_icon.png "${PKG_DIR}/usr/share/pixmaps/strop.png"

for sz in 16 24 32 48 64 128 256 512; do
    mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/${sz}x${sz}/apps"
    cp "assets/icons/strop_${sz}x${sz}.png" "${PKG_DIR}/usr/share/icons/hicolor/${sz}x${sz}/apps/strop.png"
done


# 5. Create DEBIAN/control file
INSTALLED_SIZE=$(du -sk "${PKG_DIR}/usr" | cut -f1)

cat << CTRL_EOF > "${PKG_DIR}/DEBIAN/control"
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Maintainer: Strop Contributors
Depends: python3, python3-gi, python3-evdev, gir1.2-gtk-4.0
Recommends: input-remapper, openrazer-meta | openrazer-daemon
Homepage: https://github.com/dedmo399/strop
Description: Unified Linux Peripheral Studio & HUD for Razer Hardware
 Native Linux GTK4 application suite for configuring, remapping, and customizing
 Razer keypad, keyboard, and mouse layouts with input-remapper profile integration.
 Official 1.1 device support is limited to the matrix documented in README.md.
CTRL_EOF

# 5. Create postinst and postrm scripts to refresh desktop and icon caches
cat << 'POSTINST_EOF' > "${PKG_DIR}/DEBIAN/postinst"
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    if which update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if which gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
fi
exit 0

POSTINST_EOF
chmod 755 "${PKG_DIR}/DEBIAN/postinst"

cat << 'POSTRM_EOF' > "${PKG_DIR}/DEBIAN/postrm"
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if which update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if which gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
fi
exit 0
POSTRM_EOF
chmod 755 "${PKG_DIR}/DEBIAN/postrm"

# Use readable data-file permissions and executable directory permissions.
find "${PKG_DIR}" -type d -exec chmod 755 {} +
find "${PKG_DIR}" -type f -exec chmod 644 {} +
find "${PKG_DIR}/usr/bin" -type f -exec chmod 755 {} +
chmod 755 "${PKG_DIR}/DEBIAN"
chmod 755 "${PKG_DIR}/DEBIAN/postinst"
chmod 755 "${PKG_DIR}/DEBIAN/postrm"

# 6. Build the .deb package
dpkg-deb --build --root-owner-group "${PKG_DIR}" "${DEB_FILE}"

echo "Successfully created: ${DEB_FILE}"
ls -lh "${DEB_FILE}"

# 7. Build the source release tarball (.tar.gz)
echo "Generating Source Release Archive: ${TAR_FILE}..."
rm -f "${TAR_FILE}" "${TEMP_TAR_FILE}"
tar --exclude="./.git" \
    --exclude="./.agents" \
    --exclude="./.codex" \
    --exclude="./.aws" \
    --exclude="./build" \
    --exclude="./.pytest_cache" \
    --exclude="./*.deb" \
    --exclude="./*.tar.gz" \
    --exclude="**/__pycache__" \
    --exclude="**/*.pyc" \
    -czf "${TEMP_TAR_FILE}" -C "$SCRIPT_DIR" .
mv "${TEMP_TAR_FILE}" "${TAR_FILE}"

echo "Successfully created: ${TAR_FILE}"
ls -lh "${TAR_FILE}"
