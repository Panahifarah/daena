#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-0.1.0}"
PACKAGE="daena_${VERSION}_all"
BUILDROOT="/tmp/build/${PACKAGE}"
DISTDIR="dist"

pip install uv --quiet
uv sync --no-dev --frozen --quiet

# Create package directory structure
rm -rf "${BUILDROOT}"
mkdir -p "${BUILDROOT}/DEBIAN"
mkdir -p "${BUILDROOT}/usr/bin"
mkdir -p "${BUILDROOT}/usr/lib/python3/dist-packages"
mkdir -p "${BUILDROOT}/lib/systemd/system"
mkdir -p "${BUILDROOT}/etc/daena"

# Install the package and all dependencies into dist-packages
uv pip install --python "$(which python3)" \
    --target="${BUILDROOT}/usr/lib/python3/dist-packages" \
    --no-compile \
    . 2>/dev/null

# Install script entry points
cat > "${BUILDROOT}/usr/bin/daena" << 'SCRIPT'
#!/usr/bin/env python3
from daena.cli.main import app
app()
SCRIPT
chmod +x "${BUILDROOT}/usr/bin/daena"

cat > "${BUILDROOT}/usr/bin/daena-serve" << 'SCRIPT'
#!/usr/bin/env python3
from daena.app import serve
serve()
SCRIPT
chmod +x "${BUILDROOT}/usr/bin/daena-serve"

# Install systemd service
cp deploy/daena.service "${BUILDROOT}/lib/systemd/system/daena.service"

# Install default config
cp config/daena.yaml "${BUILDROOT}/etc/daena/daena.yaml"

# Install maintainer scripts
cp debian/postinst "${BUILDROOT}/DEBIAN/postinst"
cp debian/prerm "${BUILDROOT}/DEBIAN/prerm"
chmod 755 "${BUILDROOT}/DEBIAN/postinst" "${BUILDROOT}/DEBIAN/prerm"

# Compute installed size (in KB)
INSTALLED_SIZE=$(du -sk "${BUILDROOT}" | cut -f1)

# Generate control file
cat > "${BUILDROOT}/DEBIAN/control" << CONTROL
Package: daena
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Maintainer: Amir Husayn Panahifar <ahp@panahifar.ir>
Installed-Size: ${INSTALLED_SIZE}
Depends: python3 (>= 3.13), python3-pip, liblmdb0
Recommends: systemd
Description: Collect, buffer, and forward logs and events
 Daena is a modular, extensible Linux service that collects
 logs, events, and telemetry from pluggable sources, processes
 them through a configurable pipeline, persists data locally
 in LMDB, and forwards records reliably to remote sinks.
CONTROL

# Build .deb
mkdir -p "${DISTDIR}"
fakeroot dpkg-deb --build "${BUILDROOT}" "${DISTDIR}/${PACKAGE}.deb"

echo "Built: ${DISTDIR}/${PACKAGE}.deb"
