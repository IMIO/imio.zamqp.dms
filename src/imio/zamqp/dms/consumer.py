# encoding: utf-8
from collective.behavior.talcondition.utils import _evaluateExpression
from collective.contact.plonegroup.config import get_registry_organizations
from collective.contact.plonegroup.utils import get_person_from_userid
from collective.contact.plonegroup.utils import get_selected_org_suffix_principal_ids
from collective.contact.plonegroup.utils import organizations_with_suffixes
from collective.dms.batchimport.utils import createDocument
from collective.dms.batchimport.utils import log
from collective.dms.mailcontent.dmsmail import internalReferenceIncomingMailDefaultValue
from collective.zamqp.consumer import Consumer
from imio.dms.mail import IM_EDITOR_SERVICE_FUNCTIONS
from imio.dms.mail.interfaces import IPersonnelContact
from imio.dms.mail.utils import create_period_folder
from imio.dms.mail.utils import get_dms_config
from imio.dms.mail.utils import sub_create
from imio.helpers.cache import get_plone_groups_for_user
from imio.helpers.security import get_user_from_criteria
from imio.helpers.workflow import do_transitions
from imio.zamqp.core import base
from imio.zamqp.core.consumer import consume
from imio.zamqp.core.consumer import DMSMainFile
from io import BytesIO
from plone import api
from plone.dexterity.utils import createContentInContainer
from plone.namedfile.file import NamedBlobFile
from Products.CMFCore.WorkflowCore import WorkflowException
from Products.CMFPlone.utils import base_hasattr
from Products.CMFPlone.utils import safe_unicode
from unidecode import unidecode
from z3c.relationfield.relation import RelationValue
from zope.component import getUtility
from zope.intid.interfaces import IIntIds
from zope.schema.interfaces import IVocabularyFactory

import datetime
import interfaces
import json
import re
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
        file_metadata = self.obj.context.file_metadata  # noqa
        for metadata, attr, voc in (('creating_group', 'creating_group',
                                     u'imio.dms.mail.ActiveCreatingGroupVocabulary'),
                                    ('treating_group', 'treating_groups',
                                     u'collective.dms.basecontent.treating_groups')):
            if not file_metadata.get(metadata, ''):
                continue
            parts = file_metadata[metadata].split(cg_separator)
            if len(parts) > 1:
                self.metadata[attr] = parts[1].strip()  # noqa
            else:
                continue
            factory = getUtility(IVocabularyFactory, voc)
            voc_i = factory(self.folder)  # noqa
            if self.metadata[attr] not in [term.value for term in voc_i._terms]:  # noqa
                del self.metadata[attr]  # noqa


