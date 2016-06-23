# -*- coding: utf-8 -*-
"""Setup tests for this package."""
from imio.zamqp.dms.testing import IMIO_ZAMQP_DMS_INTEGRATION_TESTING  # noqa
from plone import api

import unittest


class TestSetup(unittest.TestCase):
    """Test that imio.zamqp.dms is properly installed."""

    layer = IMIO_ZAMQP_DMS_INTEGRATION_TESTING

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')

    def test_product_installed(self):
        """Test if imio.zamqp.dms is installed."""
        self.assertTrue(self.installer.isProductInstalled(
            'imio.zamqp.dms'))

    def test_browserlayer(self):
        """Test that IImioZamqpDmsLayer is registered."""
        from imio.zamqp.dms.interfaces import (
            IImioZamqpDmsLayer)
        from plone.browserlayer import utils
        self.assertIn(IImioZamqpDmsLayer, utils.registered_layers())


class TestUninstall(unittest.TestCase):

    layer = IMIO_ZAMQP_DMS_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')
        self.installer.uninstallProducts(['imio.zamqp.dms'])

    def test_product_uninstalled(self):
        """Test if imio.zamqp.dms is cleanly uninstalled."""
        self.assertFalse(self.installer.isProductInstalled(
            'imio.zamqp.dms'))

    def test_browserlayer_removed(self):
        """Test that IImioZamqpDmsLayer is removed."""
        from imio.zamqp.dms.interfaces import IImioZamqpDmsLayer
        from plone.browserlayer import utils
        self.assertNotIn(IImioZamqpDmsLayer, utils.registered_layers())
