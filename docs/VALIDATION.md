# Validation — 0.2.0 alpha

Target source: OPNsense Community Edition **26.7.5**.

## Checks completed

- Isolated manager tests with temporary configuration/state files: arm, confirm,
  duplicate-session refusal, expiry, stale session IDs, manual/automatic restore,
  checksum failure, watchdog start failure, boot deadline preservation,
  interrupted rollback warning, reboot scheduling failure and uninstall refusal.
- The real restore verification code was exercised with a simulated PHP helper.
  These tests did not restore the host's configuration or reboot any machine.
- Header integration was tested against the actual 26.7.5 `head.inc` and
  `default.volt`: install, repeated install, removal and preservation of unrelated
  edits. Minimal supported/unsupported-layout tests are also bundled.
- Header JavaScript was executed in an isolated DOM/transport harness: countdown,
  stale status, idle, last-minute warning, missing protection, deadline due,
  failed requests, denied access and destination URL.
- JavaScript syntax checks for both the header asset and plugin page script.
- Python compilation and POSIX shell syntax checks for source install, uninstall,
  boot hook and package extension hooks.
- Source inspection of 26.7.5 API authentication/CSRF handling, JSON request
  parsing, backend parameter escaping, configuration restore and cache locations.

## Checks still required on OPNsense

- End-to-end source installation and deinstallation on an OPNsense test VM.
- Live configd/API integration, PHP lint/runtime execution, daemon behavior and
  actual configuration restore/reboot. PHP was unavailable in the build workspace.
- Visual header placement with the real WebUI, narrow screens and custom themes.
  The browser-based preview could not run because the browser download failed;
  DOM tests do not prove visual layout correctness.
- Browser navigation between modern MVC and legacy pages.
- Recovery across reboot, core update, storage failure and lost network access.
- Native package build and package upgrade/deinstallation hooks.

## Reproduce isolated checks

```sh
python3 tools/selftest.py
node tools/header-selftest.cjs
python3 -m compileall -q src/opnsense/scripts/OPNsense/PenguSafe
node --check src/opnsense/www/js/pengusafe-header.js
sh -n tools/install-dev.sh
sh -n tools/uninstall-dev.sh
```

On OPNsense, additionally run `php -l` on each PHP file and perform the
non-production VM acceptance plan in the README. Passing isolated checks is
not a guarantee of remote recovery.
