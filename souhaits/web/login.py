# -*- coding: utf-8 -*-
# This file is part of Mes-Souhaits.
#
# Copyright (c) 2016 Frederic Gobry
#
# Mes-Souhaits is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# Mes-Souhaits is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License along
# with Mes-Souhaits. If not, see: <http://www.gnu.org/licenses/>.
"""Handle login operations.

This module provides the login page and a login fragment to be
embedded in other pages.
"""

from nevow import loaders
from nevow import rend
from nevow import tags as T
from nevow import url
from nevow.inevow import IRequest

from souhaits import TEMPLATE_DIR
from souhaits.core import IService, validate_email
from souhaits.session import must_user, message
from souhaits.web import widget

class LoginInfo(object):
    """Hold all the login form information."""

    def __init__(self, warnings=True, force_reconnect=False):
        self.email = ''
        self.reconnect = False  # user is reconnecting
        # assume the account already exists
        self.force_reconnect = force_reconnect
        self.referer = '/'  # URL to redirect the user to
        self.known = True
        self.warnings = warnings  # display warnings

    def is_valid(self):
        """Return True if the login info can be used."""
        return validate_email(self.email) and self.known


def login_info_from_context(ctx):
    """Collect all login info from the context."""
    info = LoginInfo()
    email = ctx.arg('email')
    if email:
        info.email = email.decode('utf-8')
    else:
        info.email = u''
    info.reconnect = ctx.arg('reconnect') == 'true'
    info.referer = url.URL.fromString(
        ctx.arg('referer') or IRequest(ctx).getHeader('referer') or '/')
    if info.reconnect:
        # pylint: disable-msg=E1101
        info.known = IService(ctx).getUserByEmail(info.email)
    return info


class LoginFragment(rend.Fragment, widget.RoundedBoxMixin):
    """Fragment displaying a login box."""
    docFactory = loaders.xmlfile(templateDir=TEMPLATE_DIR,
                                 template='login_box.xml')

    def render_login_warnings(self, ctx, data):
        """Render the login errors."""
        # pylint: disable-msg=E1101
        if IRequest(ctx).method == 'POST' and data.warnings:
            if not data.email:
                return ctx.tag[u"Vous n'avez pas fourni votre adresse email."]
            if not validate_email(data.email):
                return ctx.tag[u"Votre adresse email est incorrecte."]
            if not data.known:
                return ctx.tag[u'Cette adresse email est inconnue.']
        return ''

    def render_login_email(self, ctx, data):
        """Render the email address."""
        return ctx.tag(value=data.email)

    def render_login_referer(self, ctx, data):
        """Render the page referer."""
        return ctx.tag(value=data.referer)

    def render_login_reconnect(self, ctx, data):
        """Render the 'reconnect?' checkbox."""
        if data.force_reconnect:
            # replace the checkbox by a hidden field
            # pylint: disable-msg=E1101
            return T.input(type='hidden', name='reconnect', value='true')
        if data.reconnect:
            ctx.tag(checked='yes')
        return ctx.tag

    def render_login(self, ctx, data):
        """Render the whole login box."""
        # pylint: disable-msg=E1101
        if IRequest(ctx).method == 'POST' and data.is_valid():
            # Simply send a challenge to this email address
            message(ctx,
                    u"""Un message de confirmation a été envoyé """
                    u"""à l'adresse <%s>.""" % data.email)

            IService(ctx).pretend_email_address(must_user(ctx).user, data.email)
            IRequest(ctx).redirect(data.referer)
            IRequest(ctx).finish()
        else:
            return ctx.tag

