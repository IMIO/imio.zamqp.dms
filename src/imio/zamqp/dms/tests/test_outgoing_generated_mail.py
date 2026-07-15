# -*- coding: utf-8 -*-
from collective.iconifiedcategory.utils import calculate_category_id
from imio.dataexchange.core.dms import OutgoingGeneratedMail as CoreOutgoingGeneratedMail
from imio.dms.mail.content.behaviors import ISigningBehavior
from imio.dms.mail.interfaces import IOMApproval
from imio.dms.mail.testing import DMSMAIL_INTEGRATION_TESTING
from imio.esign.utils import get_session_annotation
from imio.helpers.content import get_object
from imio.zamqp.dms.testing import create_fake_message
from imio.zamqp.dms.testing import store_fake_content
from imio.zamqp.dms.tests.base_test_class import BaseTestClass
from ipython_genutils.py3compat import safe_unicode
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.dexterity.utils import createContentInContainer
from plone.namedfile.file import NamedBlobFile
from Products.CMFEditions.tests.test_ModifierRegistryTool import deepcopy
from zope.lifecycleevent import Attributes
from zope.lifecycleevent import modified

import datetime
import shutil
import tempfile
import time


class TestOutgoingGeneratedMail(BaseTestClass):

    layer = DMSMAIL_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer["portal"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        self.pc = self.portal.portal_catalog
        self.imf = self.portal["incoming-mail"]
        self.omf = self.portal["outgoing-mail"]
        self.ctct = self.portal["contacts"]
        self.pgof = self.ctct["plonegroup-organization"]
        self.pf = self.ctct["personnel-folder"]
        self.tdir = tempfile.mkdtemp()
        # print(self.tdir)
        self.external_id_suffix = 0  # up to 99 possible ids
        self.rep6 = get_object(oid="reponse6", ptype="dmsoutgoingmail")
        self.rep7 = get_object(oid="reponse7", ptype="dmsoutgoingmail")
        self.rep8 = get_object(oid="reponse8", ptype="dmsoutgoingmail")
        self.rep9 = get_object(oid="reponse9", ptype="dmsoutgoingmail")
        self.portal.portal_setup.runImportStepFromProfile(
            "profile-imio.dms.mail:singles", "imiodmsmail-activate-esigning", run_dependencies=False
        )
        api.portal.set_registry_record("imio.esign.file_url", "http://localhost/test")

    def consume_ogm(self, params):
        from imio.zamqp.dms.consumer import OutgoingGeneratedMail  # import later to avoid core config error

        params = deepcopy(params)
        # Create fake messsage
        self.external_id_suffix += 1
        if "external_id" not in params:
            params["external_id"] = u"0129999000001{:02d}".format(self.external_id_suffix)
        msg = create_fake_message(CoreOutgoingGeneratedMail, params)
        ogm = OutgoingGeneratedMail("outgoing-mail", "dmsoutgoingmail", msg)
        store_fake_content(self.tdir, OutgoingGeneratedMail, params)
        time.sleep(1)  # to avoid same created date for all created objects
        ogm.create_or_update()

    def _mark_manually_signed(self, mail, fid, scan_date):
        """Turn an existing mainfile into a manually signed (not esigned) one."""
        the_file = mail[fid]
        the_file.signed = True
        the_file.esigned = False
        the_file.scan_date = scan_date
        ce = mail.categorized_elements[the_file.UID()]
        ce["signed"] = True
        ce["esigned"] = False
        ce["scan_id"] = the_file.scan_id
        mail._p_changed = True
        return the_file

    def test_scanned_OGM(self):
        params = {
            "client_id": u"059999",
            "external_id": u"012999900000010",  # non existing
            "type": u"COUR_S_GEN",
            "version": 1,
            "date": datetime.datetime(2021, 5, 18),
            "update_date": None,
            "user": u"testuser",
            "file_md5": u"",
            "file_metadata": {
                u"creator": u"scanner",
                u"scan_hour": u"13:16:29",
                u"scan_date": u"2021-05-18",
                u"filemd5": u"",
                u"filename": u"012999900000008.pdf",
                u"pc": u"pc-scan01",
                u"user": u"testuser",
                u"filesize": 7910,
            },
        }
        self.assertEqual(len(self.pc(portal_type="dmsoutgoingmail")), 9)
        self.assertEqual(len(self.pc(portal_type="dmsommainfile")), 9)
        self.assertEqual(self.rep8.objectIds(), ["1"])
        # not an existing scan_id, so no object found
        self.consume_ogm(params)
        self.assertEqual(self.rep8.objectIds(), ["1"])
        self.assertIsNone(self.rep8.outgoing_date)
        self.assertEqual(api.content.get_state(self.rep8), "created")
        # existing file, not email, creation
        self.assertEqual(self.rep8["1"].scan_id, "012999900000008")
        params["external_id"] = u"012999900000008"  # rep8 file 1
        file_id = "012999900000008.pdf"
        self.consume_ogm(params)
        self.assertEqual(self.rep8.objectIds(), ["1", file_id])
        self.assertEqual(self.rep8.outgoing_date.strftime("%Y-%m-%d %H:%M"), "2021-05-18 13:16")
        self.assertFalse(self.rep8.is_email())
        self.assertEqual(api.content.get_state(self.rep8), "sent")
        self.assertTrue(self.rep8[file_id].signed)
        # existing file, not email, update
        params["file_metadata"]["scan_hour"] = u"14:16:29"  # change hour
        params["version"] = 2
        old_uid = self.rep8[file_id].UID()
        self.consume_ogm(params)
        self.assertEqual(self.rep8.objectIds(), ["1", file_id])
        self.assertEqual(self.rep8[file_id].UID(), old_uid)  # in-place update preserves UID
        self.assertEqual(self.rep8.outgoing_date.strftime("%Y-%m-%d %H:%M"), "2021-05-18 14:16")
        self.assertEqual(self.rep8[file_id].scan_date.strftime("%Y-%m-%d %H:%M"), "2021-05-18 14:16")
        self.assertFalse(self.rep8.is_email())
        self.assertEqual(api.content.get_state(self.rep8), "sent")
        self.assertTrue(self.rep8[file_id].signed)
        # other existing file, email, creation
        self.rep9.send_modes = ["email"]
        self.assertEqual(self.rep9["1"].scan_id, "012999900000009")
        params["external_id"] = u"012999900000009"  # rep9 file 1
        file_id = "012999900000009.pdf"
        params["file_metadata"]["filename"] = safe_unicode(file_id)
        params["file_metadata"]["scan_hour"] = u"13:16:29"
        self.consume_ogm(params)
        self.assertEqual(self.rep9.objectIds(), ["1", file_id])
        self.assertEqual(self.rep9.outgoing_date.strftime("%Y-%m-%d %H:%M"), "2021-05-18 13:16")
        self.assertTrue(self.rep9.is_email())
        self.assertEqual(api.content.get_state(self.rep9), "signed")
        self.assertTrue(self.rep9[file_id].signed)
        # PVS/PD/PC flags (read from the original file scan_user): PVS => no new file, only scan_date
        # registered on the original file; PD => no outgoing_date; PC => no closing transition
        sid7 = self.rep7["1"].scan_id
        self.rep7["1"].scan_user = u"PC|PD|PVS"
        rep7_state = api.content.get_state(self.rep7)
        params["external_id"] = sid7
        params["file_metadata"]["filename"] = u"whatever.pdf"
        self.consume_ogm(params)
        self.assertEqual(self.rep7.objectIds(), ["1"])  # PVS => no new file
        self.assertEqual(self.rep7["1"].scan_date.strftime("%Y-%m-%d %H:%M"), "2021-05-18 13:16")
        self.assertIsNone(self.rep7.outgoing_date)  # PD => no outgoing_date
        self.assertEqual(api.content.get_state(self.rep7), rep7_state)  # PC => no transition
        # manually signed file + scan_date delta > 20h + not PVS => new sending => new file created
        self.rep7["1"].scan_user = u""
        self._mark_manually_signed(self.rep7, "1", datetime.datetime(2021, 5, 15, 10, 0))
        self.consume_ogm(params)
        self.assertEqual(len(self.rep7.objectIds()), 2)  # new file created
        new_id = next(i for i in self.rep7.objectIds() if i != "1")
        self.assertFalse(self.rep7[new_id].esigned)
        # manually signed file + delta > 20h + PVS => file not considered (nothing created/changed)
        sid6 = self.rep6["1"].scan_id
        self._mark_manually_signed(self.rep6, "1", datetime.datetime(2021, 5, 15, 10, 0))
        self.rep6["1"].scan_user = u"PVS"
        rep6_uid = self.rep6["1"].UID()
        params["external_id"] = sid6
        self.consume_ogm(params)
        self.assertEqual(self.rep6.objectIds(), ["1"])  # PVS => not considered
        self.assertEqual(self.rep6["1"].UID(), rep6_uid)
        # manually signed file + delta < 20h + older incoming version => update skipped
        self.rep6["1"].scan_user = u""
        self.rep6["1"].scan_date = datetime.datetime(2021, 5, 18, 12, 0)  # delta < 20h
        self.rep6["1"].version = 5
        rep6_size = self.rep6["1"].file.size
        params["version"] = 1
        self.consume_ogm(params)
        self.assertEqual(self.rep6.objectIds(), ["1"])
        self.assertEqual(self.rep6["1"].UID(), rep6_uid)  # not replaced
        self.assertEqual(self.rep6["1"].file.size, rep6_size)

    def test_esigned_OGM(self):
        params = {
            "client_id": u"059999",
            "external_id": u"012999900000008",
            "type": u"COUR_S_GEN",
            "version": 1,
            "date": datetime.datetime(2025, 11, 14),
            "update_date": None,
            "user": u"testuser",
            "file_md5": u"",
            "file_metadata": {
                u"creator": u"scanner",
                u"scan_hour": u"13:16:29",
                u"scan_date": u"2025-11-14",
                u"filemd5": u"",
                u"filename": u"Modèle de base S0009 Reponse 9.pdf",
                u"pc": u"_api_esign_",
                u"filesize": 7910,
            },
        }
        self.assertEqual(len(self.pc(portal_type="dmsoutgoingmail")), 9)
        self.assertEqual(len(self.pc(portal_type="dmsommainfile")), 9)
        # esign document whose uid cannot be resolved from the filename => file left untouched
        err_params = deepcopy(params)
        err_params["file_metadata"]["filename"] = u"noparts.pdf"  # no "__" => uid None
        self.consume_ogm(err_params)
        self.assertEqual(self.rep8.objectIds(), ["1"])
        err_params["file_metadata"]["filename"] = u"doc__missinguid-1.pdf"  # "-" rename, uid not categorized
        self.consume_ogm(err_params)
        self.assertEqual(self.rep8.objectIds(), ["1"])
        # we modify rep8 to set approvers and esign
        self.assertEqual(self.rep8.objectIds(), ["1"])
        self.assertTrue(self.rep8["1"].to_sign)
        self.assertFalse(self.rep8["1"].to_approve)  # to_approve has been changed to False because no approvers
        self.assertEqual(api.content.get_state(self.rep8), "created")
        sessions = get_session_annotation(self.portal)
        self.assertEqual(sessions, {'sessions': {}, 'numbering': 0, 'uids': {}, 'c_uids': {}})
        # FIRST CASE: 1 signer, 1 approver, 0 seal
        dirg_hp = self.pf["dirg"]["directeur-general"].UID()
        self.rep8.signers = [{"signer": dirg_hp, 'approvings': [u"_themself_"], 'number': 1, 'editor': True}]
        self.rep8.esign = True
        self.assertFalse(self.rep8.seal)
        modified(self.rep8, Attributes(ISigningBehavior, "ISigningBehavior.signers"))
        oma = IOMApproval(self.rep8)
        self.rep8["1"].to_approve = True
        uid = self.rep8["1"].UID()
        oma.add_file_to_approval(uid)
        self.assertEqual(len(oma.files_uids), 1)
        self.assertEqual(len(oma.approvers), 1)
        self.assertEqual(oma.annot["approval"][0][0], {'status': 'w', 'approved_on': None, 'approved_by': None})
        self.assertIsNone(oma.annot["current_nb"])
        self.assertEquals(len(oma.annot["session_ids"]), 0)
        api.content.transition(self.rep8, "propose_to_approve")
        self.assertEqual(api.content.get_state(self.rep8), "to_approve")
        # dirg approves
        self.assertEqual(oma.annot["current_nb"], 0)
        self.assertEqual(oma.annot["approval"][0][0]["status"], "p")
        self.assertEqual(self.rep8["1"].file.filename, u"Réponse candidature ouvrier communal.odt")
        ret, _ = oma.approve_file(self.rep8["1"], "dirg", transition="propose_to_be_signed")
        self.assertTrue(ret)
        self.assertEqual(oma.annot["approval"][0][0]["status"], "a")
        self.assertEqual(oma.annot["approval"][0][0]["approved_by"], "dirg")
        self.assertEqual(oma.annot["current_nb"], -1)  # approval is finished
        self.assertEqual(api.content.get_state(self.rep8), "to_be_signed")
        # pdf file has been generated and has replaced original file
        self.assertEqual(self.rep8.objectIds(), ["1"])
        self.assertEqual(self.rep8["1"].file.filename, u"Réponse candidature ouvrier communal__{}.pdf".format(uid))
        self.assertEqual(oma.annot["pdf_files"][0], [uid])
        self.assertListEqual(oma.annot["session_ids"].data, [0])
        self.assertIn(uid, sessions['uids'])
        self.assertEqual(len(sessions["sessions"]), 1)
        self.assertEqual(sessions["sessions"][0]["state"], "draft")  # but in reality, it will be updated
        self.assertEqual(len(sessions["sessions"][0]["files"]), 1)
        self.assertEqual(sessions["sessions"][0]["files"][0]["status"], "")
        self.assertTrue(sessions["sessions"][0]["files"][0]["filename"].endswith(u"__{}.pdf".format(uid)))
        params["file_metadata"]["filename"] = sessions["sessions"][0]["files"][0]["filename"]
        old_file_size = self.rep8["1"].file.size
        self.assertEqual(self.rep8["1"].signed, False)
        # we simulate the session sent where the state will be changed
        self.consume_ogm(params)
        self.assertEqual(self.rep8["1"].signed, True)
        self.assertNotEqual(self.rep8["1"].file.size, old_file_size)
        self.assertEqual(api.content.get_state(self.rep8), "signed")
        self.assertEqual(sessions["sessions"][0]["files"][0]["status"], "received")
        self.assertEqual(sessions["sessions"][0]["state"], "finalized")
        # SECOND CASE: 0 signer, 0 approver, 1 seal
        self.rep9.signers = [{"signer": u"_empty_", 'approvings': [u"_empty_"], 'number': 1, 'editor': True}]
        self.rep9.esign = False
        self.rep9.seal = True
        modified(self.rep9, Attributes(ISigningBehavior, "ISigningBehavior.signers"))
        self.assertEqual(api.content.get_state(self.rep9), "created")
        self.assertTrue(self.rep9["1"].to_sign)
        self.assertFalse(self.rep9["1"].to_approve)  # to_approve has been changed to False because no approvers
        oma = IOMApproval(self.rep9)
        self.assertEqual(len(oma.files_uids), 0)
        self.assertEqual(len(oma.approvers), 0)
        self.assertEqual(oma.annot["approval"], [])
        self.assertTrue(self.rep9["1"].to_sign)
        self.assertEqual(self.rep9["1"].file.filename, u"Réponse salle.odt")
        # propose to be signed, so the session is created and sent
        api.content.transition(self.rep9, "propose_to_be_signed")
        self.assertIsNone(oma.annot["current_nb"])
        self.assertEqual(oma.annot["approval"], [])
        self.assertListEqual(oma.annot["session_ids"].data, [1])
        # pdf file has been generated and has replaced original file
        self.assertEqual(self.rep9.objectIds(), ["1"])
        uid = self.rep9["1"].UID()
        self.assertEqual(self.rep9["1"].file.filename, u"Réponse salle__{}.pdf".format(uid))
        self.assertIn(uid, sessions['uids'])
        self.assertEqual(len(sessions["sessions"]), 2)
        self.assertEqual(sessions["sessions"][1]["state"], "draft")  # but in reality, it will be updated
        self.assertEqual(len(sessions["sessions"][1]["files"]), 1)
        self.assertEqual(sessions["sessions"][1]["files"][0]["status"], "")
        self.assertTrue(sessions["sessions"][1]["files"][0]["filename"].endswith(u"__{}.pdf".format(uid)))
        params["file_metadata"]["filename"] = sessions["sessions"][1]["files"][0]["filename"]
        params["external_id"] = u"012999900000009"
        old_file_size = self.rep9["1"].file.size
        self.consume_ogm(params)
        self.assertEqual(self.rep9["1"].signed, True)
        self.assertNotEqual(self.rep9["1"].file.size, old_file_size)
        self.assertEqual(api.content.get_state(self.rep9), "signed")
        self.assertEqual(sessions["sessions"][1]["files"][0]["status"], "received")
        self.assertEqual(sessions["sessions"][1]["state"], "finalized")
        # THIRD CASE: 0 signer, 0 approver, 2 seal
        self.rep7.signers = [{"signer": u"_empty_", 'approvings': [u"_empty_"], 'number': 1, 'editor': True}]
        self.rep7.esign = False
        self.rep7.seal = True
        modified(self.rep7, Attributes(ISigningBehavior, "ISigningBehavior.signers"))
        self.assertEqual(api.content.get_state(self.rep7), "created")
        oma = IOMApproval(self.rep7)
        self.assertEqual(len(oma.files_uids), 0)
        self.assertEqual(len(oma.approvers), 0)
        self.assertEqual(oma.annot["approval"], [])
        self.assertTrue(self.rep7["1"].to_sign)
        self.assertFalse(self.rep7["1"].to_approve)
        self.assertEqual(self.rep7["1"].file.filename, u"Accusé de réception.odt")
        # added another file to sign
        file_object = NamedBlobFile(self.rep6["1"].file.data, filename=self.rep6["1"].file.filename)
        self.assertEqual(file_object.filename, u"Réponse salle.odt")
        createContentInContainer(
            self.rep7,
            "dmsommainfile",
            id="2",
            title=u"test file",
            file=file_object,
            to_sign=True,
            scan_id=u"012999900000010",
            content_category=calculate_category_id(self.portal["annexes_types"]["outgoing_dms_files"]
                                                   ["outgoing-dms-file"]),
        )
        self.assertTrue(self.rep7["2"].to_sign)
        self.assertFalse(self.rep7["2"].to_approve)
        self.assertEqual(self.rep7.objectIds(), ["1", "2"])
        # propose to be signed, so the session is created and sent
        api.content.transition(self.rep7, "propose_to_be_signed")
        oma = IOMApproval(self.rep7)
        self.assertEqual(len(oma.files_uids), 2)
        self.assertEqual(oma.annot["approval"], [])
        self.assertListEqual(oma.annot["session_ids"].data, [2])
        # pdf file has been generated
        filename1 = u"Accusé de réception"
        filename2 = u"Réponse salle"
        ext_id1 = u"012999900000007"
        ext_id2 = u"012999900000010"
        self.assertEqual(self.rep7.objectIds(), ["1", "2"])
        self.assertTrue(sessions["sessions"][2]["files"][0]["filename"].startswith(filename1))
        self.assertTrue(sessions["sessions"][2]["files"][1]["filename"].startswith(filename2))
        uid1 = self.rep7["1"].UID()
        uid2 = self.rep7["2"].UID()
        self.assertIn(uid1, sessions['uids'])
        self.assertIn(uid2, sessions['uids'])
        self.assertEqual(len(sessions["sessions"]), 3)
        self.assertEqual(sessions["sessions"][2]["state"], "draft")  # but in reality, it will be updated
        self.assertEqual(len(sessions["sessions"][2]["files"]), 2)
        self.assertEqual(sessions["sessions"][2]["files"][0]["status"], "")
        self.assertEqual(sessions["sessions"][2]["files"][1]["status"], "")
        self.assertTrue(sessions["sessions"][2]["files"][0]["filename"].endswith(u"__{}.pdf".format(uid1)))
        self.assertTrue(sessions["sessions"][2]["files"][1]["filename"].endswith(u"__{}.pdf".format(uid2)))
        # we will consume first file
        params["file_metadata"]["filename"] = sessions["sessions"][2]["files"][0]["filename"]
        params["external_id"] = ext_id1
        old_file_size = self.rep7["1"].file.size
        self.consume_ogm(params)
        self.assertEqual(self.rep7["1"].signed, True)
        self.assertNotEqual(self.rep7["1"].file.size, old_file_size)
        self.assertEqual(api.content.get_state(self.rep7), "to_be_signed")
        self.assertEqual(sessions["sessions"][2]["files"][0]["status"], "received")
        self.assertEqual(sessions["sessions"][2]["state"], "draft")
        # we will consume second file (accuse de reception)
        params["file_metadata"]["filename"] = sessions["sessions"][2]["files"][1]["filename"]
        params["external_id"] = ext_id2
        old_file_size = self.rep7["2"].file.size
        self.consume_ogm(params)
        self.assertEqual(self.rep7["2"].signed, True)
        self.assertNotEqual(self.rep7["2"].file.size, old_file_size)
        self.assertEqual(api.content.get_state(self.rep7), "signed")
        self.assertEqual(sessions["sessions"][2]["files"][1]["status"], "received")
        self.assertEqual(sessions["sessions"][2]["state"], "finalized")

    def test_scanned_does_not_overwrite_esigned(self):
        # an esign signature has begun but the file is manually scanned and sent back.
        # The esigned file must be preserved and a new scanned file created alongside.
        the_file = self.rep8["1"]
        the_file.signed = True
        the_file.esigned = True
        ce = self.rep8.categorized_elements[the_file.UID()]
        ce["signed"] = True
        ce["esigned"] = True
        ce["scan_id"] = the_file.scan_id
        self.rep8._p_changed = True
        esigned_uid = the_file.UID()
        self.assertEqual(self.rep8.objectIds(), ["1"])
        params = {
            "client_id": u"059999",
            "external_id": u"012999900000008",  # rep8 file 1
            "type": u"COUR_S_GEN",
            "version": 1,
            "date": datetime.datetime(2021, 5, 18),
            "update_date": None,
            "user": u"testuser",
            "file_md5": u"",
            "file_metadata": {
                u"creator": u"scanner",
                u"scan_hour": u"13:16:29",
                u"scan_date": u"2021-05-18",
                u"filemd5": u"",
                u"filename": u"012999900000008.pdf",
                u"pc": u"pc-scan01",  # scanned, not "_api_esign_"
                u"user": u"testuser",
                u"filesize": 7910,
            },
        }
        self.consume_ogm(params)
        # esigned file preserved (not overwritten), new scanned file created alongside
        self.assertEqual(len(self.rep8.objectIds()), 2)
        self.assertEqual(self.rep8["1"].UID(), esigned_uid)
        self.assertTrue(self.rep8["1"].esigned)
        new_id = next(i for i in self.rep8.objectIds() if i != "1")
        self.assertFalse(self.rep8[new_id].esigned)
        # Other case: e-signature was started (esign=True) but the electronic file never came back
        # (no file is esigned). The scanned file is simply created.
        self.rep9.esign = True
        self.assertFalse(getattr(self.rep9["1"], "esigned", False))
        self.assertEqual(self.rep9.objectIds(), ["1"])
        params["external_id"] = u"012999900000009"  # rep9 file 1
        params["file_metadata"]["filename"] = u"012999900000009.pdf"
        self.consume_ogm(params)
        self.assertEqual(len(self.rep9.objectIds()), 2)  # scanned file created as usual
        new_id9 = next(i for i in self.rep9.objectIds() if i != "1")
        self.assertFalse(self.rep9[new_id9].esigned)

    def tearDown(self):
        # print("removing:" + self.tdir)
        shutil.rmtree(self.tdir, ignore_errors=True)
