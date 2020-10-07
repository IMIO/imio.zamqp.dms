Changelog
=========


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
