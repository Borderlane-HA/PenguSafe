#!/usr/local/bin/php
<?php

set_include_path(get_include_path() . PATH_SEPARATOR . '/usr/local/etc/inc');
require_once '/usr/local/etc/inc/config.inc';

use OPNsense\Core\Config;

if ($argc !== 2) {
    fwrite(STDERR, "usage: restore.php <snapshot>\n");
    exit(64);
}

$snapshot = $argv[1];
if (!is_file($snapshot) || !is_readable($snapshot)) {
    fwrite(STDERR, "snapshot is missing or unreadable\n");
    exit(66);
}

try {
    $config = Config::getInstance();
    if (!$config->restoreBackup($snapshot)) {
        fwrite(STDERR, "restoreBackup returned false\n");
        exit(1);
    }
    $config->forceReload();
    fwrite(STDOUT, "OK\n");
    exit(0);
} catch (Throwable $e) {
    fwrite(STDERR, $e->getMessage() . "\n");
    exit(1);
}
