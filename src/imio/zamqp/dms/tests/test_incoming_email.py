# -*- coding: utf-8 -*-

# from imio.zamqp.dms.testing import ZAMQP_INTEGRATION_TESTING
from imio.dms.mail.testing import DMSMAIL_INTEGRATION_TESTING
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

import unittest


class TestDmsfile(unittest.TestCase):

    layer = DMSMAIL_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.pc = self.portal.portal_catalog
        self.imf = self.portal['incoming-mail']
        self.omf = self.portal['outgoing-mail']

    def test_IncomingEmail_base(self):
        self.assertTrue(True)
