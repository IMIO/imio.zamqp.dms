# -*- coding: utf-8 -*-
from imio.dataexchange.core.dms import IncomingEmail as CoreIncomingEmail
from imio.dms.mail.testing import DMSMAIL_INTEGRATION_TESTING
from imio.zamqp.dms.testing import create_fake_message
from imio.zamqp.dms.testing import store_fake_content
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone import api

import datetime
import shutil
import tempfile
import unittest


class TestDmsfile(unittest.TestCase):

    layer = DMSMAIL_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.pc = self.portal.portal_catalog
        self.imf = self.portal['incoming-mail']
        self.omf = self.portal['outgoing-mail']
        self.tdir = tempfile.mkdtemp()
        print self.tdir

    def test_IncomingEmail_base(self):
        from imio.zamqp.dms.consumer import IncomingEmail  # import later to avoid core config error
        params = {
            'external_id': u'01Z999900000002', 'client_id': u'019999', 'type': u'EMAIL_E', 'version': 1,
            'date': datetime.datetime(2021, 5, 18), 'update_date': None, 'user': u'testuser', 'file_md5': u'',
            'file_metadata': {u'creator': u'scanner', u'scan_hour': u'13:16:29', u'scan_date': u'2021-05-18',
                              u'filemd5': u'', u'filename': u'01Z999900000001.tar', u'pc': u'pc-scan01',
                              u'user': u'testuser', u'filesize': 0}
        }
        metadata = {
            'From': [['Dexter Morgan', 'dexter.morgan@mpd.am']], 'To': [['', 'debra.morgan@mpd.am']], 'Cc': [],
            'Subject': 'Bloodstain pattern analysis', 'Origin': 'Agent forward',
            'Agent': [['Vince Masuka', 'vince.masuka@mpd.am']]
        }
        msg = create_fake_message(CoreIncomingEmail, params)
        # unknown agent has forwarded
        ie = IncomingEmail('incoming-mail', 'dmsincoming_email', msg)
        store_fake_content(self.tdir, IncomingEmail, params, metadata)
        ie.create_or_update()
        obj = self.pc(portal_type='dmsincoming_email', sort_on='created')[-1].getObject()
        self.assertEqual(obj.mail_type, u'email')
        self.assertEqual(obj.orig_sender_email, u'"Dexter Morgan" <dexter.morgan@mpd.am>')
        self.assertIsNone(obj.sender)
        self.assertIsNone(obj.treating_groups)
        self.assertIsNone(obj.assigned_user)
        self.assertEqual(api.content.get_state(obj), 'created')
        # known agent has forwarded
        ie = IncomingEmail('incoming-mail', 'dmsincoming_email', msg)
        metadata['Agent'] = [['', 'agent@MACOMMUNE.be']]
        store_fake_content(self.tdir, IncomingEmail, params, metadata)
        ie.create_or_update()
        obj = self.pc(portal_type='dmsincoming_email', sort_on='created')[-1].getObject()
        self.assertIsNone(obj.sender)
        self.assertIsNotNone(obj.treating_groups)
        self.assertEqual(obj.assigned_user, u'agent')
        self.assertEqual(api.content.get_state(obj), 'proposed_to_agent')

    def tearDown(self):
        print "removing:"+self.tdir
        shutil.rmtree(self.tdir, ignore_errors=True)
