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
"""Manage user web sessions."""

import time

from nevow.inevow import ISession, IRequest
from twisted.python import log

from souhaits.core import IService

COOKIE_KEY  = 'Session_Souhaits'
COOKIE_LIFE = 3600 * 24 * 180  # 180 days of expiry time


class Avatar(object):
    """A connected user.

    An avatar is a connected user. It might be linked to a registered
    user or not.

    Members:
      user:
      session:
      identified: True if the user is positively identified
      pending: True if the user has given his email but hasn't
               confirmed his id
      anonymous: True if we don't know anything about the user
    """
    # pylint: disable-msg=R0903
    def __init__(self, user, srv, session):
        self.user = user
        self.session = session

        # Easy: when we know the email, the user is identified
        self.identified = user and user.email

        if self.identified:
            self.pending = False
            self.anonymous = False
        else:
            if user:
                self.pending = srv.pretendedEmail(user) is not None
                self.anonymous = not self.pending
            else:
                self.pending = False
                self.anonymous = True


def _set_cookie(ctx, cookie):
    """Sets the browser's session cookie."""
    delay = time.strftime("%a, %d %b %Y %H:%M:%S +0000",
                          time.gmtime(time.time() + COOKIE_LIFE))
    IRequest(ctx).addCookie(COOKIE_KEY, cookie,
                            expires=delay, path="/")


def _create_session(ctx):
    """Create a new session and give it a cookie."""
    # pylint: disable-msg=E1101
    user, new_cookie = IService(ctx).createSessionUser()
    log.msg('creating new session %s' % new_cookie)
    
    _set_cookie(ctx, new_cookie)
        
    return user, new_cookie


def session_cookie(ctx):
    """Return the session cookie or None if not set."""
    return IRequest(ctx).getCookie(COOKIE_KEY)


def maybe_user(ctx):
    """Return the user's avatar, but don't create a session."""
    cookie = session_cookie(ctx)
    srv = IService(ctx)
    # pylint: disable-msg=E1101
    user = Avatar(srv.getSessionUser(cookie), srv, cookie)
    if user.session:
        # extend the cookie
        _set_cookie(ctx, user.session)
    return user


def must_user(ctx):
    """Ensure that the user has a session and return its avatar."""
    user = maybe_user(ctx)
    srv = IService(ctx)

    if user.user:
        return user

    user, cookie = _create_session(ctx)
    return Avatar(user, srv, cookie)


def destroy_session(ctx):
    """Delete the current session from the database."""
    cookie = session_cookie(ctx)
    # pylint: disable-msg=E1101
    IService(ctx).destroySession(cookie)


def message(ctx, msg):
    """Log a message to display to the user."""
    session = ISession(ctx)
    pending = getattr(session, 'message', [])
    pending.append(msg)
    session.message = pending
