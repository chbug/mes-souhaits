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
"""Implementation of the base page.

This page is inherited by all the others.
"""

from nevow import rend, loaders
from nevow.inevow import ISession, IRequest

from nevow import tags as T, stan

from souhaits import TEMPLATE_DIR
from souhaits.core import IService
from souhaits.web import login
from souhaits.web import theme

from souhaits.session import maybe_user


class BasePage(rend.Page):
    """ Base class inherited by all the actual pages of the site """

    docFactory = loaders.xmlfile(templateDir=TEMPLATE_DIR,
                                 template='site.xml')

    contentTemplateFile = None
    contentTags         = ''
    
    title = None

    # pylint: disable-msg=W0613,E1101

    def __init__(self, title=None):
        rend.Page.__init__(self)
        if title:
            self.title = title

    def theme(self):
        """Return the default page theme."""
        return theme.themes['default']

    def render_theme_css(self, ctx, data):
        """Render the CSS for the current theme."""
        return []

    def render_raw_header(self, ctx, data):
        """Render the top raw header."""
        return stan.raw ('''\
<!--[if gte IE 5.5000]>
  <script type="text/javascript" src="/js/pngfix.js"></script>
<![endif]-->''')

    def render_title(self, ctx, data):
        """Render the page title."""
        title = 'Mes souhaits'
        if self.title:
            title = self.title + ' - ' + title
        
        return ctx.tag [ title ]

    def render_content(self, ctx, data):
        """Render the page content."""
        tag = ctx.tag.clear()
        
        if self.contentTemplateFile:
            return tag[loaders.xmlfile(templateDir=TEMPLATE_DIR,
                                       template=self.contentTemplateFile)]
        else:
            return tag[self.contentTags]

    def render_listbox(self, ctx, data):
        """Render the box with the list of wishlists."""
        user = maybe_user(ctx)

        if not user.anonymous:
            tag = ctx.tag.clear()
            return tag[loaders.xmlfile(templateDir=TEMPLATE_DIR,
                                       template='listbox.xml') ]
        else:
            return ctx.tag[T.em[u"Vous n'êtes pas connecté"]]

    def render_your_account(self, ctx, data):
        """Render a message about the lists owned by the user."""
        if not data:
            return T.i[u"Vous n'avez pas de liste."]
        return ''
    
    def render_listitem(self, ctx, data):
        """Render a single list in the list box."""
        data, highlight = data

        uri = IRequest(ctx).uri
        target = "/" + data.url

        if highlight:
            new = T.img(src="/images/newitem.png", alt="",
                        title="Nouveautés")
            content = T.b [new, u'\xa0', data.name]
        else:
            content = data.name
        
        if uri == target:
            content = u"» " + data.name
        else:
            content = T.a(href=target)[content]
            
        ctx.fillSlots ('list', content)
        return ctx.tag
        
    def data_my_lists(self, ctx, data):
        """Returned the list of the wishlists owned by the user."""
        return IService(ctx).getListsOwnedBy(maybe_user(ctx).user)
    
    def data_friend_lists(self, ctx, data):
        """Returned the list of the wishlists watched by the user."""
        return IService(ctx).getFriendLists(maybe_user(ctx).user)
    
    def render_userbox(self, ctx, data):
        """Render the box containing the user's login status."""
        avatar = maybe_user(ctx)
        srv = IService(ctx)

        warn = ''
        
        if avatar.anonymous:
            email = None
        else:
            email = avatar.user.email
            if not email:
                email = srv.pretendedEmail(avatar.user)
                warn = T.span(id="activate")[u"Vous devez encore ",
                    T.a(href="/")[u"activer votre compte"]]
                
        if email:
            greetings = T.div(_class="userinfo")[
                warn, T.span(style="padding-right:3em")[email],
                T.a(href="/")[u"Réservations"],
                u' :: ', T.a(href="/logout")[u"Quitter"],
                ]

        else:
            info = login.LoginInfo(warnings=False, force_reconnect=True)
            greetings = T.div(_class="userinfo")[
                login.LoginFragment(original=info)]
        
        return ctx.tag[T.a(href="/")[T.img(src="/images/mes-souhaits.png",
                                           align="left", alt="Mes souhaits",
                                           width=203, height=36)],
                       greetings]


    def render_message(self, ctx, data):
        """Render the pending user messages."""
        session = ISession(ctx)

        pending = getattr(session, 'message', [])

        if not pending:
            return ''
            
        msg = []
        for text in pending:
            msg.append(text)
            msg.append(T.br)

        session.message = []
            
        return ctx.tag[msg]
