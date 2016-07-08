# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""

from zope.interface import Interface


class IIncomingMail(Interface):
    """Marker interface for incoming mails"""


class IOutgoingMail(Interface):
    """Marker interface for outgoing mails"""
