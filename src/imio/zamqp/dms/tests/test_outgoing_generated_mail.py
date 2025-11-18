# -*- coding: utf-8 -*-
from collective.iconifiedcategory.utils import calculate_category_id
from imio.dataexchange.core.dms import OutgoingGeneratedMail as CoreOutgoingGeneratedMail
from imio.dms.mail.testing import DMSMAIL_INTEGRATION_TESTING
from imio.dms.mail.utils import add_file_to_approval
from imio.dms.mail.utils import approve_file
from imio.dms.mail.utils import get_approval_annot
from imio.esign.utils import get_session_annotation
from imio.helpers.content import get_object
from imio.zamqp.dms.testing import create_fake_message
from imio.zamqp.dms.testing import store_fake_content
from ipython_genutils.py3compat import safe_unicode
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.dexterity.utils import createContentInContainer
from plone.namedfile.file import NamedBlobFile
from Products.CMFEditions.tests.test_ModifierRegistryTool import deepcopy
from zope.lifecycleevent import modified

import datetime
import shutil
import tempfile
import unittest


class TestOutgoingGeneratedMail(unittest.TestCase):

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
        self.external_id_suffix = 0  # up to 99 possible ids
        self.rep7 = get_object(oid="reponse7", ptype="dmsoutgoingmail")
        self.rep8 = get_object(oid="reponse8", ptype="dmsoutgoingmail")
        self.rep9 = get_object(oid="reponse9", ptype="dmsoutgoingmail")
        self.portal.portal_setup.runImportStepFromProfile(
            "profile-imio.dms.mail:singles", "imiodmsmail-om_to_approve_wfadaptation", run_dependencies=False
        )
        # print(self.tdir)

    def consume_ogm(self, params):
        from imio.zamqp.dms.consumer import OutgoingGeneratedMail  # import later to avoid core config error

        params = deepcopy(params)
        # Create fake messsage
        self.external_id_suffix += 1
        if "external_id" not in params:
            params["external_id"] = u"0129999000001{:02d}".format(self.external_id_suffix)
        msg = create_fake_message(CoreOutgoingGeneratedMail, params)
        ogm = OutgoingGeneratedMail("outgoing-mail", "dmsoutgoingmail", msg)
        store_fake_content(self.tdir, OutgoingGeneratedMail, params, {})
        ogm.create_or_update()

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
        self.assertNotEqual(self.rep8[file_id].UID(), old_uid)  # new object
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
        self.assertEqual(self.rep8.objectIds(), ["1"])
        self.assertTrue(self.rep8["1"].to_sign)
        self.assertEqual(api.content.get_state(self.rep8), "created")
        sessions = get_session_annotation(self.portal)
        self.assertEqual(sessions, {'sessions': {}, 'numbering': 0, 'uids': {}, 'c_uids': {}})
        # FIRST CASE: 1 signer, 1 approver, 0 seal
        dirg_hp = self.pf["dirg"]["directeur-general"].UID()
        self.rep8.signers = [{"signer": dirg_hp, 'approvings': [u"_themself_"], 'number': 1, 'editor': True}]
        self.rep8.esign = True
        self.assertFalse(self.rep8.seal)
        modified(self.rep8)
        a_a = get_approval_annot(self.rep8)
        self.assertEqual(len(a_a["files"]), 0)
        self.assertEqual(len(a_a["users"]), 1)
        self.assertIsNone(a_a["approval"])
        f_uid = self.rep8["1"].UID()
        # add file to approval
        add_file_to_approval(a_a, f_uid)
        self.assertEqual(len(a_a["files"]), 1)
        self.assertEqual(a_a["files"][f_uid]["nb"][1]["status"], "w")
        self.assertIsNone(a_a["approval"])
        self.assertIsNone(a_a["session_id"])
        api.content.transition(self.rep8, "propose_to_approve")
        self.assertEqual(api.content.get_state(self.rep8), "to_approve")
        # dirg approves
        ret, _ = approve_file(a_a, self.rep8, self.rep8["1"], "dirg", transition="propose_to_be_signed")
        self.assertTrue(ret)
        self.assertEqual(a_a["files"][f_uid]["nb"][1]["status"], "a")
        self.assertEqual(a_a["files"][f_uid]["nb"][1]["approved_by"], "dirg")
        self.assertEqual(a_a["approval"], 99)  # approval is finished
        self.assertEqual(api.content.get_state(self.rep8), "to_approve")  # still in to_approve before signing
        # pdf file has been generated
        self.assertEqual(self.rep8.objectIds(), ["1", "reponse-candidature-ouvrier-communal.pdf"])
        nf_uid = self.rep8["reponse-candidature-ouvrier-communal.pdf"].UID()
        self.assertEqual(a_a["session_id"], 0)
        self.assertIn(nf_uid, sessions['uids'])
        self.assertEqual(len(sessions["sessions"]), 1)
        self.assertEqual(sessions["sessions"][0]["state"], "draft")  # but in reality, it will be updated
        self.assertEqual(len(sessions["sessions"][0]["files"]), 1)
        self.assertEqual(sessions["sessions"][0]["files"][0]["status"], "")
        self.assertTrue(sessions["sessions"][0]["files"][0]["filename"].endswith(u"__{}.pdf".format(nf_uid)))
        params["file_metadata"]["filename"] = sessions["sessions"][0]["files"][0]["filename"]
        old_file_size = self.rep8["reponse-candidature-ouvrier-communal.pdf"].file.size
        # we simulate the session sent where the state will be changed
        api.content.transition(self.rep8, "propose_to_be_signed")
        self.consume_ogm(params)
        self.assertEqual(self.rep8["reponse-candidature-ouvrier-communal.pdf"].signed, True)
        self.assertNotEqual(self.rep8["reponse-candidature-ouvrier-communal.pdf"].file.size, old_file_size)
        self.assertEqual(api.content.get_state(self.rep8), "signed")
        self.assertEqual(sessions["sessions"][0]["files"][0]["status"], "received")
        self.assertEqual(sessions["sessions"][0]["state"], "finalized")
        # SECOND CASE: 0 signer, 0 approver, 1 seal
        self.rep9.signers = [{"signer": u"_empty_", 'approvings': [u"_empty_"], 'number': 1, 'editor': True}]
        self.rep9.esign = False
        self.rep9.seal = True
        modified(self.rep9)
        self.assertEqual(api.content.get_state(self.rep9), "created")
        a_a = get_approval_annot(self.rep9)
        self.assertEqual(len(a_a["files"]), 0)
        self.assertEqual(len(a_a["users"]), 0)
        self.assertIsNone(a_a["approval"])
        self.assertTrue(self.rep9["1"].to_sign)
        f_uid = self.rep9["1"].UID()
        # propose to be signed, so the session is created and sent
        api.content.transition(self.rep9, "propose_to_be_signed")
        a_a = get_approval_annot(self.rep9)
        self.assertEqual(len(a_a["files"]), 1)
        self.assertEqual(len(a_a["files"][f_uid]["nb"]), 0)
        self.assertIsNone(a_a["approval"])
        self.assertEqual(a_a["session_id"], 1)
        # pdf file has been generated
        self.assertEqual(self.rep9.objectIds(), ["1", "reponse-salle.pdf"])
        nf_uid = self.rep9["reponse-salle.pdf"].UID()
        self.assertIn(nf_uid, sessions['uids'])
        self.assertEqual(len(sessions["sessions"]), 2)
        self.assertEqual(sessions["sessions"][1]["state"], "draft")  # but in reality, it will be updated
        self.assertEqual(len(sessions["sessions"][1]["files"]), 1)
        self.assertEqual(sessions["sessions"][1]["files"][0]["status"], "")
        self.assertTrue(sessions["sessions"][1]["files"][0]["filename"].endswith(u"__{}.pdf".format(nf_uid)))
        params["file_metadata"]["filename"] = sessions["sessions"][1]["files"][0]["filename"]
        params["external_id"] = u"012999900000009"
        old_file_size = self.rep9["reponse-salle.pdf"].file.size
        self.consume_ogm(params)
        self.assertEqual(self.rep9["reponse-salle.pdf"].signed, True)
        self.assertNotEqual(self.rep9["reponse-salle.pdf"].file.size, old_file_size)
        self.assertEqual(api.content.get_state(self.rep9), "signed")
        self.assertEqual(sessions["sessions"][1]["files"][0]["status"], "received")
        self.assertEqual(sessions["sessions"][1]["state"], "finalized")
        # THIRD CASE: 0 signer, 0 approver, 2 seal
        self.rep7.signers = [{"signer": u"_empty_", 'approvings': [u"_empty_"], 'number': 1, 'editor': True}]
        self.rep7.esign = False
        self.rep7.seal = True
        modified(self.rep7)
        self.assertEqual(api.content.get_state(self.rep7), "created")
        a_a = get_approval_annot(self.rep7)
        self.assertEqual(len(a_a["files"]), 0)
        self.assertEqual(len(a_a["users"]), 0)
        self.assertIsNone(a_a["approval"])
        self.assertTrue(self.rep7["1"].to_sign)
        # added another file to sign
        file_object = NamedBlobFile(self.rep9["1"].file.data, filename=u"Réponse salle.odt")
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
        self.assertEqual(self.rep7.objectIds(), ["1", "2"])
        f_uid1 = self.rep7["1"].UID()
        f_uid2 = self.rep7["2"].UID()
        # propose to be signed, so the session is created and sent
        setattr(self.portal, "_debug_", True)
        api.content.transition(self.rep7, "propose_to_be_signed")
        a_a = get_approval_annot(self.rep7)
        self.assertEqual(len(a_a["files"]), 2)
        self.assertEqual(len(a_a["files"][f_uid1]["nb"]), 0)
        self.assertEqual(len(a_a["files"][f_uid2]["nb"]), 0)
        self.assertIsNone(a_a["approval"])
        self.assertEqual(a_a["session_id"], 2)
        # pdf file has been generated
        pdf_id1 = u"accuse-de-reception.pdf"
        pdf_id2 = u"reponse-salle.pdf"
        filename1 = u"Accusé de réception"
        filename2 = u"Réponse salle"
        ext_id1 = u"012999900000007"
        ext_id2 = u"012999900000010"
        if self.rep7.objectIds()[-1] == pdf_id1:
            pdf_id1, pdf_id2 = pdf_id2, pdf_id1
            filename1, filename2 = filename2, filename1
            ext_id1, ext_id2 = ext_id2, ext_id1
        self.assertEqual(self.rep7.objectIds(), ["1", "2", pdf_id1, pdf_id2])
        self.assertTrue(sessions["sessions"][2]["files"][0]["filename"].startswith(filename1))
        self.assertTrue(sessions["sessions"][2]["files"][1]["filename"].startswith(filename2))
        nf_uid1 = self.rep7[pdf_id1].UID()
        nf_uid2 = self.rep7[pdf_id2].UID()
        self.assertIn(nf_uid1, sessions['uids'])
        self.assertIn(nf_uid2, sessions['uids'])
        self.assertEqual(len(sessions["sessions"]), 3)
        self.assertEqual(sessions["sessions"][2]["state"], "draft")  # but in reality, it will be updated
        self.assertEqual(len(sessions["sessions"][2]["files"]), 2)
        self.assertEqual(sessions["sessions"][2]["files"][0]["status"], "")
        self.assertEqual(sessions["sessions"][2]["files"][1]["status"], "")
        self.assertTrue(sessions["sessions"][2]["files"][0]["filename"].endswith(u"__{}.pdf".format(nf_uid1)))
        self.assertTrue(sessions["sessions"][2]["files"][1]["filename"].endswith(u"__{}.pdf".format(nf_uid2)))
        # we will consume first file
        params["file_metadata"]["filename"] = sessions["sessions"][2]["files"][0]["filename"]
        params["external_id"] = ext_id1
        old_file_size = self.rep7[pdf_id1].file.size
        self.consume_ogm(params)
        self.assertEqual(self.rep7[pdf_id1].signed, True)
        self.assertNotEqual(self.rep7[pdf_id1].file.size, old_file_size)
        self.assertEqual(api.content.get_state(self.rep7), "to_be_signed")
        self.assertEqual(sessions["sessions"][2]["files"][0]["status"], "received")
        self.assertEqual(sessions["sessions"][2]["state"], "draft")
        # we will consume second file (accuse de reception)
        params["file_metadata"]["filename"] = sessions["sessions"][2]["files"][1]["filename"]
        params["external_id"] = ext_id2
        old_file_size = self.rep7[pdf_id2].file.size
        self.consume_ogm(params)
        self.assertEqual(self.rep7[pdf_id2].signed, True)
        self.assertNotEqual(self.rep7[pdf_id2].file.size, old_file_size)
        self.assertEqual(api.content.get_state(self.rep7), "signed")
        self.assertEqual(sessions["sessions"][2]["files"][1]["status"], "received")
        self.assertEqual(sessions["sessions"][2]["state"], "finalized")

    def tearDown(self):
        # print("removing:" + self.tdir)
        shutil.rmtree(self.tdir, ignore_errors=True)
