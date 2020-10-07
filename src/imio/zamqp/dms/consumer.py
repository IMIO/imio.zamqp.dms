# encoding: utf-8

from collective.contact.plonegroup.config import get_registry_organizations
from collective.contact.plonegroup.utils import organizations_with_suffixes
from collective.dms.batchimport.utils import createDocument
from collective.dms.batchimport.utils import log
from collective.dms.mailcontent.dmsmail import internalReferenceIncomingMailDefaultValue
from collective.dms.mailcontent.dmsmail import receptionDateDefaultValue
from collective.zamqp.consumer import Consumer
from imio.helpers.content import transitions
from imio.zamqp.core import base
from imio.zamqp.core.consumer import consume
from imio.zamqp.core.consumer import DMSMainFile
from io import BytesIO
from plone import api
from plone.dexterity.utils import createContentInContainer
from plone.namedfile.file import NamedBlobFile
from Products.CMFPlone.utils import base_hasattr
from z3c.relationfield.relation import RelationValue
from zope.component import getUtility
from zope.intid.interfaces import IIntIds
from zope.schema.interfaces import IVocabularyFactory

import datetime
import interfaces
import json
import tarfile


cg_separator = ' ___ '

# INCOMING MAILS #


class IncomingMailConsumer(base.DMSConsumer, Consumer):
    connection_id = 'dms.connection'
    exchange = 'dms.incomingmail'
    marker = interfaces.IIncomingMail
    queuename = 'dms.incomingmail.{0}'

IncomingMailConsumerUtility = IncomingMailConsumer()


def consume_incoming_mails(message, event):
    consume(IncomingMail, 'incoming-mail', 'dmsincomingmail', message)


class CommonMethods(object):

    def creating_group_split(self):
        # we manage optional fields (1.3 schema)
        file_metadata = self.obj.context.file_metadata
        for metadata, attr, voc in (('creating_group', 'creating_group',
                                     u'imio.dms.mail.ActiveCreatingGroupVocabulary'),
                                    ('treating_group', 'treating_groups',
                                     u'collective.dms.basecontent.treating_groups')):
            if not file_metadata.get(metadata, ''):
                continue
            parts = file_metadata[metadata].split(cg_separator)
            if len(parts) > 1:
                self.metadata[attr] = parts[1].strip()
            factory = getUtility(IVocabularyFactory, voc)
            voc_i = factory(self.folder)
            if self.metadata[attr] not in [term.value for term in voc_i._terms]:
                del self.metadata[attr]


class IncomingMail(DMSMainFile, CommonMethods):

    def create(self, obj_file):
        # create a new im when barcode isn't found in catalog
        if self.scan_fields['scan_date']:
            self.metadata['reception_date'] = self.scan_fields['scan_date']
        if 'recipient_groups' not in self.metadata:
            self.metadata['recipient_groups'] = []
        self.creating_group_split()
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


class OutgoingMail(DMSMainFile, CommonMethods):

    @property
    def file_portal_types(self):
        return ['dmsommainfile']

    def create(self, obj_file):
        # create a new om when barcode isn't found in catalog
        if self.scan_fields['scan_date']:
            self.metadata['outgoing_date'] = self.scan_fields['scan_date']
        self.creating_group_split()
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
        with api.env.adopt_user(username='scanner'):
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


class OutgoingGeneratedMail(DMSMainFile, CommonMethods):

    @property
    def file_portal_types(self):
        return ['dmsommainfile']

    @property
    def existing_file(self):
        result = self.site.portal_catalog(
            portal_type=self.file_portal_types,
            scan_id=self.scan_fields.get('scan_id'),
            signed=False,
            sort_on='created',
            sort_order='descending'
        )
        if result:
            return result[0].getObject()

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
                    'created': ['propose_to_be_signed', 'mark_as_sent'], 'scanned': [],
                    'proposed_to_n_plus_1': ['propose_to_be_signed', 'mark_as_sent'],
                    'to_be_signed': ['mark_as_sent'], 'to_print': ['propose_to_be_signed', 'mark_as_sent']
                }
                state = api.content.get_state(self.document)
                i = 0
                while state != 'sent' and i < 10:
                    transitions(self.document, trans.get(state, []))
                    state = api.content.get_state(self.document)
                    i += 1

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


