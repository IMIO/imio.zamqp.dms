# -*- coding: utf-8 -*-
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.testing import z2

import imio.zamqp.dms


class ImioZamqpDmsLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        self.loadZCML(package=imio.zamqp.dms)

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'imio.zamqp.dms:default')


IMIO_ZAMQP_DMS_FIXTURE = ImioZamqpDmsLayer()


IMIO_ZAMQP_DMS_INTEGRATION_TESTING = IntegrationTesting(
    bases=(IMIO_ZAMQP_DMS_FIXTURE,),
    name='ImioZamqpDmsLayer:IntegrationTesting'
)


IMIO_ZAMQP_DMS_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(IMIO_ZAMQP_DMS_FIXTURE,),
    name='ImioZamqpDmsLayer:FunctionalTesting'
)


IMIO_ZAMQP_DMS_ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        IMIO_ZAMQP_DMS_FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        z2.ZSERVER_FIXTURE
    ),
    name='ImioZamqpDmsLayer:AcceptanceTesting'
)
