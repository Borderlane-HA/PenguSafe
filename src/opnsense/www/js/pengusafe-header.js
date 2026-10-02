/* PenguSafe 0.2.0 — a read-only indicator. The firewall owns the deadline. */
(function () {
    'use strict';
    if (window.penguSafeHeaderLoaded) return;
    window.penguSafeHeaderLoaded = true;
    function start() {
        const target = document.querySelector('header.page-head .navbar-right');
        if (!target) return; // Login and unsupported layouts have no indicator.
        const css = document.createElement('link');
        css.rel = 'stylesheet';
        css.href = '/ui/css/pengusafe-header.css?v=0.2.0';
        document.head.appendChild(css);
        const item = document.createElement('li');
        item.id = 'pengusafe-header';
        const link = document.createElement('a');
        link.href = '/ui/pengusafe/';
        link.className = 'ps-global-badge';
        link.innerHTML = '<i class="fa fa-shield" aria-hidden="true"></i> <span class="ps-global-name">PenguSafe </span><span class="ps-global-label">Checking…</span>';
        item.appendChild(link);
        target.insertBefore(item, target.firstChild);
        const label = link.querySelector('.ps-global-label');
        let state = null, synced = 0, timer = null, pending = false, stopped = false, failed = false;
        function setLabel(text, kind, title) {
            label.textContent = text;
            link.dataset.state = kind;
            link.title = title + ' Click to open PenguSafe.';
            link.setAttribute('aria-label', 'PenguSafe: ' + link.title);
        }
        function render() {
            if (!state) return;
            if (failed || performance.now() - synced > 30000) {
                setLabel('Status unknown', 'unknown', 'Unable to verify the timer. Automatic rollback may still be running.');
            } else if (state.active) {
                const remaining = Math.max(0, Math.ceil(state.remaining - (performance.now() - synced) / 1000));
                const value = remaining === 0 ? 'Rollback due' : String(Math.floor(remaining / 60)).padStart(2, '0') + ':' + String(remaining % 60).padStart(2, '0');
                const unsafe = !state.watchdog || !state.snapshot_present;
                setLabel(unsafe ? value + ' · Check!' : value, unsafe || remaining <= 60 ? 'danger' : 'armed', unsafe ? 'Safe session protection needs attention.' : 'Time until automatic rollback.');
            } else if (['rollback_failed', 'arm_failed', 'rolling_back'].includes(state.state)) {
                setLabel(state.state === 'rolling_back' ? 'Rolling back…' : 'Check status', 'danger', 'Review the safe session status.');
            } else {
                setLabel('Idle', 'idle', 'No safe session is active.');
            }
        }
        async function poll() {
            if (pending || stopped) return;
            clearTimeout(timer);
            pending = true;
            const controller = new AbortController();
            const timeout = setTimeout(function () { controller.abort(); }, 8000);
            try {
                const reply = await fetch('/api/pengusafe/session/status', {
                    credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
                    headers: {Accept: 'application/json'}
                });
                if (reply.status === 401 || reply.status === 403 || reply.redirected) {
                    item.remove(); stopped = true; return;
                }
                if (!reply.ok) throw new Error('Status request failed');
                const data = await reply.json();
                if (data.status !== 'ok' || typeof data.active !== 'boolean') throw new Error('Invalid status');
                state = data; synced = performance.now(); failed = false;
                render();
            } catch (error) {
                failed = true;
                setLabel('Status unknown', 'unknown', 'Unable to verify the timer. Automatic rollback may still be running.');
            } finally {
                clearTimeout(timeout);
                pending = false;
                if (!stopped) timer = setTimeout(poll, state && state.active ? 5000 : 15000);
            }
        }
        document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });
        window.addEventListener('pengusafe:changed', poll);
        setInterval(render, 1000);
        poll();
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
}());
