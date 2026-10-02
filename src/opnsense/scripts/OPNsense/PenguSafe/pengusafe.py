#!/usr/local/bin/python3

import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import syslog
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path

BASE_DIR = Path("/conf/pengusafe")
STATE_FILE = BASE_DIR / "session.json"
SNAPSHOT_FILE = BASE_DIR / "snapshot.xml"
HISTORY_FILE = BASE_DIR / "history.jsonl"
LOCK_FILE = BASE_DIR / ".lock"
CONFIG_FILE = Path("/conf/config.xml")
PID_FILE = Path("/var/run/pengusafe.pid")
WATCHDOG = "/usr/local/opnsense/scripts/OPNsense/PenguSafe/watchdog.py"
RESTORE = "/usr/local/opnsense/scripts/OPNsense/PenguSafe/restore.php"
DAEMON = "/usr/sbin/daemon"
SHUTDOWN = "/sbin/shutdown"
ALLOWED_TIMEOUTS = {120, 300, 600, 900, 1800}


def response(status="ok", **kwargs):
    data = {"status": status}
    data.update(kwargs)
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def ensure_storage():
    BASE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        BASE_DIR.chmod(0o700)
    except OSError:
        pass


def atomic_json(path: Path, data):
    ensure_storage()
    fd, tmp_name = tempfile.mkstemp(prefix=".pengusafe-", dir=str(BASE_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def sha256_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_xml(path: Path):
    if not path.is_file() or path.stat().st_size < 64:
        raise RuntimeError(f"invalid XML file: {path}")
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise RuntimeError(f"XML validation failed: {exc}") from exc
    if root.tag != "opnsense":
        raise RuntimeError(f"unexpected config root element: {root.tag}")


def history_add(event, session=None, actor=None, message=None):
    ensure_storage()
    item = {
        "time": int(time.time()),
        "event": event,
        "session_id": (session or {}).get("id"),
        "actor": actor,
        "comment": (session or {}).get("comment", ""),
    }
    if message:
        item["message"] = str(message)[:500]
    with HISTORY_FILE.open("a", encoding="utf-8") as handle:
        os.chmod(HISTORY_FILE, 0o600)
        handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def current_state():
    state = read_json(STATE_FILE)
    if not isinstance(state, dict):
        return None
    return state


def pid_alive(pid):
    if not isinstance(pid, int) or pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def watchdog_running():
    try:
        pid = int(PID_FILE.read_text(encoding="ascii").strip())
    except (FileNotFoundError, ValueError, OSError):
        return False
    if not pid_alive(pid):
        return False
    # Do not trust a stale pid file which may now belong to another process.
    try:
        proc = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "command="],
                              capture_output=True, text=True, timeout=5, check=False)
        return proc.returncode == 0 and WATCHDOG in proc.stdout.split()
    except (OSError, subprocess.TimeoutExpired):
        return False


