<style>
    .ps-hero { padding: 22px 24px; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 20px; }
    .ps-title { display:flex; align-items:center; gap:10px; margin:0 0 8px 0; }
    .ps-title i { font-size:26px; }
    .ps-subtitle { opacity:.75; margin-bottom:0; }
    .ps-panel { border:1px solid #ddd; border-radius:6px; padding:20px; margin-bottom:20px; }
    .ps-status-line { display:flex; align-items:center; gap:10px; font-size:16px; margin-bottom:12px; }
    .ps-dot { width:10px; height:10px; border-radius:50%; display:inline-block; background:#888; }
    .ps-dot.safe { background:#5cb85c; }
    .ps-dot.armed { background:#f0ad4e; }
    .ps-dot.danger { background:#d9534f; }
    .ps-countdown { font-size:42px; font-weight:600; letter-spacing:1px; margin:14px 0 4px; font-variant-numeric:tabular-nums; }
    .ps-meta { opacity:.75; margin-bottom:16px; }
    .ps-actions { display:flex; gap:10px; flex-wrap:wrap; margin-top:18px; }
    .ps-form-row { margin-bottom:15px; }
    .ps-form-row label { display:block; margin-bottom:6px; }
    .ps-history td { vertical-align:top !important; }
    .ps-muted { opacity:.7; }
    .ps-warning { margin-top:12px; }
</style>

<div class="ps-hero">
    <h2 class="ps-title"><i class="fa fa-shield"></i> PenguSafe</h2>
    <p class="ps-subtitle">Safe configuration changes with local automatic rollback.</p>
</div>

<div id="psMessage" class="alert hidden" role="alert"></div>

<div class="ps-panel" id="psIdlePanel">
    <div class="ps-status-line"><span class="ps-dot safe"></span><strong>Safe Change Mode is idle</strong></div>
    <p>No protected configuration session is active.</p>

    <div class="row">
        <div class="col-md-4 ps-form-row">
            <label for="psTimeout">Automatic rollback after</label>
            <select id="psTimeout" class="form-control">
                <option value="120">2 minutes</option>
                <option value="300" selected>5 minutes</option>
                <option value="600">10 minutes</option>
                <option value="900">15 minutes</option>
                <option value="1800">30 minutes</option>
            </select>
        </div>
        <div class="col-md-8 ps-form-row">
            <label for="psComment">Comment</label>
            <input id="psComment" type="text" maxlength="200" class="form-control" placeholder="e.g. IoT VLAN migration">
        </div>
    </div>

    <button class="btn btn-primary" id="psArm"><i class="fa fa-shield"></i> Start Safe Session</button>
    <div class="alert alert-warning ps-warning">
        PenguSafe 0.2.0 is an alpha safety feature. Test it on a non-production OPNsense VM before relying on it remotely.
    </div>
</div>

<div class="ps-panel hidden" id="psActivePanel">
    <div class="ps-status-line"><span id="psActiveDot" class="ps-dot armed"></span><strong>Safe Session Active</strong></div>
    <div class="ps-countdown" id="psCountdown">--:--</div>
    <div class="ps-meta" id="psDeadline">until automatic rollback</div>
    <p><strong>Comment:</strong> <span id="psActiveComment">—</span></p>
    <p><strong>Started by:</strong> <span id="psActor">—</span></p>
    <p><strong>Watchdog:</strong> <span id="psWatchdog">—</span></p>
    <p><strong>Snapshot:</strong> <span id="psSnapshot">—</span></p>

    <div class="ps-actions">
        <button class="btn btn-danger" id="psRollback"><i class="fa fa-undo"></i> Rollback Now</button>
        <button class="btn btn-success" id="psConfirm"><i class="fa fa-check"></i> Confirm Changes</button>
    </div>
</div>

<div class="ps-panel">
    <h4>Recent activity</h4>
    <div class="table-responsive">
        <table class="table table-striped table-condensed ps-history">
            <thead><tr><th>Time</th><th>Event</th><th>User</th><th>Comment</th></tr></thead>
            <tbody id="psHistory"><tr><td colspan="4" class="ps-muted">Loading…</td></tr></tbody>
        </table>
    </div>
</div>

<script>
$(document).ready(function() {
    let serverRemaining = 0;
    let lastSync = 0;
    let activeSession = false;
    let sessionId = null;
    let statusPending = false;
    let statusKnown = false;
    let actionPending = false;

    function showMessage(type, text) {
        $('#psMessage').removeClass('hidden alert-success alert-info alert-warning alert-danger')
            .addClass('alert-' + type).text(text);
    }

    function fmt(seconds) {
        seconds = Math.max(0, parseInt(seconds || 0, 10));
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    }

    function renderCountdown() {
        if (!activeSession) return;
        const elapsed = Math.floor((performance.now() - lastSync) / 1000);
        if (!statusKnown || elapsed > 15) {
            $('#psCountdown').text('Status unknown');
            $('#psConfirm,#psRollback').prop('disabled', true);
            return;
        }
        const remaining = Math.max(0, serverRemaining - elapsed);
        $('#psCountdown').text(remaining === 0 ? 'Rollback due' : fmt(remaining));
        $('#psConfirm').prop('disabled', actionPending || remaining <= 0);
        $('#psRollback').prop('disabled', actionPending);
        $('#psActiveDot').toggleClass('danger', remaining <= 60).toggleClass('armed', remaining > 60);
    }

    function loadStatus() {
        if (statusPending || actionPending) return;
        statusPending = true;
        $.ajax({url: '/api/pengusafe/session/status', type: 'GET', dataType: 'json', timeout: 8000, global: false})
        .done(function(data) {
            statusPending = false;
            if (data.status !== 'ok') {
                statusKnown = false;
                $('#psArm,#psConfirm,#psRollback').prop('disabled', true);
                showMessage('danger', data.message || 'Unable to read PenguSafe status.');
                return;
            }
            statusKnown = true;
            sessionId = data.id || null;
            activeSession = !!data.active;
            $('#psArm').prop('disabled', actionPending || ['rolling_back', 'rollback_failed'].includes(data.state));
            if (['arm_failed', 'rollback_failed', 'rolling_back'].includes(data.state)) {
                showMessage('danger', data.error || 'Session state: ' + data.state + '. Review the logs and use console access if needed.');
            }
            if (activeSession) {
                serverRemaining = parseInt(data.remaining || 0, 10);
                lastSync = performance.now();
                $('#psIdlePanel').addClass('hidden');
                $('#psActivePanel').removeClass('hidden');
                $('#psActiveComment').text(data.comment || '—');
                $('#psActor').text(data.actor || '—');
                $('#psWatchdog').html(data.watchdog ? '<span class="text-success">running</span>' : '<span class="text-danger">not running</span>');
                $('#psSnapshot').html(data.snapshot_present ? '<span class="text-success">protected</span>' : '<span class="text-danger">missing</span>');
                renderCountdown();
            } else {
                $('#psActivePanel').addClass('hidden');
                $('#psIdlePanel').removeClass('hidden');
            }
        }).fail(function() {
            statusPending = false;
            statusKnown = false;
            $('#psArm,#psConfirm,#psRollback').prop('disabled', true);
            showMessage('warning', 'Unable to verify PenguSafe status. Automatic rollback may still be running.');
        });
    }

    function loadHistory() {
        ajaxGet('/api/pengusafe/session/history', {}, function(data) {
            const body = $('#psHistory').empty();
            if (!data.rows || data.rows.length === 0) {
                body.append('<tr><td colspan="4" class="ps-muted">No activity yet.</td></tr>');
                return;
            }
            data.rows.forEach(function(row) {
                const when = row.time ? new Date(row.time * 1000).toLocaleString() : '—';
                $('<tr>')
                    .append($('<td>').text(when))
                    .append($('<td>').text(row.event || '—'))
                    .append($('<td>').text(row.actor || '—'))
                    .append($('<td>').text(row.comment || ''))
                    .appendTo(body);
            });
        });
    }

    $('#psArm').prop('disabled', true).click(function() {
        if (!statusKnown || actionPending) return;
        actionPending = true;
        $('#psArm').prop('disabled', true);
        ajaxCall('/api/pengusafe/session/arm', {
            timeout: $('#psTimeout').val(),
            comment: $('#psComment').val()
        }, function(data) {
            actionPending = false;
            window.dispatchEvent(new Event('pengusafe:changed'));
            $('#psArm').prop('disabled', false);
            if (data.status === 'ok') {
                showMessage('success', 'Safe Session armed. The local rollback watchdog is active.');
                loadStatus(); loadHistory();
            } else {
                showMessage('danger', data.message || 'Unable to arm Safe Session.');
            }
        });
    });

    $('#psConfirm').click(function() {
        if (!confirm('Confirm the current OPNsense configuration and cancel automatic rollback?')) return;
        if (!sessionId || actionPending || !statusKnown) return;
        actionPending = true;
        $('#psConfirm,#psRollback').prop('disabled', true);
        ajaxCall('/api/pengusafe/session/confirm', {session_id: sessionId}, function(data) {
            actionPending = false;
            window.dispatchEvent(new Event('pengusafe:changed'));
            $('#psConfirm,#psRollback').prop('disabled', false);
            if (data.status === 'ok') {
                showMessage('success', 'Changes confirmed. Automatic rollback has been cancelled.');
                loadStatus(); loadHistory();
            } else {
                showMessage('danger', data.message || 'Unable to confirm Safe Session.');
            }
        });
    });

    $('#psRollback').click(function() {
        if (!confirm('Restore the protected configuration now? OPNsense will reboot.')) return;
        if (!sessionId || actionPending || !statusKnown) return;
        actionPending = true;
        $('#psConfirm,#psRollback').prop('disabled', true);
        ajaxCall('/api/pengusafe/session/rollback', {session_id: sessionId}, function(data) {
            if (data.status === 'ok') {
                showMessage('warning', 'Protected configuration restored. OPNsense is rebooting.');
            } else {
                actionPending = false;
                loadStatus();
                $('#psConfirm,#psRollback').prop('disabled', false);
                showMessage('danger', data.message || 'Rollback failed.');
            }
        });
    });

    document.addEventListener('visibilitychange', function() { if (!document.hidden) loadStatus(); });
    loadStatus();
    loadHistory();
    setInterval(renderCountdown, 250);
    setInterval(loadStatus, 5000);
    setInterval(loadHistory, 15000);
});
</script>
