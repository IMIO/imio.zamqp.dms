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
        def assert_flow(params, metadata, expected_output):
            # expected states following the registry and the treating_group presence
            expected_c_states = expected_output["c_states"]
            tg = None
            for i, i_registry_value in enumerate((u"created", u"proposed_to_manager", u"proposed_to_agent",
                                                  u"in_treatment", u"closed", u"_n_plus_h_", u"_n_plus_l_")):
                # Set settings to one of the possible value
                self.state_set_registry_value[0]["state_value"] = i_registry_value
                api.portal.set_registry_record(self.state_set_registry_key, self.state_set_registry_value)

                obj = self.create_incoming_email(params, metadata)

                # Quality control and assertions
                self.assertEqual(obj.mail_type, u'courrier')
                self.assertEqual(obj.orig_sender_email, expected_output["orig_mail_sender"])
                if expected_output["sender"] is None:
                    self.assertIsNone(obj.sender)
                else:
                    self.assertEqual(len(obj.sender), 1)
                    self.assertEqual(obj.sender[0].to_object, expected_output["sender"])
                if expected_output["treating_groups"] is None:
                    self.assertIsNone(obj.treating_groups)
                else:
                    self.assertIsNotNone(obj.treating_groups)
                if expected_output["assigned_user"] is None:
                    self.assertIsNone(obj.assigned_user)
                else:
                    self.assertEqual(obj.assigned_user, expected_output["assigned_user"])
                try:
                    self.assertEqual(api.content.get_state(obj), expected_c_states[i], i_registry_value)
                except AssertionError:
                    import ipdb; ipdb.set_trace()
                if tg:
                    self.assertEqual(tg, obj.treating_groups, i_registry_value)
                tg = obj.treating_groups

            return tg

        params = {
            'client_id': u'019999', 'type': u'EMAIL_E', 'version': 1,
            'date': datetime.datetime(2021, 5, 18), 'update_date': None, 'user': u'testuser', 'file_md5': u'',
            'file_metadata': {u'creator': u'scanner', u'scan_hour': u'13:16:29', u'scan_date': u'2021-05-18',
                                u'filemd5': u'', u'filename': u'01Z999900000001.tar', u'pc': u'pc-scan01',
                                u'user': u'testuser', u'filesize': 0}
        }
        metadatas = [
            {
                'From': [['Dexter Morgan', 'dexter.morgan@mpd.am']],
                'To': [['', 'debra.morgan@mpd.am']],
                'Cc': [],
                'Subject': 'Bloodstain pattern analysis',
                'Origin': 'Agent forward',
                'Agent': [['Vince Masuka', 'vince.masuka@mpd.am']]
            },
            {
                'From': [["", "jean.courant@electrabel.eb"]],
                'To': [['', 'debra.morgan@mpd.am']],
                'Cc': [],
                'Subject': 'Bloodstain pattern analysis',
                'Origin': 'Agent forward',
                'Agent': [["", "agent@MACOMMUNE.be"]]
            }
        ]
        expected_outputs = [
            {
                "c_states": ("created", "created", "created", "created", "created", "created", "created"),
                "orig_mail_sender": u'"Dexter Morgan" <dexter.morgan@mpd.am>',
                "sender": None,
                "treating_groups": None,
                "assigned_user": None,
            },
            {
                "c_states": ("created", "proposed_to_manager", "proposed_to_agent", "in_treatment", "closed",
                             "proposed_to_agent", "proposed_to_agent"),
                "orig_mail_sender": u'jean.courant@electrabel.eb',
                "sender": self.diry.jeancourant['agent-electrabel'],
                "treating_groups": not None,
                "assigned_user": u'agent',
            },
        ]

        self.state_set_registry_key = "imio.dms.mail.browser.settings.IImioDmsMailConfig.iemail_state_set"
        self.state_set_registry_value = api.portal.get_registry_record(self.state_set_registry_key)

        for metadata, expected_output in zip(metadatas, expected_outputs):
            tg = assert_flow(params, metadata, expected_output)

        # with n_plus_1 level
        self.portal.portal_setup.runImportStepFromProfile('profile-imio.dms.mail:singles',
                                                          'imiodmsmail-im_n_plus_1_wfadaptation',
                                                          run_dependencies=False)
        groupname_1 = '{}_n_plus_1'.format(tg)
        self.assertTrue(group_has_user(groupname_1))
        expected_outputs[1]["c_states"] = ("created", "proposed_to_manager", "proposed_to_agent", "in_treatment",
                                           "closed", "proposed_to_n_plus_1", "proposed_to_n_plus_1")
        for metadata, expected_output in zip(metadatas, expected_outputs):
            tg = assert_flow(params, metadata, expected_output)

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
        expected_outputs[1]["c_states"] = ("created", "proposed_to_manager", "proposed_to_agent", "in_treatment",
                                           "closed", "proposed_to_n_plus_2", "proposed_to_n_plus_1")
        for metadata, expected_output in zip(metadatas, expected_outputs):
            tg = assert_flow(params, metadata, expected_output)

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
        self.assertEqual(obj.sender[0].to_object, self.diry.jeancourant['agent-electrabel'])
        self.assertEqual(obj.assigned_user, u'encodeur')
        self.assertEqual(obj.treating_groups, self.diry['plonegroup-organization']['direction-generale']['secretariat'].UID())

        # transfer_email_pat doesn't match the transferer email
        metadata['Agent'] = [['Electrabel', 'contak@electrabel.eb']]
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.sender[0].to_object, self.diry.jeancourant['agent-electrabel'])
        self.assertIsNone(obj.assigned_user)
        self.assertIsNone(obj.treating_groups)

        # original_email_pat matches the original sender email
        metadata['From'] = [['Serge Robinet', 'serge.robinet@swde.eb']]
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.sender[0].to_object, self.diry.sergerobinet['agent-swde'])
        self.assertEqual(obj.assigned_user, u'agent')
        self.assertEqual(obj.treating_groups, self.diry['plonegroup-organization']['direction-generale']['communication'].UID())

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

        # agent is part of the encodeurs group
        self.routing[0]["tg_value"] = u"_hp_"
        api.portal.set_registry_record(self.routing_key, self.routing)
        api.group.add_user(groupname='encodeurs', username='agent')
        obj = self.create_incoming_email(params, metadata)
        # TODO fix broken TAL condition 2, cannot work if we defined assigned_user to be None
        # python: 'encodeurs' in modules['imio.helpers.cache'].get_plone_groups_for_user(assigned_user)
        self.assertEqual(obj.treating_groups, self.diry.jeancourant["agent-electrabel"].UID())
        self.assertIsNone(obj.assigned_user)
        api.group.remove_user(groupname='encodeurs', username='agent')

        # primary_organization defined
        obj = self.create_incoming_email(params, metadata)
        self.assertEqual(obj.treating_groups,
                         self.diry['plonegroup-organization']['direction-generale']['communication'].UID())

        # primary_organization undefined
        self.diry['personnel-folder']['agent'].primary_organization = None
        obj = self.create_incoming_email(params, metadata)
        voc = getUtility(IVocabularyFactory, name=u'collective.dms.basecontent.treating_groups')
        [(t.value, t.title) for t in voc(None)]  # noqa

    def tearDown(self):
        print("removing:" + self.tdir)
        shutil.rmtree(self.tdir, ignore_errors=True)
