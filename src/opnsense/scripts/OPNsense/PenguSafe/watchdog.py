#!/usr/local/bin/python3

import json
import subprocess
import syslog
import time

STATE_FILE = "/conf/pengusafe/session.json"
MANAGER = "/usr/local/opnsense/scripts/OPNsense/PenguSafe/pengusafe.py"


def read_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def main():
    syslog.openlog("pengusafe-watchdog")
    syslog.syslog(syslog.LOG_NOTICE, "watchdog started")

    while True:
        state = read_state()
        if not state or state.get("state") != "armed":
            # Stay alive while idle: immediate re-arming must not race with exit.
            time.sleep(1)
            continue

        expires = int(state.get("expires", 0))
        if expires <= 0:
            syslog.syslog(syslog.LOG_ERR, "armed session has invalid expiry; watchdog exiting")
            return 1

        remaining = expires - int(time.time())
        if remaining <= 0:
            syslog.syslog(syslog.LOG_WARNING, "safe session expired; starting automatic rollback")
            completed = subprocess.run(
                [MANAGER, "expire", state["id"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
                check=False,
            )
            if completed.returncode != 0:
                syslog.syslog(
                    syslog.LOG_CRIT,
                    "automatic rollback failed: " + (completed.stdout or completed.stderr).strip()[:500],
                )
                # State may have changed while waiting for the manager lock.
                time.sleep(1)
                continue
            time.sleep(1)

        time.sleep(min(1, max(remaining, 1)))


if __name__ == "__main__":
    raise SystemExit(main())
