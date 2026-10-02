#!/usr/bin/env python3
"""Run with temporary configs; never restore or reboot the host."""
import importlib.util
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'src/opnsense/scripts/OPNsense/PenguSafe'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rejects(fn, text):
    try:
        fn()
    except RuntimeError as exc:
        assert text in str(exc), str(exc)
    else:
        raise AssertionError('Expected refusal: ' + text)


ps = load('pengusafe')
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp) / 'pengusafe'
    conf = Path(tmp) / 'config.xml'
    original = "<?xml version='1.0'?><opnsense><system><hostname>test</hostname></system></opnsense>"
    conf.write_text(original)
    ps.BASE_DIR, ps.CONFIG_FILE = base, conf
    ps.STATE_FILE, ps.SNAPSHOT_FILE = base / 'session.json', base / 'snapshot.xml'
    ps.HISTORY_FILE, ps.LOCK_FILE = base / 'history.jsonl', base / '.lock'
    ps.PID_FILE = Path(tmp) / 'pengusafe.pid'
    ps.start_watchdog = lambda: True
    ps.watchdog_running = lambda: True
    reboots = []
    ps.schedule_reboot = lambda delay=3: reboots.append(delay)

    session = ps.locked_call(ps.arm, 120, 'tester', 'confirm test')
    assert ps.status()['active'] and ps.SNAPSHOT_FILE.read_text() == original
    assert base.stat().st_mode & 0o777 == 0o700
    assert ps.SNAPSHOT_FILE.stat().st_mode & 0o777 == 0o600
    rejects(lambda: ps.locked_call(ps.arm, 120, 'tester', ''), 'already active')
    rejects(lambda: ps.locked_call(ps.prepare_uninstall), 'cannot uninstall')
    rejects(lambda: ps.locked_call(ps.confirm, 'tester', 'stale-id'), 'changed')
    rejects(lambda: ps.locked_call(ps.rollback, 'watchdog', True, session['id']), 'not expired')
    ps.locked_call(ps.confirm, 'tester', session['id'])
    assert not ps.SNAPSHOT_FILE.exists() and not ps.status()['active'] and not reboots

    new = ps.locked_call(ps.arm, 120, 'tester', 'rollback test')
    rejects(lambda: ps.locked_call(ps.rollback, 'watchdog', True, session['id']), 'changed')
    conf.write_text(original.replace('test', 'changed'))
    # Exercise the actual checksum / XML / post-restore verification code.
    class Result:
        returncode = 0
        stdout = 'OK\n'
        stderr = ''
    def fake_restore(*args, **kwargs):
        shutil.copyfile(ps.SNAPSHOT_FILE, conf)
        return Result()
    ps.subprocess.run = fake_restore
    ps.locked_call(ps.rollback, 'tester', False, new['id'])
    assert conf.read_text() == original and reboots == [3]

    new = ps.locked_call(ps.arm, 120, 'tester', 'checksum test')
    ps.SNAPSHOT_FILE.write_text(original.replace('test', 'tampered'))
    rejects(lambda: ps.locked_call(ps.rollback, 'tester', False, new['id']), 'checksum mismatch')
    assert ps.status()['state'] == 'rollback_failed' and reboots == [3]

    new = ps.locked_call(ps.arm, 120, 'tester', 'expired test')
    new['expires'] = int(ps.time.time()) - 1
    ps.atomic_json(ps.STATE_FILE, new)
    rejects(lambda: ps.locked_call(ps.confirm, 'tester', new['id']), 'expired')
    assert ps.status()['active']
    ps.locked_call(ps.rollback, 'watchdog', True, new['id'])
    assert reboots == [3, 0]

    # Persisted original deadline is reused at boot; it is not reset.
    new = ps.locked_call(ps.arm, 120, 'tester', 'resume test')
    assert ps.locked_call(ps.resume)['resumed']
    assert ps.current_state()['expires'] == new['expires']
    ps.locked_call(ps.confirm, 'tester', new['id'])
    new = ps.locked_call(ps.arm, 120, 'tester', 'reboot failure')
    def fail_reboot(delay=3):
        raise RuntimeError('daemon rejected reboot')
    ps.schedule_reboot = fail_reboot
    rejects(lambda: ps.locked_call(ps.rollback, 'tester', False, new['id']), 'daemon rejected')
    assert ps.status()['state'] == 'rollback_failed'
    assert ps.status()['configuration_restored'] is True
    interrupted = ps.current_state()
    interrupted['state'] = 'rolling_back'
    ps.atomic_json(ps.STATE_FILE, interrupted)
    rejects(lambda: ps.locked_call(ps.resume), 'interrupted')
    interrupted['state'] = 'rollback_failed'
    ps.atomic_json(ps.STATE_FILE, interrupted)

    def fail_start():
        raise RuntimeError('watchdog start failure')
    ps.start_watchdog = fail_start
    rejects(lambda: ps.locked_call(ps.arm, 120, 'tester', ''), 'watchdog start failure')
    assert ps.status()['state'] == 'arm_failed' and not ps.SNAPSHOT_FILE.exists()
    assert ps.history(5)['count'] == 5
    ps.watchdog_running = lambda: False
    assert ps.locked_call(ps.prepare_uninstall)['ready']

header = load('header_integration')
minimal = '<html><head><script>var menu_search_box;</script></head></html>'
assert header.transform(header.transform(minimal, True), False) == minimal
assert header.transform(header.transform(minimal, True), True).count(header.BEGIN) == 1
for fixture in ['head-26.7.5.inc', 'default.volt']:
    path = ROOT.parent.parent / fixture
    if path.exists():
        text = path.read_text()
        installed = header.transform(text, True)
        assert installed.count(header.BEGIN) == 1
        assert header.transform(installed, True) == installed
        assert header.transform(installed, False) == text
        changed = installed.replace('no-js', 'external-update')
        assert 'external-update' in header.transform(changed, False)
rejects(lambda: header.transform('<head></head>', True), 'unsupported')
rejects(lambda: header.transform(header.BEGIN + '<head></head>', False), 'incomplete')
print('PenguSafe: state, expiry, stale-session, integrity, uninstall and header tests passed.')
