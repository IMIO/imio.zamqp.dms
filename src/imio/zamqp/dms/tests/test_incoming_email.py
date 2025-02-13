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
        self.ctct = self.portal['contacts']
        self.pgof = self.ctct['plonegroup-organization']
        self.pf = self.ctct['personnel-folder']
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

    def test_IncomingEmail_condition(self):
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

        routing_key = "imio.dms.mail.browser.settings.IImioDmsMailConfig.iemail_routing"
        ev_org = self.pgof["evenements"].UID()
        routing = [
            {
                "forward": u"agent",
                "transfer_email_pat": u"",
                "original_email_pat": u"",
                "tal_condition_1": u"",
                "user_value": u"agent1",
                "tal_condition_2": u"",
                "tg_value": ev_org,
            }
        ]
        api.portal.set_registry_record(routing_key, routing)

        # check no condition
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.assigned_user, u'agent1')
        self.assertEqual(obj.treating_groups, ev_org)
        # check False condition 1
        routing[0]["tal_condition_1"] = u"python:False"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.assigned_user)
        self.assertIsNone(obj.treating_groups)
        # check condition 1 on member id
        routing[0]["tal_condition_1"] = u"python:member.getId() == 'agent'"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.assigned_user, u'agent1')
        self.assertEqual(obj.treating_groups, ev_org)
        # check condition 1 on context
        routing[0]["tal_condition_1"] = u"python:context.getId() == 'incoming-mail'"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.assigned_user, u'agent1')
        self.assertEqual(obj.treating_groups, ev_org)
        # check condition 1 on maidata
        routing[0]["tal_condition_1"] = u"python:maildata['From'][0][1] == 'jean.courant@electrabel.eb'"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.assigned_user, u'agent1')
        self.assertEqual(obj.treating_groups, ev_org)
        # check condition 2 on assigned_user
        routing[0]["tal_condition_2"] = u"python:assigned_user == 'agent1'"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.assigned_user, u'agent1')
        self.assertEqual(obj.treating_groups, ev_org)
        # check False condition 2
        routing[0]["tal_condition_1"] = u""
        routing[0]["tal_condition_2"] = u"python:False"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.assigned_user)
        self.assertIsNone(obj.treating_groups)

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
        self.assertEqual(obj.sender[0].to_object, self.ctct.jeancourant['agent-electrabel'])

        # internal held_positions: primary organization related held position will be selected
        metadata['From'] = [['', 'agent@macommune.be']]
        obj = self.create_incoming_email(params, metadata)
        senders = self.pc(email='agent@macommune.be', portal_type=['organization', 'person', 'held_position'])
        self.assertEqual(len(senders), 8)
        self.assertListEqual([br.id for br in senders],
                             ['agent-secretariat', 'agent-grh', 'agent-communication', 'agent-budgets',
                              'agent-comptabilite', 'agent-batiments', 'agent-voiries', 'agent-evenements'])
        self.assertEqual(len(obj.sender), 1)
        self.assertEqual(obj.sender[0].to_object, self.pf['agent']['agent-communication'])

        # internal held_positions: no primary organization, only one held position will be selected
        self.pf['agent'].primary_organization = None
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(len(obj.sender), 1)
        self.assertEqual(obj.sender[0].to_object, self.pf['agent']['agent-secretariat'])

    def test_IncomingEmail_routing(self):
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
        routing_key = "imio.dms.mail.browser.settings.IImioDmsMailConfig.iemail_routing"
        routing = [
            {
                u"forward": u"agent",
                u"transfer_email_pat": u"",
                u"original_email_pat": u"",
                u"tal_condition_1": u"",
                u"user_value": u"_transferer_",
                u"tal_condition_2": u"",
                u"tg_value": u"_primary_org_",
            },
        ]
        api.portal.set_registry_record(routing_key, routing)
        # check patterns
        routing[0]["transfer_email_pat"] = u".*@space.x"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.treating_groups)
        self.assertIsNone(obj.assigned_user)
        routing[0]["transfer_email_pat"] = u".*@macommune.be"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNotNone(obj.treating_groups)
        self.assertIsNotNone(obj.assigned_user)
        routing[0]["original_email_pat"] = u".*@space.x"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.treating_groups)
        self.assertIsNone(obj.assigned_user)
        routing[0]["original_email_pat"] = u".*@electrabel.eb"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNotNone(obj.treating_groups)
        self.assertIsNotNone(obj.assigned_user)
        # check condition1
        routing[0]["original_email_pat"] = u""
        routing[0]["transfer_email_pat"] = u""
        routing[0]["tal_condition_1"] = u"python:False"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.treating_groups)
        self.assertIsNone(obj.assigned_user)
        routing[0]["tal_condition_1"] = u"python:True"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNotNone(obj.treating_groups)
        self.assertIsNotNone(obj.assigned_user)
        routing[0]["tal_condition_1"] = u""
        # assigner_user
        # _empty_
        routing[0]["user_value"] = u"_empty_"
        routing[0]["tg_value"] = self.pgof['direction-generale']['secretariat'].UID()
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups, self.pgof['direction-generale']['secretariat'].UID())
        self.assertIsNone(obj.assigned_user)
        # _transferer_
        routing[0]["user_value"] = u"_transferer_"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups, self.pgof['direction-generale']['secretariat'].UID())
        self.assertEqual(obj.assigned_user, 'agent')
        # defined user but not in group
        routing[0]["user_value"] = u"agent1"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.treating_groups)
        self.assertIsNone(obj.assigned_user)
        # defined user but not in group
        routing[0]["tg_value"] = self.pgof["evenements"].UID()
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups, self.pgof['evenements'].UID())
        self.assertEqual(obj.assigned_user, 'agent1')

        # Primary org
        # _uni_org_only_
        routing[0]["tg_value"] = u"_uni_org_only_"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups, self.pgof['evenements'].UID())
        self.assertEqual(obj.assigned_user, 'agent1')
        # _primary_org_
        routing[0]["user_value"] = u"_transferer_"
        routing[0]["tg_value"] = u"_primary_org_"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups, self.pgof['direction-generale']['communication'].UID())
        self.assertEqual(obj.assigned_user, 'agent')
        self.pf['agent'].primary_organization = None
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.treating_groups)
        self.assertIsNone(obj.assigned_user)
        # _hp_
        self.pf['agent'].primary_organization = None
        routing[0]["tg_value"] = u"_hp_"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertNotEqual(obj.treating_groups, self.pgof['direction-generale']['communication'].UID())
        self.assertEqual(obj.assigned_user, 'agent')
        self.pf['agent'].primary_organization = self.pgof['direction-generale']['communication'].UID()
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups, self.pgof['direction-generale']['communication'].UID())
        self.assertEqual(obj.assigned_user, 'agent')
        # _empty_
        routing[0]["tg_value"] = u"_empty_"
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertIsNone(obj.assigned_user)
        self.assertIsNone(obj.treating_groups)
        # defined group
        routing[0]["tg_value"] = self.pgof["direction-generale"]["grh"].UID()
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups, self.pgof['direction-generale']['grh'].UID())
        self.assertEqual(obj.assigned_user, 'agent')

        # agent is part of the encodeurs group
        routing[0]["tg_value"] = u"_hp_"
        api.portal.set_registry_record(routing_key, routing)
        api.group.add_user(groupname='encodeurs', username='agent')
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups, self.pgof['direction-generale']['communication'].UID())
        api.group.remove_user(groupname='encodeurs', username='agent')

        self.pf['agent'].primary_organization = None
        obj = self.create_incoming_email(params, metadata)
        hps = api.content.get("/contacts/personnel-folder/agent").get_held_positions()
        orgs = [hp.get_organization().UID() for hp in hps]
        self.assertTrue(obj.treating_groups in orgs)

        # Testing
        routing = [
            {
                u"forward": u"agent",
                u"transfer_email_pat": u"",
                u"original_email_pat": u"",
                u"tal_condition_1": u"",
                u"user_value": u"encodeur",
                u"tal_condition_2": u"python: 'encodeurs' in modules['imio.dms.mail.utils']."
                                    u"current_user_groups_ids(userid=assigned_user)",
                u"tg_value": self.pgof["direction-generale"]["secretariat"].UID(),
            },
        ]
        api.portal.set_registry_record(routing_key, routing)
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups, self.pgof['direction-generale']['secretariat'].UID())
        self.assertEqual(obj.assigned_user, 'encodeur')

    def tearDown(self):
        print("removing:" + self.tdir)
        shutil.rmtree(self.tdir, ignore_errors=True)
