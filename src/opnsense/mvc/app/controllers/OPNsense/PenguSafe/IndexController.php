<?php

namespace OPNsense\PenguSafe;

class IndexController extends \OPNsense\Base\IndexController
{
    public function indexAction()
    {
        $this->view->pick('OPNsense/PenguSafe/index');
    }
}
