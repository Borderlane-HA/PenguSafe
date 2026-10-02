#!/usr/local/bin/python3
"""Install/remove only a marked script include; never restore an old core file."""
import os
import sys
import tempfile
from pathlib import Path

TARGETS = (
    Path('/usr/local/www/head.inc'),
    Path('/usr/local/opnsense/mvc/app/views/layouts/default.volt'),
)
BEGIN = '<!-- PenguSafe global timer: begin -->'
END = '<!-- PenguSafe global timer: end -->'
BLOCK = BEGIN + '\n<script defer src="/ui/js/pengusafe-header.js?v=0.2.0"></script>\n' + END + '\n'


def transform(text, install):
    while BEGIN in text:
        start = text.index(BEGIN)
        end = text.find(END, start)
        if end < 0:
            raise RuntimeError('incomplete PenguSafe marker; refusing to change header')
        end += len(END)
        if text[end:end + 1] == '\n':
            end += 1
        text = text[:start] + text[end:]
    if install:
        if text.count('</head>') != 1 or 'menu_search_box' not in text:
            raise RuntimeError('unsupported OPNsense header; expected WebUI header was not found')
        text = text.replace('</head>', BLOCK + '</head>', 1)
    return text


def atomic_write(path, text):
    stat = path.stat()
    fd, tmp = tempfile.mkstemp(prefix='.pengusafe-header-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, stat.st_mode & 0o7777)
        os.chown(tmp, stat.st_uid, stat.st_gid)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def apply(install):
    # Validate both headers before touching either one.
    changes = []
    for path in TARGETS:
        original = path.read_text(encoding='utf-8')
        changes.append((path, original, transform(original, install)))
    written = []
    try:
        for path, original, changed in changes:
            if changed != original:
                atomic_write(path, changed)
                written.append((path, original))
        if written:
            for cached in Path('/var/lib/php/cache').glob('*.php'):
                cached.unlink(missing_ok=True)
    except Exception:
        for path, original in reversed(written):
            atomic_write(path, original)
        raise


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in {'install', 'remove', 'check'}:
        sys.exit('usage: header_integration.py install|remove|check')
    try:
        if sys.argv[1] == 'check':
            for path in TARGETS:
                transform(path.read_text(encoding='utf-8'), True)
        else:
            apply(sys.argv[1] == 'install')
    except (OSError, RuntimeError) as exc:
        sys.exit('PenguSafe header integration: ' + str(exc))
