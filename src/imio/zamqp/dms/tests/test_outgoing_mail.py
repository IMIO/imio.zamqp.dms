# -*- coding: utf-8 -*-
from collective.iconifiedcategory.utils import calculate_category_id
from copy import deepcopy
from imio.dataexchange.core.dms import OutgoingMail as CoreOutgoingMail
from imio.dms.mail.testing import DMSMAIL_INTEGRATION_TESTING
from imio.helpers.content import get_object
from imio.zamqp.dms.testing import create_fake_message
from imio.zamqp.dms.testing import store_fake_content
from imio.zamqp.dms.tests.base_test_class import BaseTestClass
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

import datetime
import tempfile
import time


class TestOutgoingMail(BaseTestClass):

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

    def consume_outgoing_mail(self, params):
        from imio.zamqp.dms.consumer import OutgoingMail  # import later to avoid core config error

        params = deepcopy(params)
        # Create fake message
        if "external_id" not in params:
            params["external_id"] = u"0129999000001{:02d}".format(self.external_id_suffix)
            params["file_metadata"]["filename"] = u"{}.PDF".format(params["external_id"])
        self.external_id_suffix += 1
        msg = create_fake_message(CoreOutgoingMail, params)
        om = OutgoingMail("outgoing-mail", "dmsoutgoingmail", msg)
        store_fake_content(self.tdir, OutgoingMail, params)
        # Create outgoing mail from message
        time.sleep(1)  # to avoid same created date for all created objects
        om.create_or_update()
        obj = self.pc(portal_type="dmsoutgoingmail", sort_on="created")[-1].getObject()
        return obj

    def test_OutgoingMail(self):
        params = {
            # "external_id": u"01299990000000",
            "client_id": u"019999",
            "type": u"COUR_S",
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
                u"filename": u"012999900000101.PDF",
                u"pc": u"pc-scan01",
                u"user": u"testuser",
                u"filesize": 7910,
            },
        }
        self.assertEqual(len(self.pc(portal_type="dmsoutgoingmail")), 9)
        self.assertEqual(len(self.pc(portal_type="dmsommainfile")), 9)
        # create new outgoing mail
        obj = self.consume_outgoing_mail(params)
        self.assertEqual(obj.id, u"012999900000101")
        self.assertIsNone(obj.sender)
        self.assertIsNone(obj.treating_groups)
        self.assertIsNone(obj.assigned_user)
        self.assertEqual(api.content.get_state(obj), "scanned")
        self.assertEqual(obj.outgoing_date.strftime("%Y-%m-%d %H:%M"), "2025-12-07 13:16")
        expected_cc = calculate_category_id(
            self.portal["annexes_types"]["outgoing_dms_files"]["outgoing-scanned-dms-file"]
        )
        self.check_categorized_element(
            obj, 1, **{"category_id": "outgoing-scanned-dms-file", "id": "012999900000101.pdf", "signed": True}
        )
        self.assertEqual(obj["012999900000101.pdf"].content_category, expected_cc)
        # update existing outgoing mail
        params["external_id"] = u"012999900000008"
        params["file_metadata"]["filename"] = u"012999900000008.PDF"
        obj = get_object(oid="reponse8", ptype="dmsoutgoingmail")
        self.assertIsNone(obj.outgoing_date)
        self.assertEqual(len(obj.objectIds()), 1)
        fid = obj.objectIds()[0]
        self.consume_outgoing_mail(params)
        self.assertNotIn(fid, obj)
        self.assertIsNone(obj.outgoing_date)  # update does not set outgoing_date
        self.assertEqual(len(self.pc(portal_type="dmsoutgoingmail")), 10)
        self.assertEqual(len(self.pc(portal_type="dmsommainfile")), 10)
        self.check_categorized_element(
            obj, 1, **{"category_id": "outgoing-scanned-dms-file", "id": "012999900000008.pdf", "signed": True}
        )
        self.assertEqual(obj["012999900000008.pdf"].content_category, expected_cc)
