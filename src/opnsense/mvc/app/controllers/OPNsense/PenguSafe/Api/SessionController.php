<?php

namespace OPNsense\PenguSafe\Api;

use OPNsense\Base\ApiControllerBase;
use OPNsense\Core\Backend;

class SessionController extends ApiControllerBase
{
    private function backendJson($action, array $params = [])
    {
        $backend = new Backend();
        $raw = trim($backend->configdpRun($action, $params));
        $result = json_decode($raw, true);
        if (!is_array($result)) {
            return [
                'status' => 'error',
                'message' => $raw !== '' ? $raw : 'PenguSafe backend returned no valid response.'
            ];
        }
        return $result;
    }

    public function statusAction()
    {
        if (!$this->request->isGet()) {
            return ['status' => 'error', 'message' => 'GET required'];
        }
        return $this->backendJson('pengusafe status');
    }

    public function historyAction()
    {
        if (!$this->request->isGet()) {
            return ['status' => 'error', 'message' => 'GET required'];
        }
        return $this->backendJson('pengusafe history', [25]);
    }

    public function armAction()
    {
        if (!$this->request->isPost()) {
            return ['status' => 'error', 'message' => 'POST required'];
        }

        $this->throwReadOnly();
        $this->throwNotFullAdmin();

        $timeout = (int)$this->request->getPost('timeout', 'int', 300);
        $allowed = [120, 300, 600, 900, 1800];
        if (!in_array($timeout, $allowed, true)) {
            return ['status' => 'error', 'message' => 'Invalid timeout'];
        }

        $comment = trim((string)$this->request->getPost('comment'));
        $comment = preg_replace('/[\x00-\x1F\x7F]/u', ' ', $comment);
        if (function_exists('mb_substr')) {
            $comment = mb_substr($comment, 0, 200);
        } else {
            $comment = substr($comment, 0, 200);
        }

        return $this->backendJson('pengusafe arm', [
            $timeout,
            $this->getUserName(),
            $comment
        ]);
    }

    public function confirmAction()
    {
        if (!$this->request->isPost()) {
            return ['status' => 'error', 'message' => 'POST required'];
        }

        $this->throwReadOnly();
        $this->throwNotFullAdmin();

        $id = (string)$this->request->getPost('session_id');
        if (!preg_match('/^ps-[0-9]{8}-[0-9]{6}-[a-f0-9]{6}$/D', $id)) {
            return ['status' => 'error', 'message' => 'Refresh the page to load the current session.'];
        }
        return $this->backendJson('pengusafe confirm', [$this->getUserName(), $id]);
    }

    public function rollbackAction()
    {
        if (!$this->request->isPost()) {
            return ['status' => 'error', 'message' => 'POST required'];
        }

        $this->throwReadOnly();
        $this->throwNotFullAdmin();

        $id = (string)$this->request->getPost('session_id');
        if (!preg_match('/^ps-[0-9]{8}-[0-9]{6}-[a-f0-9]{6}$/D', $id)) {
            return ['status' => 'error', 'message' => 'Refresh the page to load the current session.'];
        }
        return $this->backendJson('pengusafe rollback', [$this->getUserName(), $id]);
    }
}
