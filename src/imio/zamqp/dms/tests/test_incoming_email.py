# -*- coding: utf-8 -*-
from copy import deepcopy

from collective.wfadaptations.api import add_applied_adaptation
from imio.dataexchange.core.dms import IncomingEmail as CoreIncomingEmail
from imio.dms.mail.testing import DMSMAIL_INTEGRATION_TESTING
from imio.dms.mail.utils import group_has_user
from imio.dms.mail.wfadaptations import IMServiceValidation
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
            'external_id': u'01Z9999000000', 'client_id': u'019999', 'type': u'EMAIL_E', 'version': 1,
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
        fw_tr_reg = 'imio.dms.mail.browser.settings.IImioDmsMailConfig.iemail_manual_forward_transition'
        # expected states following the registry and the treating_group presence
        c_states = (('created', 'created'), ('created', 'proposed_to_manager'),
                    ('created', 'proposed_to_agent'), ('created', 'proposed_to_agent'),
                    ('created', 'proposed_to_agent'))
        tg = None
        for i, reg_val in enumerate((u'created', u'manager', u'n_plus_h', u'n_plus_l', u'agent')):
            api.portal.set_registry_record(fw_tr_reg, reg_val)
            # unknown agent has forwarded
            params['external_id'] = u'01Z9999000000' + u'{:02d}'.format(i+1)
            msg = create_fake_message(CoreIncomingEmail, params)
            ie = IncomingEmail('incoming-mail', 'dmsincoming_email', msg)
            store_fake_content(self.tdir, IncomingEmail, params, metadata)
            ie.create_or_update()
            obj = self.pc(portal_type='dmsincoming_email', sort_on='created')[-1].getObject()
            self.assertEqual(obj.mail_type, u'courrier')
            self.assertEqual(obj.orig_sender_email, u'"Dexter Morgan" <dexter.morgan@mpd.am>')
            self.assertIsNone(obj.sender)
            self.assertIsNone(obj.treating_groups)
            self.assertIsNone(obj.assigned_user)
            self.assertEqual(api.content.get_state(obj), c_states[i][0], reg_val)
            # known agent has forwarded
            params['external_id'] = u'01Z9999000000' + u'{:02d}'.format(i+6)
            msg = create_fake_message(CoreIncomingEmail, params)
            ie = IncomingEmail('incoming-mail', 'dmsincoming_email', msg)
            metadata2 = deepcopy(metadata)
            metadata2['Agent'] = [['', 'agent@MACOMMUNE.be']]
            store_fake_content(self.tdir, IncomingEmail, params, metadata2)
            ie.create_or_update()
            obj = self.pc(portal_type='dmsincoming_email', sort_on='created')[-1].getObject()
            self.assertIsNone(obj.sender)
            self.assertIsNotNone(obj.treating_groups)
            if tg:
                self.assertEqual(tg, obj.treating_groups, reg_val)
            tg = obj.treating_groups
            self.assertEqual(obj.assigned_user, u'agent')
            self.assertEqual(api.content.get_state(obj), c_states[i][1], reg_val)

        # with n_plus_1 level
        self.portal.portal_setup.runImportStepFromProfile('profile-imio.dms.mail:singles',
                                                          'imiodmsmail-im_n_plus_1_wfadaptation',
                                                          run_dependencies=False)
        groupname_1 = '{}_n_plus_1'.format(tg)
        self.assertTrue(group_has_user(groupname_1))
        c_states = (('created', 'created'), ('created', 'proposed_to_manager'),
                    ('created', 'proposed_to_n_plus_1'), ('created', 'proposed_to_n_plus_1'),
                    ('created', 'proposed_to_agent'))
        for i, reg_val in enumerate((u'created', u'manager', u'n_plus_h', u'n_plus_l', u'agent')):
            api.portal.set_registry_record(fw_tr_reg, reg_val)
            # unknown agent has forwarded
            params['external_id'] = u'01Z9999000000' + u'{:02d}'.format(i+11)
            msg = create_fake_message(CoreIncomingEmail, params)
            ie = IncomingEmail('incoming-mail', 'dmsincoming_email', msg)
            store_fake_content(self.tdir, IncomingEmail, params, metadata)
            ie.create_or_update()
            obj = self.pc(portal_type='dmsincoming_email', sort_on='created')[-1].getObject()
            self.assertIsNone(obj.treating_groups)
            self.assertIsNone(obj.assigned_user)
            self.assertEqual(api.content.get_state(obj), c_states[i][0], reg_val)
            # known agent has forwarded
            params['external_id'] = u'01Z9999000000' + u'{:02d}'.format(i+16)
            msg = create_fake_message(CoreIncomingEmail, params)
            ie = IncomingEmail('incoming-mail', 'dmsincoming_email', msg)
            metadata2 = deepcopy(metadata)
            metadata2['Agent'] = [['', 'agent@MACOMMUNE.be']]
            store_fake_content(self.tdir, IncomingEmail, params, metadata2)
            ie.create_or_update()
            obj = self.pc(portal_type='dmsincoming_email', sort_on='created')[-1].getObject()
            self.assertIsNotNone(obj.treating_groups)
            self.assertEqual(obj.assigned_user, u'agent')
            self.assertEqual(api.content.get_state(obj), c_states[i][1], reg_val)

        # with n_plus_2 level
        n_plus_2_params = {'validation_level': 2,
                           'state_title': u'Valider par le chef de département',
                           'forward_transition_title': u'Proposer au chef de département',
                           'backward_transition_title': u'Renvoyer au chef de département',
                           'function_title': u'chef de département'}
        sva = IMServiceValidation()
        adapt_is_applied = sva.patch_workflow('incomingmail_workflow', **n_plus_2_params)
        if adapt_is_applied:
            add_applied_adaptation('imio.dms.mail.wfadaptations.IMServiceValidation',
                                   'incomingmail_workflow', True, **n_plus_2_params)
        groupname_2 = '{}_n_plus_2'.format(tg)
        self.assertFalse(group_has_user(groupname_2))
        api.group.add_user(groupname=groupname_2, username='chef')
        c_states = (('created', 'created'), ('created', 'proposed_to_manager'),
                    ('created', 'proposed_to_n_plus_2'), ('created', 'proposed_to_n_plus_1'),
                    ('created', 'proposed_to_agent'))
        for i, reg_val in enumerate((u'created', u'manager', u'n_plus_h', u'n_plus_l', u'agent')):
            api.portal.set_registry_record(fw_tr_reg, reg_val)
            # unknown agent has forwarded
            params['external_id'] = u'01Z9999000000' + u'{:02d}'.format(i+21)
            msg = create_fake_message(CoreIncomingEmail, params)
            ie = IncomingEmail('incoming-mail', 'dmsincoming_email', msg)
            store_fake_content(self.tdir, IncomingEmail, params, metadata)
            ie.create_or_update()
            obj = self.pc(portal_type='dmsincoming_email', sort_on='created')[-1].getObject()
            self.assertIsNone(obj.treating_groups)
            self.assertIsNone(obj.assigned_user)
            self.assertEqual(api.content.get_state(obj), c_states[i][0], reg_val)
            # known agent has forwarded
            params['external_id'] = u'01Z9999000000' + u'{:02d}'.format(i+26)
            msg = create_fake_message(CoreIncomingEmail, params)
            ie = IncomingEmail('incoming-mail', 'dmsincoming_email', msg)
            metadata2 = deepcopy(metadata)
            metadata2['Agent'] = [['', 'agent@MACOMMUNE.be']]
            store_fake_content(self.tdir, IncomingEmail, params, metadata2)
            ie.create_or_update()
            obj = self.pc(portal_type='dmsincoming_email', sort_on='created')[-1].getObject()
            self.assertIsNotNone(obj.treating_groups)
            self.assertEqual(obj.assigned_user, u'agent')
            self.assertEqual(api.content.get_state(obj), c_states[i][1], reg_val)

    def tearDown(self):
        print "removing:"+self.tdir
        shutil.rmtree(self.tdir, ignore_errors=True)
