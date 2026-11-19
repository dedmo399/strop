#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
VERSION="$(PYTHONPATH="$SCRIPT_DIR" python3 -c 'import strop_core; print(strop_core.__version__)')"

PKG_NAME="strop"
PKGREL="${PKGREL:-1}"
BUILD_DIR="${SCRIPT_DIR}/build/arch"
SOURCE_MANIFEST="${BUILD_DIR}/.strop-source-files"
TAR_NAME="${PKG_NAME}_${VERSION}.tar.gz"
STAGED_TAR="${BUILD_DIR}/${TAR_NAME}"
OUT_PKG_GLOB="${PKG_NAME}-${VERSION}-${PKGREL}-any.pkg.tar.*"
ARCH_IMAGE="${STROP_ARCH_IMAGE:-archlinux:base-devel}"

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

if [ -f "${SCRIPT_DIR}/.strop-source-files" ]; then
    cp "${SCRIPT_DIR}/.strop-source-files" "$SOURCE_MANIFEST"
elif command -v git >/dev/null 2>&1 && \
    [ "$(GIT_DISCOVERY_ACROSS_FILESYSTEM=1 git rev-parse --show-toplevel 2>/dev/null || true)" = "$SCRIPT_DIR" ]; then
    GIT_DISCOVERY_ACROSS_FILESYSTEM=1 git ls-files -z > "$SOURCE_MANIFEST"
else
    echo "Cannot identify source files: use a Git checkout or a Strop source release." >&2
    exit 1
fi

echo "Staging source tarball for Arch/CachyOS build: ${TAR_NAME}..."
tar -czf "${STAGED_TAR}" \
    -C "$BUILD_DIR" .strop-source-files \
    -C "$SCRIPT_DIR" --null --verbatim-files-from --no-recursion \
    --files-from="$SOURCE_MANIFEST"

TAR_SHA256="$(sha256sum "${STAGED_TAR}" | awk '{print $1}')"

sed \
    -e "s/^pkgver=.*/pkgver=${VERSION}/" \
    -e "s/^pkgrel=.*/pkgrel=${PKGREL}/" \
    -e "s/^sha256sums=.*/sha256sums=('${TAR_SHA256}')/" \
    "${SCRIPT_DIR}/packaging/arch/PKGBUILD" > "${BUILD_DIR}/PKGBUILD"

echo "Building Arch/CachyOS package (${PKG_NAME} ${VERSION}-${PKGREL}, arch=any)..."

if command -v makepkg >/dev/null 2>&1; then
    (
        cd "${BUILD_DIR}"
        makepkg -f --nodeps --clean
    )
elif command -v docker >/dev/null 2>&1 || command -v podman >/dev/null 2>&1; then
    CONTAINER_RT="docker"
    if ! command -v docker >/dev/null 2>&1; then
        CONTAINER_RT="podman"
    fi
    echo "Using ${CONTAINER_RT} (${ARCH_IMAGE}) to run makepkg..."
    "${CONTAINER_RT}" run --rm \
        -v "${BUILD_DIR}:/work" \
        -e "HOST_UID=$(id -u)" \
        -e "HOST_GID=$(id -g)" \
        "${ARCH_IMAGE}" \
        bash -euo pipefail -c '
            if ! command -v python >/dev/null 2>&1; then
                pacman -Sy --noconfirm --needed python
            fi
            useradd -m -s /bin/bash builder
            cp -a /work /home/builder/work
            chown -R builder:builder /home/builder/work
            su - builder -c "cd /home/builder/work && makepkg -f --nodeps --clean"
            cp -f /home/builder/work/strop-*.pkg.tar.* /work/
            chown "${HOST_UID}:${HOST_GID}" /work/strop-*.pkg.tar.*
        '
else
    echo "Error: makepkg, docker, or podman is required to build Arch/CachyOS packages." >&2
    exit 1
fi

shopt -s nullglob
BUILT_PKGS=( "${BUILD_DIR}"/${OUT_PKG_GLOB} )
if [ "${#BUILT_PKGS[@]}" -eq 0 ]; then
    echo "Error: expected package matching ${BUILD_DIR}/${OUT_PKG_GLOB} was not produced." >&2
    exit 1
fi

for pkg in "${BUILT_PKGS[@]}"; do
    out_file="${SCRIPT_DIR}/$(basename "$pkg")"
    cp -f "$pkg" "$out_file"
    echo "Successfully created: ${out_file}"
    ls -lh "${out_file}"
    sha256sum "${out_file}"
done
