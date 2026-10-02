#!/bin/sh
set -eu
if [ "$(id -u)" -ne 0 ]; then echo "Run as root." >&2; exit 1; fi
if [ "$(uname -s)" != FreeBSD ] || [ ! -f /usr/local/etc/inc/config.inc ]; then
    echo "This uninstaller requires an OPNsense firewall." >&2; exit 1
fi
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SCRIPTS="$ROOT/src/opnsense/scripts/OPNsense/PenguSafe"
# Use this release's manager also when removing an earlier source install.
/usr/local/bin/python3 "$SCRIPTS/pengusafe.py" prepare-uninstall
/usr/local/bin/python3 "$SCRIPTS/header_integration.py" remove
rm -rf /usr/local/opnsense/mvc/app/controllers/OPNsense/PenguSafe
rm -rf /usr/local/opnsense/mvc/app/models/OPNsense/PenguSafe
rm -rf /usr/local/opnsense/mvc/app/views/OPNsense/PenguSafe
rm -rf /usr/local/opnsense/scripts/OPNsense/PenguSafe
rm -f /usr/local/opnsense/service/conf/actions.d/actions_pengusafe.conf
rm -f /usr/local/etc/rc.syshook.d/start/50-pengusafe
rm -f /usr/local/opnsense/www/js/pengusafe-header.js /usr/local/opnsense/www/css/pengusafe-header.css
service configd restart
rm -f /var/lib/php/tmp/opnsense_menu_cache.xml /var/lib/php/tmp/opnsense_acl_cache.json
rm -f /var/lib/php/cache/*.php

echo "PenguSafe source files removed. /conf/pengusafe was preserved. Hard-refresh the WebUI."
