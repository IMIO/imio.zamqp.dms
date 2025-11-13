# -*- coding: utf-8 -*-
from imio.dataexchange.core.dms import OutgoingGeneratedMail as CoreOutgoingGeneratedMail
from imio.dms.mail.testing import DMSMAIL_INTEGRATION_TESTING
from imio.helpers.content import get_object
from imio.zamqp.dms.testing import create_fake_message
from imio.zamqp.dms.testing import store_fake_content
from ipython_genutils.py3compat import safe_unicode
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from Products.CMFEditions.tests.test_ModifierRegistryTool import deepcopy

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
        self.rep8 = get_object(oid="reponse8", ptype="dmsoutgoingmail")
        self.rep9 = get_object(oid="reponse9", ptype="dmsoutgoingmail")
        print(self.tdir)

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
            "client_id": u"019999",
            "external_id": u"052999900000010",  # non existing
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
                u"filename": u"052999900000008.pdf",
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
        # existing file, not email
        self.assertEqual(self.rep8["1"].scan_id, "052999900000008")
        params["external_id"] = u"052999900000008"  # rep8 file 1
        file_id = "052999900000008.pdf"
        self.consume_ogm(params)
        self.assertEqual(self.rep8.objectIds(), ["1", file_id])
        self.assertEqual(self.rep8.outgoing_date.strftime("%Y-%m-%d %H:%M"), "2021-05-18 13:16")
        self.assertFalse(self.rep8.is_email())
        self.assertEqual(api.content.get_state(self.rep8), "sent")
        self.assertTrue(self.rep8[file_id].signed)
        # existing file, email
        self.rep9.send_modes = ["email"]
        self.assertEqual(self.rep9["1"].scan_id, "052999900000009")
        params["external_id"] = u"052999900000009"  # rep9 file 1
        file_id = "052999900000009.pdf"
        params["file_metadata"]["filename"] = safe_unicode(file_id)
        self.consume_ogm(params)
        self.assertEqual(self.rep9.objectIds(), ["1", file_id])
        self.assertEqual(self.rep9.outgoing_date.strftime("%Y-%m-%d %H:%M"), "2021-05-18 13:16")
        self.assertTrue(self.rep9.is_email())
        self.assertEqual(api.content.get_state(self.rep9), "signed")
        self.assertTrue(self.rep9[file_id].signed)

    def tearDown(self):
        print("removing:" + self.tdir)
        shutil.rmtree(self.tdir, ignore_errors=True)