def start_watchdog():
    if watchdog_running():
        return True
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    completed = subprocess.run(
        [DAEMON, "-f", "-p", str(PID_FILE), WATCHDOG],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("unable to start watchdog: " + completed.stderr.strip())
    for _ in range(20):
        if watchdog_running():
            return True
        time.sleep(0.05)
    # daemon may have forked and not created the pid file yet. Session remains
    # recoverable on next boot, but arming should fail rather than pretend safe.
    raise RuntimeError("watchdog did not create a live pid file")


def snapshot_config():
    validate_xml(CONFIG_FILE)
    ensure_storage()
    fd, tmp_name = tempfile.mkstemp(prefix="snapshot-", suffix=".xml", dir=str(BASE_DIR))
    os.close(fd)
    try:
        # OPNsense writers use an exclusive flock on config.xml.
        with CONFIG_FILE.open('rb') as source, open(tmp_name, 'wb') as target:
            fcntl.flock(source.fileno(), fcntl.LOCK_SH)
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())
        os.chmod(tmp_name, 0o600)
        with open(tmp_name, "rb") as handle:
            os.fsync(handle.fileno())
        validate_xml(Path(tmp_name))
        os.replace(tmp_name, SNAPSHOT_FILE)
        return sha256_file(SNAPSHOT_FILE)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def arm(timeout, actor, comment):
    timeout = int(timeout)
    if timeout not in ALLOWED_TIMEOUTS:
        raise RuntimeError("unsupported timeout")
    existing = current_state()
    if existing and existing.get("state") in {"armed", "rolling_back"}:
        raise RuntimeError("a safe session is already active")

    snapshot_hash = snapshot_config()
    now = int(time.time())
    session = {
        "id": "ps-" + time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + "-" + uuid.uuid4().hex[:6],
        "state": "armed",
        "started": now,
        "expires": now + timeout,
        "timeout": timeout,
        "actor": actor,
        "comment": comment,
        "snapshot_sha256": snapshot_hash,
    }
    atomic_json(STATE_FILE, session)
    history_add("armed", session, actor)
    try:
        start_watchdog()
    except Exception as exc:
        session["state"] = "arm_failed"
        session["finished"] = int(time.time())
        atomic_json(STATE_FILE, session)
        history_add("arm_failed", session, actor, exc)
        try:
            SNAPSHOT_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return session


def require_session(session, expected_id=None):
    if not session or session.get("state") != "armed":
        raise RuntimeError("no armed safe session")
    if expected_id and session.get("id") != expected_id:
        raise RuntimeError("safe session changed; refresh the page and try again")


def confirm(actor, expected_id=None):
    session = current_state()
    require_session(session, expected_id)
    if int(time.time()) >= int(session["expires"]):
        raise RuntimeError("safe session has expired; automatic rollback is due")
    session["state"] = "confirmed"
    session["finished"] = int(time.time())
    session["confirmed_by"] = actor
    atomic_json(STATE_FILE, session)
    history_add("confirmed", session, actor)
    try:
        SNAPSHOT_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    return session


