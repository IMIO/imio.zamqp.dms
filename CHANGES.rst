Changelog
=========


0.10 (2021-06-04)
-----------------

- Changed email dmsfile title (and id)
  [sgeulette]
- Store original_sender_email on dmsincoming_email
  [sgeulette]
- Use right metadata set to create dmsincoming_email
  [sgeulette]
- Use current_user obj directly to avoid error when username is different from userid
  [sgeulette]
- Added tests
  [sgeulette]

0.9 (2021-04-21)
----------------

- Changed new incoming email state following iemail_manual_forward_transitions option.
  [sgeulette]
- Changed the way an internal user is searched
  [sgeulette]
- Added default email mail_type
  [sgeulette]
- Defined _upload_file_extra_data to replace set_scan_attr when possible
  [sgeulette]
- Removed Subject value from email metadata
  [sgeulette]
- Set `_iem_agent` attribute when agent forwarded email and document transitioned
  [sgeulette]
- Closed a generated document only if not an email or email has been sent
  [sgeulette]

0.8 (2020-10-07)
----------------

- Corrected available created transitions in OutgoingGeneratedMail.
  [sgeulette]
- Replaced service_chief by n_plus_1
  [sgeulette]

0.7 (2019-11-25)
----------------

- Managed creating_group and treating_group metadatas.
  [sgeulette]
- Added consumer for dmsincoming_email type
  [daggelpop,sgeulette]

0.6 (2018-07-24)
----------------

- Search differently existing file for OutgoingGeneratedMail.
  [sgeulette]

0.5 (2018-03-29)
----------------

- Use scanner role to do 'set_scanned' transition.
  [sgeulette]

0.4 (2018-01-24)
----------------

- Changed outgoing date value in OutgoingGeneratedMail consumer.
  [sgeulette]

0.3 (2018-01-24)
----------------

- Set datetime value in outgoing date.
  [sgeulette]

0.2 (2018-01-22)
----------------

- Replaced file_portal_type by file_portal_types (list).
  [sgeulette]
- No more use commit function but generic consume
  [sgeulette]
- Removed useless transition
  [sgeulette]

0.1 (2017-06-01)
----------------

- Added OutgoingMailConsumer
  [sgeulette]
- Added OutgoingGeneratedMailConsumer
  [sgeulette]
- Replaced and refactored imio.dms.amqp, using imio.zamqp.core as base.
  [sgeulette]
