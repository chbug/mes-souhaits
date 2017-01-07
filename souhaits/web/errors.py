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
"""Handle the error pages."""

from souhaits.core import IService
from souhaits.web.base import BasePage
from zope.interface import implements  # pylint: disable-msg=F0401

from nevow.inevow import IRequest, ICanHandleException, ICanHandleNotFound
from twisted.web import http
from twisted.python import log

from nevow import tags as T

class The500Page(BasePage):
    """Serves the 500 internal error page."""

    implements(ICanHandleException)

    # pylint: disable-msg=E1101
    contentTags = T.div[
        T.h1[u'Aïe. Problème de serveur'],
        T.p[u'Le serveur a eu un problème. Si ce problème persiste,'
            u' envoyez un mail au ',
            T.a(href='mailto:webmaster@mes-souhaits.net')[u'webmaster'],
            u'. Merci de votre compréhension.']
        ]

    def renderHTTP_exception(self, ctx, failure):
        """Render the error page."""
        request = IRequest(ctx)
        request.setResponseCode(http.INTERNAL_SERVER_ERROR)
        res = self.renderHTTP(ctx)
        request.finishRequest(False)
        log.err(failure)
        service = IService(ctx)
        service.build_and_send(service.ADMIN,
                               '[crash report] mes-souhaits.net',
                               str(failure))
        return res

class The404Page(BasePage):
    """Render the 404 not found error page."""

    implements(ICanHandleNotFound)

    contentTemplateFile = 'notfound.xml'

    def renderHTTP_notFound(self, ctx):
        """Render the 404 page."""
        return self.renderHTTP(ctx)
