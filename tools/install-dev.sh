#!/bin/sh
set -eu
if [ "$(id -u)" -ne 0 ]; then echo "Run as root." >&2; exit 1; fi
if [ "$(uname -s)" != FreeBSD ] || [ ! -f /usr/local/etc/inc/config.inc ]; then
    echo "This installer requires an OPNsense firewall." >&2; exit 1
fi
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SCRIPTS="$ROOT/src/opnsense/scripts/OPNsense/PenguSafe"
# Preflight before modifying installed files; refuse upgrades during active sessions.
/usr/local/bin/python3 "$SCRIPTS/header_integration.py" check
/usr/local/bin/python3 "$SCRIPTS/pengusafe.py" prepare-uninstall
cp -R "$ROOT/src/opnsense/." /usr/local/opnsense/
cp -R "$ROOT/src/etc/." /usr/local/etc/
chmod 700 /usr/local/opnsense/scripts/OPNsense/PenguSafe/*.py
chmod 700 /usr/local/opnsense/scripts/OPNsense/PenguSafe/restore.php
chmod 755 /usr/local/etc/rc.syshook.d/start/50-pengusafe
chmod 644 /usr/local/opnsense/www/js/pengusafe-header.js /usr/local/opnsense/www/css/pengusafe-header.css
/usr/local/opnsense/scripts/OPNsense/PenguSafe/header_integration.py install
service configd restart
# Refresh menu/ACL registrations and compiled views on OPNsense 26.7.5.
rm -f /var/lib/php/tmp/opnsense_menu_cache.xml /var/lib/php/tmp/opnsense_acl_cache.json
rm -f /var/lib/php/cache/*.php

echo "PenguSafe 0.2.0 alpha installed. Log out/in, then hard-refresh the WebUI."
