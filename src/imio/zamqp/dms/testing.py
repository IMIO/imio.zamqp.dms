# -*- coding: utf-8 -*-

from imio.dataexchange.core.document import Document
from imio.dms.mail.utils import Dummy

import cPickle


def create_fake_message(klass, dic):
    """Create a message of klass instance with dic params."""
    doc = Document(**dic)
    inst = klass(doc)
    return Dummy(body=cPickle.dumps(inst))