class IncomingMail(DMSMainFile, CommonMethods):

    def create(self, obj_file):
        # create a new im when barcode isn't found in catalog
        if self.scan_fields['scan_date']:
            self.metadata['reception_date'] = self.scan_fields['scan_date']
        if 'recipient_groups' not in self.metadata:
            self.metadata['recipient_groups'] = []
        self.creating_group_split()
        mail_types_rec = api.portal.get_registry_record('imio.dms.mail.browser.settings.IImioDmsMailConfig.mail_types')
        mail_types = [dic['value'] for dic in mail_types_rec if dic['active']]
        self.metadata['mail_type'] = mail_types[0]
        (document, main_file) = createDocument(
            self.context,
            create_period_folder(self.folder, datetime.datetime.now()),
            self.document_type,
            '',
            obj_file,
            owner=self.obj.creator,
            metadata=self.metadata)
        self.set_scan_attr(main_file)
        main_file.reindexObject(idxs=('SearchableText', ))
        document.reindexObject(idxs=('SearchableText', ))

    def _upload_file_extra_data(self):
        """ """
        return self.scan_fields

    def update(self, the_file, obj_file):
        # update dmsfile when barcode is found in catalog
        if self.obj.version < getattr(the_file, 'version', 1):
            log.info('file not updated due to an oldest version (scan_id: {0})'.format(the_file.scan_id))
            return
        document = the_file.aq_parent
        # TODO TEST document STATE ?
        api.content.delete(obj=the_file)
        # dont modify id !
        del self.metadata['id']
        del self.metadata['mail_type']
        for key, value in self.metadata.items():
            if base_hasattr(document, key) and value:
                setattr(document, key, value)
        new_file = self._upload_file(document, obj_file)
        document.reindexObject(idxs=('SearchableText', ))
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

    def _upload_file_extra_data(self):
        """ """
        return self.scan_fields

    def create(self, obj_file):
        # create a new om when barcode isn't found in catalog
        if self.scan_fields['scan_date']:
            self.metadata['outgoing_date'] = self.scan_fields['scan_date']
        self.creating_group_split()
        (document, main_file) = createDocument(
            self.context,
            create_period_folder(self.folder, datetime.datetime.now()),
            self.document_type,
            '',
            obj_file,
            mainfile_type='dmsommainfile',
            owner=self.obj.creator,
            metadata=self.metadata)
        # MANAGE signed: to True ?
        self.scan_fields['signed'] = True
        self.set_scan_attr(main_file)
        main_file.reindexObject(idxs=('SearchableText', ))
        document.reindexObject(idxs=('SearchableText', ))
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
        # MANAGE signed: to True ?
        self.scan_fields['signed'] = True
        new_file = self._upload_file(document, obj_file)
        document.reindexObject(idxs=('SearchableText', ))
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
            self.document = the_file.aq_parent  # noqa
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
                if (signed_file.scan_date and self.scan_fields['scan_date']
                        and self.scan_fields['scan_date'] - signed_file.scan_date) < datetime.timedelta(0, 72000):
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
                self.document.outgoing_date = (self.scan_fields['scan_date'] and self.scan_fields['scan_date']
                                               or datetime.datetime.now())
                self.document.reindexObject(idxs=('in_out_date', ))
            if not params['PC'] and (not self.document.is_email() or self.document.email_status):
                # close
                trans = {
                    'created': ['mark_as_sent', 'propose_to_be_signed', 'set_to_print', 'propose_to_n_plus_1'],
                    'scanned': ['mark_as_sent'],
                    'proposed_to_n_plus_1': ['mark_as_sent', 'propose_to_be_signed', 'set_to_print'],
                    'to_be_signed': ['mark_as_sent'], 'to_print': ['propose_to_be_signed', 'mark_as_sent']
                }
                state = api.content.get_state(self.document)
                i = 0
                while state != 'sent' and i < 10:
                    do_transitions(self.document, trans.get(state, []))
                    state = api.content.get_state(self.document)
                    i += 1

    def _upload_file_extra_data(self):
        """ """
        return self.scan_fields

    def create(self, obj_file):
        # create a new dmsfile
        document = self.document
        self.scan_fields['signed'] = True
        main_file = self._upload_file(document, obj_file)
        document.reindexObject(idxs=('SearchableText', ))
        log.info('file has been created (scan_id: {0})'.format(main_file.scan_id))

    def update(self, the_file, obj_file):
        # replace an existing dmsfile
        if self.obj.version < getattr(the_file, 'version', 1):
            log.info('file not updated due to an oldest version (scan_id: {0})'.format(the_file.scan_id))
            return
        document = the_file.aq_parent
        api.content.delete(obj=the_file)
        self.scan_fields['signed'] = True
        new_file = self._upload_file(document, obj_file)
        document.reindexObject(idxs=('SearchableText', ))
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
        files = tar.getnames()
        filename = 'email.pdf'
        if 'email.eml' in files:
            filename = 'email.eml'
        metadata = json.loads(tar.extractfile('metadata.json').read())
        attachments = [
            {'filename': member.path.decode('utf8').split('/')[-1],  # noqa
             'content': tar.extractfile(member).read()}
            for member in tar.getmembers()
            if member.path.startswith("/attachments/")  # noqa
        ]
        return (safe_unicode(filename), tar.extractfile(filename).read()), metadata, attachments

    def create(self, obj_file):
        pass

    def create_or_update(self):
        mf_tup, maildata, attachments = self.extract_tar(self.file_content)
        # maildata = {
        # u'Origin': u'Agent forward',
        # u'From': [[u'Fr\xe9d\xe9ric Rasic', u'frasic@imio.be']],
        # u'Cc': [],
        # u'Agent': [[u'St\xe9phan Geulette', u'stephan.geulette@imio.be']],
        # u'To': [[u'tous@imio.be', u'tous@imio.be']],
        # u'Subject': u'[Tous] Diffusion \xe9lectronique des documents de paie'}

        # self.metadata = {
        # 'file_title': u'01Z999900000001.tar', 'mail_type': None, 'id': u'01Z999900000001'}
        # self.scan_fields = {
        # 'scan_id': u'01Z999900000001', 'scanner': u'pc-scan01', , 'scan_user': u'testuser'
        # 'scan_date': datetime.datetime(2020, 10, 20, 16, 53, 23), 'version': 1, 'pages_number': None}

        for key in ('scanner', 'scan_user', 'pages_number'):
            del self.scan_fields[key]

        self.metadata['title'] = maildata['Subject'] or u'(VIDE)'
        # or translate(u'(EMPTY)', domain='imio.zamqp.dms', context=getRequest())
        if 'internal_reference_no' not in self.metadata:
            self.metadata['internal_reference_no'] = internalReferenceIncomingMailDefaultValue(self.context)
        if self.scan_fields['scan_date']:
            self.metadata['reception_date'] = self.scan_fields['scan_date']
        mail_types_rec = api.portal.get_registry_record('imio.dms.mail.browser.settings.IImioDmsMailConfig.mail_types')
        mail_types = [dic['value'] for dic in mail_types_rec if dic['active']]
        if u'email' in mail_types:
            self.metadata['mail_type'] = u'email'
        else:
            self.metadata['mail_type'] = mail_types[0]

        intids = getUtility(IIntIds)
        with api.env.adopt_user(user=api.user.get_current()):
            document = sub_create(self.folder, 'dmsincoming_email', datetime.datetime.now(), self.metadata.pop('id'),
                                  **self.metadata)
            log.info('document has been created (id: %s)' % document.id)
            catalog = api.portal.get_tool('portal_catalog')

            # original_mail_date (sent date of relevant email)
            if maildata.get('Original mail date'):
                parsed_original_date = datetime.datetime.strptime(
                    maildata.get('Original mail date'),
                    '%Y-%m-%d',
                )
                document.original_mail_date = parsed_original_date

            # sender (all contacts with the "From" email)
            oes_eml = u""
            if maildata.get('From'):
                if maildata['From'][0][0]:
                    realname, oes_eml = maildata['From'][0]
                    oes = u'"{0}" <{1}>'.format(unidecode(realname), oes_eml)
                else:
                    oes = maildata['From'][0][1]
                document.orig_sender_email = oes
                results = catalog.unrestrictedSearchResults(email=maildata['From'][0][1].lower(),
                                                            portal_type=['organization', 'person', 'held_position'])
                if results:
                    filtered = []
                    internals = {}
                    for brain in results:
                        obj = brain._unrestrictedGetObject()
                        if brain.portal_type != 'held_position' or not IPersonnelContact.providedBy(obj):
                            filtered.append(obj)
                            continue
                        person = obj.get_person()
                        internals.setdefault(person, []).append(obj)
                    # for internal positions, we keep only the corresponding primary org position or only one
                    for person in internals:
                        if person.primary_organization:
                            hps = [hp for hp in internals[person]
                                   if hp.get_organization().UID() == person.primary_organization]
                        else:
                            hps = internals[person]
                        filtered.append(hps[0])
                    document.sender = [RelationValue(intids.getId(ctc)) for ctc in filtered]

            # before routing
            users = {}  # TODO no need to be used later and no orgs needed
            userid = None  # user ID of the agent
            agent_email = None
            assigned_user = None
            tg = None
            active_orgs = get_registry_organizations()
            # get a userid for the agent
            if maildata.get('Agent'):
                agent_email = maildata['Agent'][0][1].lower()
                results = catalog.unrestrictedSearchResults(email=agent_email,
                                                            portal_type=['held_position'],
                                                            object_provides=IPersonnelContact.__identifier__)
                for brain in results:
                    obj = brain._unrestrictedGetObject()
                    person = obj.get_person()
                    org = obj.get_organization().UID()
                    if org in active_orgs:
                        users.setdefault(person.userid, set()).add(org)
                if not users:
                    for udic in get_user_from_criteria(self.site, email=agent_email):
                        if udic['email'].lower() != agent_email:  # to be sure email is not a part of longer email
                            continue
                        groups = get_plone_groups_for_user(user_id=udic['userid'])
                        orgs = organizations_with_suffixes(groups, IM_EDITOR_SERVICE_FUNCTIONS, group_as_str=True)
                        users.setdefault(udic['userid'], set()).update([org for org in orgs if org in active_orgs])
                if len(users) > 1:
                    # we keep the one with more hps
                    userid = sorted(users.items(), key=lambda tup: len(tup[1]), reverse=True)[0][0]
                    log.error('Multiple users found for agent email {}. Kept {}'.format(agent_email, userid))
                elif len(users) == 1:
                    userid = users.keys()[0]

            # routing rules from config
            rt = api.portal.get_registry_record("imio.dms.mail.browser.settings.IImioDmsMailConfig.iemail_routing")
            for dic in rt or []:
                # check transfer_email
                if dic["transfer_email_pat"].strip():
                    if agent_email and not re.match(dic["transfer_email_pat"], agent_email):
                        continue
                # check original email sender
                if dic["original_email_pat"].strip():
                    if oes_eml and not re.match(dic["original_email_pat"], oes_eml):
                        continue
                # check condition 1
                extra = {"maildata": maildata}
                if userid:
                    extra["member"] = api.user.get(userid)
                if not _evaluateExpression(self.folder, expression=dic["tal_condition_1"], extra_expr_ctx=extra):
                    continue
                # assigned_user value
                if dic["user_value"] == "_transferer_":
                    assigned_user = userid
                elif dic["user_value"] == "_empty_":
                    assigned_user = None
                else:
                    assigned_user = dic["user_value"]
                # check condition 2
                extra["assigned_user"] = assigned_user
                if not _evaluateExpression(self.folder, expression=dic["tal_condition_2"], extra_expr_ctx=extra):
                    continue
                # treating_groups value
                if dic["tg_value"] == "_uni_org_only_":
                    au_groups = get_plone_groups_for_user(user_id=assigned_user)
                    au_orgs = organizations_with_suffixes(au_groups, IM_EDITOR_SERVICE_FUNCTIONS, group_as_str=True)
                    au_orgs = [org for org in au_orgs if org in active_orgs]
                    # get the only one org of the assigned user
                    if assigned_user and len(au_orgs) == 1:
                        tg = au_orgs[0]
                elif dic["tg_value"] == "_primary_org_":
                    if assigned_user:
                        person = get_person_from_userid(assigned_user, unrestricted=True, only_active=True)
                        if person is None:
                            person = get_person_from_userid(assigned_user, unrestricted=True)
                        # get the primary org of the assigned user
                        if person and person.primary_organization and person.primary_organization in active_orgs:
                            tg = person.primary_organization
                elif dic["tg_value"] == "_hp_":
                    if assigned_user and assigned_user == userid:
                        # we get an organization from the userid
                        person = get_person_from_userid(assigned_user, unrestricted=True, only_active=True)
                        if person is None:
                            person = get_person_from_userid(assigned_user, unrestricted=True)
                        if person:
                            hps = person.get_held_positions()
                            orgs = [hp.get_organization().UID() for hp in hps]
                            orgs = [org for org in orgs if org in active_orgs]
                            if orgs:
                                if (len(orgs) > 1 and person.primary_organization
                                        and person.primary_organization in active_orgs):
                                    tg = person.primary_organization
                                else:
                                    tg = orgs[0]
                elif dic["tg_value"] == "_empty_":
                    tg = None  # already
                else:
                    tg = dic["tg_value"]
                # break the loop if we got this far, it means the routing rule is applied
                break

            if tg and assigned_user:
                # check if user is well in correct groups
                pids = get_selected_org_suffix_principal_ids(tg, IM_EDITOR_SERVICE_FUNCTIONS)
                if assigned_user in pids:
                    document.assigned_user = assigned_user
                    document.treating_groups = tg
            elif tg:
                document.treating_groups = tg
                document.assigned_user = None
            elif assigned_user:
                document.assigned_user = None

            # state set rules from config
            to_state = None
            trs = []
            ss = api.portal.get_registry_record("imio.dms.mail.browser.settings.IImioDmsMailConfig.iemail_state_set")
            for dic in ss or []:
                # check transfer_email
                if dic["transfer_email_pat"].strip():
                    if agent_email and not re.match(dic["transfer_email_pat"], agent_email):
                        continue
                # check original email sender
                if dic["original_email_pat"].strip():
                    if oes_eml and not re.match(dic["original_email_pat"], oes_eml):
                        continue
                # check condition 1
                extra = {"maildata": maildata}
                if userid:
                    extra["member"] = api.user.get(userid)
                if not _evaluateExpression(self.folder, expression=dic["tal_condition_1"], extra_expr_ctx=extra):
                    continue
                # state value
                s_v = dic["state_value"]
                if s_v == u"created":
                    break
                if document.treating_groups:
                    trs = ["propose_to_n_plus_1", "propose_to_n_plus_2", "propose_to_n_plus_3", "propose_to_n_plus_4",
                           "propose_to_n_plus_5", "propose_to_manager", "propose_to_pre_manager"]
                    to_state = s_v
                    if s_v == u"proposed_to_premanager":
                        trs = ["propose_to_pre_manager"]
                    elif s_v == u"proposed_to_manager":
                        trs = ["propose_to_manager", "propose_to_pre_manager"]
                    elif s_v == u"proposed_to_agent":
                        trs.insert(0, "propose_to_agent")
                    elif s_v == u"in_treatment":
                        trs.insert(0, "propose_to_agent")
                        trs.insert(0, "treat")
                    elif s_v == u"closed":
                        trs.insert(0, "propose_to_agent")
                        trs.insert(0, "treat")
                        trs.insert(0, "close")
                    elif s_v.startswith(u"proposed_to_n_plus_"):
                        level = s_v.split(u"proposed_to_n_plus_")[-1]
                        trs = [tr for tr in trs if tr[-1] == "r" or (tr[-1] in "12345" and tr[-1] >= level)]
                    elif s_v in (u"_n_plus_h_", u"_n_plus_l_"):
                        to_state = 'proposed_to_agent'
                        tr_levels = get_dms_config(['transitions_levels', 'dmsincomingmail'])
                        wf_from_to = get_dms_config(['wf_from_to', 'dmsincomingmail', 'n_plus', 'to'])
                        st_from_tr = {tr: st for (st, tr) in wf_from_to}
                        if tr_levels['created'].get(document.treating_groups):
                            tr = tr_levels['created'][document.treating_groups][0]
                            if s_v == '_n_plus_h_':
                                to_state = st_from_tr[tr]
                            elif s_v == '_n_plus_l_':
                                while tr != 'propose_to_agent':
                                    to_state = st_from_tr[tr]
                                    tr = tr_levels[to_state][document.treating_groups][0]
                        if to_state == 'proposed_to_agent':
                            trs.insert(0, 'propose_to_agent')
                    else:
                        to_state = None
                break

            # we store a flag to indicate that this content is agent forwarded and has been transitioned to
            if to_state is not None:
                setattr(document, '_iem_agent', to_state)
                i = 0
                state = api.content.get_state(document)
                pw = api.portal.get_tool("portal_workflow")
                while state != to_state and i < 10:
                    for tr in trs:
                        try:
                            pw.doActionFor(document, tr)
                        except WorkflowException:
                            continue
                        state = api.content.get_state(document)
                        if state == to_state:
                            break
                    i += 1

            file_object = NamedBlobFile(mf_tup[1], filename=mf_tup[0])
            self.metadata['file_title'] = mf_tup[0]
            main_file = self._upload_file(document, file_object)
            log.info('file has been created (scan_id: {0})'.format(main_file.scan_id))
            document.reindexObject()

            for attachment in attachments:
                file_object = NamedBlobFile(
                    attachment['content'],
                    filename=attachment['filename'])
                appendix = createContentInContainer(
                    document,
                    'dmsappendixfile',
                    title=attachment['filename'],
                    file=file_object)
                log.info('appendix has been created (id: %s)' % appendix.id)

    def _upload_file_extra_data(self):
        """ """
        return self.scan_fields
