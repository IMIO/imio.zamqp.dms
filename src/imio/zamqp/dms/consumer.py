# encoding: utf-8

import datetime
from plone import api
from Products.CMFPlone.utils import base_hasattr

from collective.dms.batchimport.utils import createDocument, log
from collective.zamqp.consumer import Consumer
from imio.helpers.content import transitions
from imio.zamqp.core import base
from imio.zamqp.core.consumer import DMSMainFile, consume

import interfaces

# INCOMING MAILS #


class IncomingMailConsumer(base.DMSConsumer, Consumer):
    connection_id = 'dms.connection'
    exchange = 'dms.incomingmail'
    marker = interfaces.IIncomingMail
    queuename = 'dms.incomingmail.{0}'

IncomingMailConsumerUtility = IncomingMailConsumer()


def consume_incoming_mails(message, event):
    consume(IncomingMail, 'incoming-mail', 'dmsincomingmail', message)


class IncomingMail(DMSMainFile):

    def create(self, obj_file):
        # create a new im when barcode isn't found in catalog
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
        # update dmsfile when barcode is found in catalog
        if self.obj.version < getattr(the_file, 'version', 1):
            log.info('file not updated due to an oldest version (scan_id: {0})'.format(the_file.scan_id))
            return
        document = the_file.aq_parent
        #### TEST STATE
        api.content.delete(obj=the_file)
        # dont modify id !
        del self.metadata['id']
        for key, value in self.metadata.items():
            if base_hasattr(document, key) and value:
                setattr(document, key, value)
        new_file = self._upload_file(document, obj_file)
        self.set_scan_attr(new_file)
        document.reindexObject(idxs=('SearchableText'))
        log.info('file has been updated (scan_id: {0})'.format(new_file.scan_id))

# OUTGOING MAILS #


class OutgoingMailConsumer(base.DMSConsumer, Consumer):
    connection_id = 'dms.connection'
    exchange = 'dms.outgoingmail'
    marker = interfaces.IOutgoingMail
    queuename = 'dms.outgoingmail.{0}'

OutgoingMailConsumerUtility = OutgoingMailConsumer()


def consume_outgoing_mails(message, event):
    consume(OutgoingMail, 'outgoing-mail', 'dmsoutgoingmail', message)


class OutgoingMail(DMSMainFile):

    @property
    def file_portal_types(self):
        return ['dmsommainfile']

    def create(self, obj_file):
        # create a new om when barcode isn't found in catalog
        if self.scan_fields['scan_date']:
            self.metadata['outgoing_date'] = self.scan_fields['scan_date']
        (document, main_file) = createDocument(
            self.context,
            self.folder,
            self.document_type,
            '',
            obj_file,
            mainfile_type='dmsommainfile',
            owner=self.obj.creator,
            metadata=self.metadata)
        # MANAGE signed: to True ?
        self.scan_fields['signed'] = True
        self.set_scan_attr(main_file)
        document.reindexObject(idxs=('SearchableText'))
        api.content.transition(obj=document, transition='set_scanned')

    def update(self, the_file, obj_file):
        # update dmsfile when barcode is found in catalog
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
        # MANAGE signed: to True ?
        self.scan_fields['signed'] = True
        self.set_scan_attr(new_file)
        document.reindexObject(idxs=('SearchableText'))
        log.info('file has been updated (scan_id: {0})'.format(new_file.scan_id))

# OUTGOING GENERATED MAILS #


class OutgoingGeneratedMailConsumer(base.DMSConsumer, Consumer):
    connection_id = 'dms.connection'
    exchange = 'dms.outgoinggeneratedmail'
    marker = interfaces.IOutgoingGeneratedMail
    queuename = 'dms.outgoinggeneratedmail.{0}'

OutgoingGeneratedMailConsumerUtility = OutgoingGeneratedMailConsumer()


def consume_outgoing_generated_mails(message, event):
    consume(OutgoingGeneratedMail, 'outgoing-mail', 'dmsoutgoingmail', message)


class OutgoingGeneratedMail(DMSMainFile):

    @property
    def file_portal_types(self):
        return ['dmsommainfile']

    def create_or_update(self):
        with api.env.adopt_roles(['Manager']):
            obj_file = self.obj_file  # namedblobfile object
            the_file = self.existing_file  # dmsfile
            if the_file is None:
                log.error('file not found (scan_id: {0})'.format(self.scan_fields.get('scan_id')))
                return
            params = {'PD': False, 'PC': False, 'PVS': False}
            # PD = no date, PC = no closing, PVS = no new file
            if the_file.scan_user:
                for param in the_file.scan_user.split('|'):
                    params[param] = True
            # the_file.scan_user = None  # Don't remove for next generation
            self.document = the_file.aq_parent
            # search for signed file
            result = self.site.portal_catalog(
                portal_type='dmsommainfile',
                scan_id=self.scan_fields.get('scan_id'),
                signed=True
            )
            if result:
                # Is there a new version because export failing or really a new sending
                # Check if we are in a time delta of 20 hours: < = export failing else new sending
                signed_file = result[0].getObject()
                if (signed_file.scan_date and self.scan_fields['scan_date'] and
                        self.scan_fields['scan_date'] - signed_file.scan_date) < datetime.timedelta(0, 72000):
                    self.update(result[0].getObject(), obj_file)
                elif not params['PVS']:
                    # make a new file
                    self.create(obj_file)
                else:
                    log.error('file not considered: existing signed but PVS (scan_id: {0})'.format(
                              self.scan_fields.get('scan_id')))
            elif not params['PVS']:
                # make a new file
                self.create(obj_file)
            else:
                # register scan date on original model
                the_file.scan_date = self.scan_fields['scan_date']
            if not params['PD']:
                self.document.outgoing_date = (self.scan_fields['scan_date'] and self.scan_fields['scan_date'] or
                                               datetime.datetime.now())
                self.document.reindexObject(idxs=('in_out_date'))
            if not params['PC']:
                # close
                trans = {
                    'created': ['set_scanned', 'mark_as_sent'], 'scanned': [],
                    'proposed_to_service_chief': ['propose_to_be_signed', 'mark_as_sent'],
                    'to_be_signed': ['mark_as_sent'], 'to_print': ['propose_to_be_signed', 'mark_as_sent']
                }
                transitions(self.document, trans.get(api.content.get_state(self.document), []))

    def create(self, obj_file):
        # create a new dmsfile
        document = self.document
        main_file = self._upload_file(document, obj_file)
        self.scan_fields['signed'] = True
        self.set_scan_attr(main_file)
        document.reindexObject(idxs=('SearchableText'))
        log.info('file has been created (scan_id: {0})'.format(main_file.scan_id))

    def update(self, the_file, obj_file):
        # replace an existing dmsfile
        if self.obj.version < getattr(the_file, 'version', 1):
            log.info('file not updated due to an oldest version (scan_id: {0})'.format(the_file.scan_id))
            return
        document = the_file.aq_parent
        api.content.delete(obj=the_file)
        new_file = self._upload_file(document, obj_file)
        self.scan_fields['signed'] = True
        self.set_scan_attr(new_file)
        document.reindexObject(idxs=('SearchableText'))
        log.info('file has been updated (scan_id: {0})'.format(new_file.scan_id))
