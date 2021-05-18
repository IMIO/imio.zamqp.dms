# -*- coding: utf-8 -*-

from imio.dataexchange.core.dms import IncomingEmail as CoreIncomingEmail
from imio.dms.mail.testing import DMSMAIL_INTEGRATION_TESTING
from imio.zamqp.dms.testing import create_fake_message
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

import datetime
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
        from imio.zamqp.dms.consumer import IncomingEmail  # import later to avoid core config error
        params = {'external_id': u'01Z999900000002', 'client_id': u'019999', 'type': u'EMAIL_E', 'version': 1,
                  'date': datetime.datetime(2021, 5, 18), 'update_date': None, 'user': u'testuser', 'file_md5': u'',
                  'file_metadata': {u'creator': u'scanner', u'scan_hour': u'13:16:29', u'scan_date': u'2021-05-18',
                                    u'filemd5': u'', u'filename': u'01Z999900000001.tar', u'pc': u'pc-scan01',
                                    u'user': u'testuser', u'filesize': 0}}
        msg = create_fake_message(CoreIncomingEmail, params)
        ie = IncomingEmail('incoming-mail', 'dmsincoming_email', msg)
        self.assertTrue(True)
