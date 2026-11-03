# -*- coding: utf-8 -*-

from imio.dataexchange.core.document import Document
from imio.dms.mail.utils import Dummy

import cPickle
import json
import os
import tarfile


def create_fake_message(klass, dic):
    """Create a message of klass instance with dic params."""
    doc = Document(**dic)
    inst = klass(doc)
    return Dummy(body=cPickle.dumps(inst))


def create_tarfile(tdir, name, content, main='email.pdf'):
    """Create a tar file with an empty main file (email.pdf or email.eml) and the content."""
    f = open(os.path.join(tdir, main), 'w')
    f.close()
    f = open(os.path.join(tdir, 'metadata.json'), 'w')
    f.write(content)
    f.close()
    f = tarfile.open(os.path.join(tdir, name), 'w')
    f.add(os.path.join(tdir, main), arcname=main)
    f.add(os.path.join(tdir, 'metadata.json'), arcname='metadata.json')
    f.close()
    return open(os.path.join(tdir, name), 'rb')


def store_fake_content(tdir, klass, params, metadata=None, main='email.pdf'):
    """Patch file_content value."""
    if metadata is None:
        metadata = {}
    if klass.__name__ == "IncomingEmail":
        fh = create_tarfile(tdir, params["file_metadata"]["filename"], json.dumps(metadata), main=main)
    else:
        fh = open(os.path.join(os.path.dirname(__file__), "tests", "example.pdf"), "rb")
    setattr(klass, "file_content", fh.read())
    fh.close()
