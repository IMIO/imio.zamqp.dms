# -*- coding: utf-8 -*-
from collective.wfadaptations.api import add_applied_adaptation
from copy import deepcopy
from imio.dataexchange.core.dms import IncomingEmail as CoreIncomingEmail
from imio.dms.mail.testing import DMSMAIL_INTEGRATION_TESTING
from imio.dms.mail.utils import group_has_user
from imio.dms.mail.wfadaptations import IMServiceValidation
from imio.zamqp.dms.testing import create_fake_message
from imio.zamqp.dms.testing import store_fake_content
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from zope.component import getUtility
from zope.schema.interfaces import IVocabularyFactory

import datetime
import shutil
import tempfile
import unittest
import re


class TestDmsfile(unittest.TestCase):

    layer = DMSMAIL_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.pc = self.portal.portal_catalog
        self.imf = self.portal['incoming-mail']
        self.omf = self.portal['outgoing-mail']
        self.diry = self.portal['contacts']
        self.tdir = tempfile.mkdtemp()
        self.external_id_suffix = 1  # up to 9999 possible ids
        print(self.tdir)

    def create_incoming_email(self, params, metadata):
        from imio.zamqp.dms.consumer import IncomingEmail  # import later to avoid core config error

        # Create fake messsage
        params['external_id'] = u'01Z9999000000{:04d}'.format(self.external_id_suffix)
        self.external_id_suffix += 1
        msg = create_fake_message(CoreIncomingEmail, params)
        ie = IncomingEmail('incoming-mail', 'dmsincoming_email', msg)
        store_fake_content(self.tdir, IncomingEmail, params, metadata)

        # Create incoming mail from message
        ie.create_or_update()
        obj = self.pc(portal_type='dmsincoming_email', sort_on='created')[-1].getObject()
        return obj

    def test_IncomingEmail_flow(self):
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

        self.ss_key = "imio.dms.mail.browser.settings.IImioDmsMailConfig.iemail_state_set"
        self.ss = api.portal.get_registry_record(self.ss_key)

        # expected states following the registry and the treating_group presence
        c_states = ("created", "proposed_to_manager", "proposed_to_agent", "in_treatment", "closed",
                    "proposed_to_agent", "proposed_to_agent")
        tg = None
        for i, reg_val in enumerate((u"created", u"proposed_to_manager", u"proposed_to_agent", u"in_treatment",
                                     u"closed", u"_n_plus_h_", u"_n_plus_l_")):
            # api.portal.set_registry_record(fw_tr_reg, reg_val)
            self.ss[0]["state_value"] = reg_val
            api.portal.set_registry_record(self.ss_key, self.ss)
            # unknown agent has forwarded
            params['external_id'] = u'01Z9999000000{:02d}'.format(i + 1)
            obj = self.create_incoming_email(params, metadata)
            self.assertEqual(obj.mail_type, u'courrier')
            self.assertEqual(obj.orig_sender_email, u'"Dexter Morgan" <dexter.morgan@mpd.am>')
            self.assertIsNone(obj.sender)
            self.assertIsNone(obj.treating_groups)
            self.assertIsNone(obj.assigned_user)
            self.assertEqual(api.content.get_state(obj), 'created', reg_val)
            # known agent has forwarded
            params['external_id'] = u'01Z9999000000{:02d}'.format(i + 8)
            metadata2 = deepcopy(metadata)
            metadata2["Agent"] = [["", "agent@MACOMMUNE.be"]]
            metadata2["From"] = [["", "jean.courant@electrabel.eb"]]
            obj = self.create_incoming_email(params, metadata2)
            self.assertIsNotNone(obj.sender)
            self.assertIsNotNone(obj.treating_groups)
            if tg:
                self.assertEqual(tg, obj.treating_groups, reg_val)
            tg = obj.treating_groups
            self.assertEqual(obj.assigned_user, u'agent')
            self.assertEqual(api.content.get_state(obj), c_states[i], reg_val)

        # with n_plus_1 level
        self.portal.portal_setup.runImportStepFromProfile('profile-imio.dms.mail:singles',
                                                          'imiodmsmail-im_n_plus_1_wfadaptation',
                                                          run_dependencies=False)
        groupname_1 = '{}_n_plus_1'.format(tg)
        self.assertTrue(group_has_user(groupname_1))
        c_states = ("created", "proposed_to_manager", "proposed_to_agent", "in_treatment", "closed",
                    "proposed_to_n_plus_1", "proposed_to_n_plus_1")
        for i, reg_val in enumerate((u"created", u"proposed_to_manager", u"proposed_to_agent", u"in_treatment",
                                     u"closed", u"_n_plus_h_", u"_n_plus_l_")):
            # api.portal.set_registry_record(fw_tr_reg, reg_val)
            self.ss[0]["state_value"] = reg_val
            api.portal.set_registry_record(self.ss_key, self.ss)
            # unknown agent has forwarded
            params['external_id'] = u'01Z9999000000{:02d}'.format(i + 21)
            obj = self.create_incoming_email(params, metadata)
            self.assertIsNone(obj.treating_groups)
            self.assertIsNone(obj.assigned_user)
            self.assertEqual(api.content.get_state(obj), 'created', reg_val)
            # known agent has forwarded
            params['external_id'] = u'01Z9999000000{:02d}'.format(i + 28)
            metadata2 = deepcopy(metadata)
            metadata2["Agent"] = [["", "agent@MACOMMUNE.be"]]
            metadata2["From"] = [["", "jean.courant@electrabel.eb"]]
            obj = self.create_incoming_email(params, metadata2)
            self.assertIsNotNone(obj.treating_groups)
            self.assertEqual(obj.assigned_user, u'agent')
            self.assertEqual(api.content.get_state(obj), c_states[i], reg_val)

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
        c_states = ("created", "proposed_to_manager", "proposed_to_agent", "in_treatment", "closed",
                    "proposed_to_n_plus_2", "proposed_to_n_plus_1")
        for i, reg_val in enumerate((u"created", u"proposed_to_manager", u"proposed_to_agent", u"in_treatment",
                                     u"closed", u"_n_plus_h_", u"_n_plus_l_")):
            # api.portal.set_registry_record(fw_tr_reg, reg_val)
            self.ss[0]["state_value"] = reg_val
            api.portal.set_registry_record(self.ss_key, self.ss)
            # unknown agent has forwarded
            params['external_id'] = u'01Z9999000000{:02d}'.format(i + 41)
            obj = self.create_incoming_email(params, metadata)
            self.assertIsNone(obj.treating_groups)
            self.assertIsNone(obj.assigned_user)
            self.assertEqual(api.content.get_state(obj), 'created', reg_val)
            # known agent has forwarded
            params['external_id'] = u'01Z9999000000{:02d}'.format(i + 48)
            metadata2 = deepcopy(metadata)
            metadata2["Agent"] = [['', 'agent@MACOMMUNE.be']]
            metadata2["From"] = [["", "jean.courant@electrabel.eb"]]
            obj = self.create_incoming_email(params, metadata2)
            self.assertIsNotNone(obj.treating_groups)
            self.assertEqual(obj.assigned_user, u'agent')
            self.assertEqual(api.content.get_state(obj), c_states[i], reg_val)

    def test_IncomingEmail_email_pat(self):
        params = {
            'client_id': u'019999', 'type': u'EMAIL_E', 'version': 1,
            'date': datetime.datetime(2021, 5, 18), 'update_date': None, 'user': u'testuser', 'file_md5': u'',
            'file_metadata': {u'creator': u'scanner', u'scan_hour': u'13:16:29', u'scan_date': u'2021-05-18',
                              u'filemd5': u'', u'filename': u'01Z999900000001.tar', u'pc': u'pc-scan01',
                              u'user': u'testuser', u'filesize': 0}
        }
        metadata = {
            'From': [['Jean Courant', 'jean.courant@electrabel.eb']], 'To': [['', 'debra.morgan@mpd.am']], 'Cc': [],
            'Subject': 'Bloodstain pattern analysis', 'Origin': 'Agent forward',
            'Agent': [['Agent', 'agent@macommune.be']]
        }

        self.routing_key = "imio.dms.mail.browser.settings.IImioDmsMailConfig.iemail_routing"
        self.routing = [
            {
                "forward": u"agent",
                "transfer_email_pat": u".*@macommune.be",
                "original_email_pat": u"",
                "tal_condition_1": u"",
                "user_value": u"encodeur",
                "tal_condition_2": u"",
                "tg_value": u"_primary_org_",
            },
            {
                "forward": u"agent",
                "transfer_email_pat": u"",
                "original_email_pat": u"serge.robinet@.*",
                "tal_condition_1": u"",
                "user_value": u"agent",
                "tal_condition_2": u"",
                "tg_value": u"_primary_org_",
            },
            {
                "forward": u"agent",
                "transfer_email_pat": u"",
                "original_email_pat": u"",
                "tal_condition_1": u"",
                "user_value": u"_empty_",
                "tal_condition_2": u"",
                "tg_value": u"_empty_",
            }
        ]
        api.portal.set_registry_record(self.routing_key, self.routing)

        # transfer_email_pat matches the transferer email
        obj = self.create_incoming_email(params, metadata)
        assert re.match(self.routing[0]["transfer_email_pat"], obj.agent_email)

        # transfer_email_pat doesn't match the transferer email
        metadata['Agent'] = [['Electrabel', 'contak@electrabel.eb']]
        obj = self.create_incoming_email(params, metadata)
        assert not re.match(self.routing[0]["transfer_email_pat"], obj.agent_email)
        assert not re.match(self.routing[1]["original_email_pat"], obj.sender[0].to_object.email)

        # original_email_pat matches the original sender email
        metadata['From'] = [['Serge Robinet', 'serge.robinet@swde.eb']]
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(len(obj.sender), 1)
        assert re.match(self.routing[1]["original_email_pat"], obj.sender[0].to_object.email)

    def test_IncomingEmail_sender(self):
        params = {
            'client_id': u'019999', 'type': u'EMAIL_E', 'version': 1,
            'date': datetime.datetime(2021, 5, 18), 'update_date': None, 'user': u'testuser', 'file_md5': u'',
            'file_metadata': {u'creator': u'scanner', u'scan_hour': u'13:16:29', u'scan_date': u'2021-05-18',
                              u'filemd5': u'', u'filename': u'01Z999900000001.tar', u'pc': u'pc-scan01',
                              u'user': u'testuser', u'filesize': 0}
        }
        metadata = {
            'From': [['Jean Courant', 'jean.courant@electrabel.eb']], 'To': [['', 'debra.morgan@mpd.am']], 'Cc': [],
            'Subject': 'Bloodstain pattern analysis', 'Origin': 'Agent forward',
            'Agent': [['Agent', 'agent@MACOMMUNE.BE']]
        }

        # external held_position
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(len(obj.sender), 1)
        self.assertEqual(obj.sender[0].to_object, self.diry.jeancourant['agent-electrabel'])

        # internal held_positions: primary organization related held position will be selected
        metadata['From'] = [['', 'agent@macommune.be']]
        obj = self.create_incoming_email(params, metadata)
        senders = self.pc(email='agent@macommune.be', portal_type=['organization', 'person', 'held_position'])
        self.assertEqual(len(senders), 8)
        self.assertListEqual([br.id for br in senders],
                             ['agent-secretariat', 'agent-grh', 'agent-communication', 'agent-budgets',
                              'agent-comptabilite', 'agent-batiments', 'agent-voiries', 'agent-evenements'])
        self.assertEqual(len(obj.sender), 1)
        self.assertEqual(obj.sender[0].to_object, self.diry['personnel-folder']['agent']['agent-communication'])

        # internal held_positions: no primary organization, only one held position will be selected
        self.diry['personnel-folder']['agent'].primary_organization = None
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(len(obj.sender), 1)
        self.assertEqual(obj.sender[0].to_object, self.diry['personnel-folder']['agent']['agent-secretariat'])

    def test_IncomingEmail_treating_groups(self):
        params = {
            'client_id': u'019999', 'type': u'EMAIL_E', 'version': 1,
            'date': datetime.datetime(2021, 5, 18), 'update_date': None, 'user': u'testuser', 'file_md5': u'',
            'file_metadata': {u'creator': u'scanner', u'scan_hour': u'13:16:29', u'scan_date': u'2021-05-18',
                              u'filemd5': u'', u'filename': u'01Z999900000001.tar', u'pc': u'pc-scan01',
                              u'user': u'testuser', u'filesize': 0}
        }
        metadata = {
            'From': [['Jean Courant', 'jean.courant@electrabel.eb']], 'To': [['', 'debra.morgan@mpd.am']], 'Cc': [],
            'Subject': 'Bloodstain pattern analysis', 'Origin': 'Agent forward',
            'Agent': [['Agent', 'agent@MACOMMUNE.BE']]
        }
        self.routing_key = "imio.dms.mail.browser.settings.IImioDmsMailConfig.iemail_routing"
        self.routing = api.portal.get_registry_record(self.routing_key)

        # Primary org
        self.routing[1]["tg_value"] = u"_primary_org_"
        api.portal.set_registry_record(self.routing_key, self.routing)
        self.diry['personnel-folder']['agent'].primary_organization = None
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.treating_groups)

        self.diry['personnel-folder']['agent'].primary_organization = self.diry['plonegroup-organization']['direction-generale']['communication'].UID()
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups,
                         self.diry['plonegroup-organization']['direction-generale']['communication'].UID())
        voc = getUtility(IVocabularyFactory, name=u'collective.dms.basecontent.treating_groups')
        [(t.value, t.title) for t in voc(None)]  # noqa

        # agent is part of the encodeurs group
        self.routing[1]["tg_value"] = u"_hp_"
        api.portal.set_registry_record(self.routing_key, self.routing)
        api.group.add_user(groupname='encodeurs', username='agent')
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups, self.diry['plonegroup-organization']['direction-generale']['communication'].UID())
        api.group.remove_user(groupname='encodeurs', username='agent')

        self.diry['personnel-folder']['agent'].primary_organization = None
        obj = self.create_incoming_email(params, metadata)
        hps = api.content.get("/contacts/personnel-folder/agent").get_held_positions()
        orgs = [hp.get_organization().UID() for hp in hps]
        self.assertTrue(obj.treating_groups in orgs)

        # No treating group
        self.routing[1]["tg_value"] = u"_empty_"
        api.portal.set_registry_record(self.routing_key, self.routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.treating_groups)

        # Specific treating group
        self.routing[1]["tg_value"] = self.diry['plonegroup-organization']['direction-generale']['communication'].UID()
        api.portal.set_registry_record(self.routing_key, self.routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups,
                         self.diry['plonegroup-organization']['direction-generale']['communication'].UID())

        # Uni org only
        self.routing[1]["tg_value"] = u"_uni_org_only_"
        api.portal.set_registry_record(self.routing_key, self.routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.treating_groups)

        metadata['Agent'][0] = ['Encodeur', 'encodeur@macommune.be']
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNotNone(obj.treating_groups)

    def tearDown(self):
        print("removing:" + self.tdir)
        shutil.rmtree(self.tdir, ignore_errors=True)
