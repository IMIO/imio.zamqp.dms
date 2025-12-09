# -*- coding: utf-8 -*-
from copy import deepcopy
from imio.dataexchange.core.dms import IncomingMail as CoreIncomingMail
from imio.dms.mail.testing import DMSMAIL_INTEGRATION_TESTING
from imio.zamqp.dms.testing import create_fake_message
from imio.zamqp.dms.testing import store_fake_content
from imio.zamqp.dms.tests.base_test_class import BaseTestClass
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

import datetime
import tempfile


class TestIncomingMail(BaseTestClass):

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
        self.external_id_suffix = 1  # up to 99 possible ids
        print(self.tdir)

    def consume_incoming_mail(self, params):
        from imio.zamqp.dms.consumer import IncomingMail  # import later to avoid core config error

        params = deepcopy(params)
        # Create fake messsage
        if "external_id" not in params:
            params["external_id"] = u"0109999000001{:02d}".format(self.external_id_suffix)
            params["file_metadata"]["filename"] = u"{}.PDF".format(params["external_id"])
        self.external_id_suffix += 1
        msg = create_fake_message(CoreIncomingMail, params)
        ie = IncomingMail("incoming-mail", "dmsincomingmail", msg)
        store_fake_content(self.tdir, IncomingMail, params)
        # Create incoming mail from message
        ie.create_or_update()
        obj = self.pc(portal_type="dmsincomingmail", sort_on="created")[-1].getObject()
        return obj

    def test_IncomingMail(self):
        params = {
            # "external_id": u"01Z9999000000",
            "client_id": u"019999",
            "type": u"COUR_E",
            "version": 1,
            "date": datetime.datetime(2025, 12, 7),
            "update_date": None,
            "user": u"testuser",
            "file_md5": u"",
            "file_metadata": {
                u"creator": u"scanner",
                u"scan_hour": u"13:16:29",
                u"scan_date": u"2025-12-07",
                u"filemd5": u"",
                u"filename": u"010999900000001.PDF",
                u"pc": u"pc-scan01",
                u"user": u"testuser",
                u"filesize": 7910,
            },
        }
        self.assertEqual(len(self.pc(portal_type="dmsincomingmail")), 9)
        self.assertEqual(len(self.pc(portal_type="dmsmainfile")), 9)
        # create new incoming mail
        obj = self.consume_incoming_mail(params)
        self.assertEqual(obj.id, u"010999900000101")
        self.assertEqual(obj.mail_type, u"courrier")
        self.assertIsNone(obj.sender)
        self.assertIsNone(obj.treating_groups)
        self.assertIsNone(obj.assigned_user)
        self.assertEqual(api.content.get_state(obj), "created")
        self.check_categorized_element(obj, 1, **{"category_id": "incoming-dms-file", "id": "010999900000101.pdf"})
        # update existing incoming mail
        params["external_id"] = u"010999900000008"
        params["file_metadata"]["filename"] = u"010999900000008.PDF"
        obj = obj.aq_parent["courrier8"]
        self.assertIn("in-courrier2.pdf", obj)
        self.consume_incoming_mail(params)
        self.assertNotIn("in-courrier2.pdf", obj)
        self.assertEqual(len(self.pc(portal_type="dmsincomingmail")), 10)
        self.assertEqual(len(self.pc(portal_type="dmsmainfile")), 10)
        self.check_categorized_element(obj, 1, **{"category_id": "incoming-dms-file", "id": "010999900000008.pdf"})
