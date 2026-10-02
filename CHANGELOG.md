# Changelog

## 0.2.0 — 2026-10-02 (alpha)

- Add a clickable global PenguSafe status badge and countdown to the top-right
  WebUI header, including legacy pages. The badge opens System → PenguSafe.
- Show idle, active, last-minute warning, protection warning and unknown status.
- Use GET requests for status and history, matching the API method requirements.
- Reject confirmations after the deadline.
- Bind WebUI confirm/rollback requests and watchdog expiry to their session ID;
  recheck the deadline under the manager lock to avoid acting on a newer session.
- Keep the watchdog alive while idle to avoid an immediate re-arm/exit race.
- Validate watchdog process identity rather than trusting a stale PID file.
- Refuse source upgrades and uninstall while armed/rolling back; stop the idle
  watchdog before removing or replacing its code.
- Copy the configuration under the OPNsense file lock.
- Read recent history with bounded memory and improve watchdog error logging.
- Record reboot scheduling failures and report interrupted rollback on boot.
- Add reversible, idempotent header integration and boot-time reapplication.
- Refresh the actual OPNsense 26.7.5 menu/ACL caches after source installation.
- Add package header install/remove hooks for developer builds.
- Add English GitHub installation, upgrade, uninstall, testing and recovery docs,
  alpha guidance, a README hero and automated regression checks.

## 0.1.0 — Initial alpha

- Safe sessions, protected snapshots, local watchdog, manual confirmation,
  manual/automatic full configuration rollback and reboot, persistent history.
