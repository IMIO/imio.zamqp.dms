# encoding: utf-8

from plone import api
from Products.CMFPlone.utils import base_hasattr

from collective.dms.batchimport.utils import createDocument, log
from collective.zamqp.consumer import Consumer
from imio.zamqp.core import base
from imio.zamqp.core.consumer import DMSMainFile, commit

import interfaces


class IncomingMailConsumer(base.DMSConsumer, Consumer):
    connection_id = 'dms.connection'
    exchange = 'dms.incomingmail'
    marker = interfaces.IIncomingMail
    queuename = 'dms.incomingmail.{0}'

IncomingMailConsumerUtility = IncomingMailConsumer()


def consume_incoming_mails(message, event):
    doc = IncomingMail('incoming-mail', 'dmsincomingmail', message)
    doc.create_or_update()
    commit()
    message.ack()


class IncomingMail(DMSMainFile):

    def create(self, obj_file):
        if self.scan_fields['scan_date']:
            self.metadata['reception_date'] = self.scan_fields['scan_date']
        if 'recipient_groups' not in self.metadata:
            self.metadata['recipient_groups'] = []
        (document, main_file) = createDocument(
            self.context,
            self.folder,
            self.document_type,
            '',
            obj_file,
            owner=self.obj.creator,
            metadata=self.metadata)
        self.set_scan_attr(main_file)
        document.reindexObject(idxs=('SearchableText'))

    def update(self, the_file, obj_file):
        if self.obj.version < getattr(the_file, 'version', 1):
            log.info('file not updated due to an oldest version (scan_id: {0})'.format(the_file.scan_id))
            return
        api.content.delete(obj=the_file)
        document = the_file.aq_parent
        # dont modify id !
        del self.metadata['id']
        for key, value in self.metadata.items():
            if base_hasattr(document, key) and value:
                setattr(document, key, value)
        new_file = self._upload_file(document, obj_file)
        self.set_scan_attr(new_file)
        document.reindexObject(idxs=('SearchableText'))
        log.info('file has been updated (scan_id: {0})'.format(new_file.scan_id))