def schedule_reboot(delay=3):
    # Detach the reboot so a manual rollback API call can return JSON first.
    cmd = f"sleep {int(delay)}; {SHUTDOWN} -r now"
    completed = subprocess.run(
        [DAEMON, "-f", "/bin/sh", "-c", cmd],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=10, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("unable to schedule reboot: " + completed.stderr.strip()[:500])


def restore_snapshot(session):
    if not SNAPSHOT_FILE.is_file():
        raise RuntimeError("protected snapshot is missing")
    validate_xml(SNAPSHOT_FILE)
    expected = session.get("snapshot_sha256", "")
    actual = sha256_file(SNAPSHOT_FILE)
    if not expected or actual != expected:
        raise RuntimeError("protected snapshot checksum mismatch")

    completed = subprocess.run(
        [RESTORE, str(SNAPSHOT_FILE)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0 or completed.stdout.strip() != "OK":
        raise RuntimeError("OPNsense config restore failed: " + completed.stderr.strip()[:500])

    # Validate what is now actually on disk before allowing a reboot.
    validate_xml(CONFIG_FILE)
    if sha256_file(CONFIG_FILE) != actual:
        raise RuntimeError("restored /conf/config.xml does not match the protected snapshot")


def rollback(actor, automatic=False, expected_id=None):
    session = current_state()
    require_session(session, expected_id)
    if automatic and int(time.time()) < int(session["expires"]):
        raise RuntimeError("safe session has not expired")

    session["state"] = "rolling_back"
    session["rollback_started"] = int(time.time())
    session["rollback_by"] = actor
    atomic_json(STATE_FILE, session)
    history_add("rollback_started", session, actor, "automatic" if automatic else "manual")

    try:
        restore_snapshot(session)
    except Exception as exc:
        session["state"] = "rollback_failed"
        session["finished"] = int(time.time())
        session["error"] = str(exc)[:500]
        atomic_json(STATE_FILE, session)
        history_add("rollback_failed", session, actor, exc)
        raise

    session["state"] = "rolled_back"
    session["finished"] = int(time.time())
    atomic_json(STATE_FILE, session)
    history_add("rolled_back", session, actor, "reboot scheduled")
    try:
        schedule_reboot(0 if automatic else 3)
    except Exception as exc:
        session['state'] = 'rollback_failed'
        session['configuration_restored'] = True
        session['error'] = 'Configuration restored, but reboot scheduling failed: ' + str(exc)[:400]
        atomic_json(STATE_FILE, session)
        history_add('rollback_failed', session, actor, session['error'])
        raise
    return session


def status():
    session = current_state()
    if not session:
        return {
            "status": "ok",
            "active": False,
            "state": "idle",
            "watchdog": False,
            "server_time": int(time.time()),
        }
    now = int(time.time())
    result = dict(session)
    result.update({
        "status": "ok",
        "active": session.get("state") == "armed",
        "remaining": max(0, int(session.get("expires", 0)) - now) if session.get("state") == "armed" else 0,
        "watchdog": watchdog_running(),
        "snapshot_present": SNAPSHOT_FILE.is_file(),
        "server_time": now,
    })
    return result


def history(limit):
    try:
        limit = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        limit = 25
    rows = []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as handle:
            lines = deque(handle, maxlen=limit)
        for line in reversed(lines):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except FileNotFoundError:
        pass
    return {"status": "ok", "rows": rows, "count": len(rows)}


def resume():
    session = current_state()
    if session and session.get('state') == 'rolling_back':
        raise RuntimeError('previous rollback was interrupted; review the snapshot and configuration from the console')
    if not session or session.get("state") != "armed":
        return {"status": "ok", "resumed": False}
    start_watchdog()
    history_add("watchdog_resumed", session, "system")
    return {"status": "ok", "resumed": True, "session_id": session.get("id")}


def prepare_uninstall():
    session = current_state()
    if session and session.get("state") in {"armed", "rolling_back"}:
        raise RuntimeError("cannot uninstall during an active safe session; confirm or roll back first")
    if watchdog_running():
        pid = int(PID_FILE.read_text(encoding="ascii").strip())
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if not watchdog_running():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("watchdog did not stop; uninstall cancelled")
    PID_FILE.unlink(missing_ok=True)
    return {"status": "ok", "ready": True}


def locked_call(fn, *args):
    ensure_storage()
    with LOCK_FILE.open("a+") as lock:
        os.chmod(LOCK_FILE, 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return fn(*args)


def main(argv):
    syslog.openlog("pengusafe")
    if len(argv) < 2:
        response("error", message="missing command")
        return 64

    command = argv[1]
    try:
        if command == "status":
            response(**status())
        elif command == "history":
            result = history(argv[2] if len(argv) > 2 else 25)
            response(**result)
        elif command == "arm":
            if len(argv) != 5:
                raise RuntimeError("arm requires timeout, actor and comment")
            session = locked_call(arm, argv[2], argv[3], argv[4])
            response("ok", active=True, session=session, remaining=session["timeout"])
        elif command == "confirm":
            if len(argv) not in {3, 4}:
                raise RuntimeError("confirm requires actor and optional session id")
            session = locked_call(confirm, argv[2], argv[3] if len(argv) == 4 else None)
            response("ok", active=False, state="confirmed", session=session)
        elif command == "rollback":
            if len(argv) not in {3, 4}:
                raise RuntimeError("rollback requires actor and optional session id")
            session = locked_call(rollback, argv[2], False, argv[3] if len(argv) == 4 else None)
            response("ok", active=False, state="rolled_back", rebooting=True, session=session)
        elif command == "expire":
            if len(argv) != 3:
                raise RuntimeError("expire requires session id")
            session = locked_call(rollback, "watchdog", True, argv[2])
            response("ok", active=False, state="rolled_back", rebooting=True, session=session)
        elif command == "prepare-uninstall":
            response(**locked_call(prepare_uninstall))
        elif command == "resume":
            result = locked_call(resume)
            response(**result)
        else:
            response("error", message="unknown command")
            return 64
    except Exception as exc:
        syslog.syslog(syslog.LOG_ERR, f"{command} failed: {exc}")
        response("error", message=str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