# INCOMING EMAILS #


class IncomingEmailConsumer(base.DMSConsumer, Consumer):
    connection_id = 'dms.connection'
    exchange = 'dms.incoming.email'
    marker = interfaces.IIncomingEmail
    queuename = 'dms.incoming.email.{0}'


IncomingEmailConsumerUtility = IncomingEmailConsumer()


def consume_incoming_emails(message, event):
    consume(IncomingEmail, 'incoming-mail', 'dmsincoming_email', message)


class IncomingEmail(DMSMainFile, CommonMethods):

    def extract_tar(self, archive_content):
        archive_file = BytesIO(archive_content)
        tar = tarfile.open(fileobj=archive_file)
        pdf = tar.extractfile('email.pdf').read()
        metadata = json.loads(tar.extractfile('metadata.json').read())
        attachments = [
            {'filename': member.path.decode('utf8').split('/')[-1],
             'content': tar.extractfile(member).read()}
            for member in tar.getmembers()
            if member.path.startswith("/attachments/")
        ]
        return pdf, metadata, attachments

    def create_or_update(self):
        pdf, metadata, attachments = self.extract_tar(self.file_content)

        metadata['title'] = metadata['Subject']
        file_title = 'Incoming email'
        if 'internal_reference_no' not in metadata:
            metadata['internal_reference_no'] = internalReferenceIncomingMailDefaultValue(self.context)
        if 'reception_date' not in metadata:
            metadata['reception_date'] = receptionDateDefaultValue(self.context)

        intids = getUtility(IIntIds)
        owner = api.user.get_current().id
        with api.env.adopt_user(username=owner):
            document = createContentInContainer(self.folder, 'dmsincoming_email', **metadata)
            log.info('document has been created (id: %s)' % document.id)
            catalog = api.portal.get_tool('portal_catalog')

            # sender (all contacts with the "From" email)
            if metadata.get('From'):
                from_email = metadata['From'][0][1]
                results = catalog.unrestrictedSearchResults(email=from_email)
                if results:
                    document.sender = [RelationValue(intids.getId(brain.getObject())) for brain in results]

            # treating_groups (agent internal service, if there is one)
            # assigned_user (agent user; only if treating_groups assigned)
            if metadata.get('Agent'):
                agent_email = metadata['Agent'][0][1]
                results = catalog.unrestrictedSearchResults(email=agent_email, portal_type='person',
                                                            object_provides=['imio.dms.mail.interfaces.IPersonnelContact'])
                for brain in results:
                    contact = brain.getObject()
                    userid = contact.userid
                    if userid:
                        groups = api.group.get_groups(username=userid)
                        agent_orgs = organizations_with_suffixes(groups, ['validateur', 'editeur'])
                        active_orgs = get_registry_organizations()
                        agent_active_orgs = [org for org in agent_orgs if org in active_orgs]
                        if agent_active_orgs:
                            document.treating_groups = agent_active_orgs[0]  # only take one
                            document.assigned_user = userid
                            break

            # original_mail_date (sent date of relevant email)
            if metadata.get('Original mail date'):
                parsed_original_date = datetime.datetime.strptime(
                    metadata.get('Original mail date'),
                    '%Y-%m-%d',
                )
                document.original_mail_date = parsed_original_date

            if document.treating_groups and document.assigned_user:
                # TODO maybe multiple levels !! and directly to agent ?
                api.content.transition(obj=document, transition='propose_to_n_plus_1')

            file_object = NamedBlobFile(
                pdf,
                filename=u'email.pdf')
            version = createContentInContainer(
                document,
                'dmsmainfile',
                title=file_title,
                file=file_object)

            for attachment in attachments:
                file_object = NamedBlobFile(
                    attachment['content'],
                    filename=attachment['filename'])
                version = createContentInContainer(
                    document,
                    'dmsappendixfile',
                    title=attachment['filename'],
                    file=file_object)
                log.info('file document has been created (id: %s)' % version.id)
