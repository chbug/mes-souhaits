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
"""Handles new list creation fragment and page."""

from nevow import rend, tags as T, loaders
from nevow.inevow import IRequest

from souhaits.session import must_user, maybe_user, message
from souhaits.core import IService, validate_email

from souhaits.web import base
from souhaits.web import arg
from souhaits.web import widget


class NewListFragment(rend.Fragment, widget.RoundedBoxMixin):
    """Render a 'new list' page fragment."""

    def _create_list(self, ctx, name, email):
        """Actually create the new list."""
        req = IRequest(ctx)
        srv = IService(ctx)

        avatar = must_user(ctx)
        # pylint: disable-msg=E1101
        wl = srv.createList(avatar.user, name, email)
        if not wl:
            req.redirect('/')
            req.finish()
            return

        if not avatar.identified:
            message(ctx, u"Un message de confirmation a été envoyé"
                    u" à l'adresse <%s>." % (email,))

        req.redirect('/' + wl.url)
        req.finish()

    def render_form(self, ctx, _):
        """Render the 'new list' form."""
        req  = IRequest(ctx)
        avatar = maybe_user(ctx)

        warnings = []

        # pylint: disable-msg=E1101
        if req.method == 'POST':
            name = arg(req, 'list')
            if not name:
                warnings.append(u"Vous n'avez pas donné de nom à la liste.")

            if avatar.identified:
                email = avatar.user.email
                clean_email = email
            else:
                email = arg(req, 'email')
                if not email:
                    warnings.append(u"Vous n'avez pas donné d'adresse email.")

                clean_email = validate_email(email)
                if not clean_email:
                    warnings.append(u"Votre adresse email est invalide.")
                    
            if name and clean_email:
                self._create_list(ctx, name, clean_email)
                return ''
        else:
            name = ''
            email = ''

        if avatar.identified:
            email_form = ''

        else:
            email_form = T.tr[T.td[T.b[u'Votre adresse e-mail\xa0:']],
                              T.td[T.input(type="text", name="email",
                                           id="listemail", value=email)],
                              T.td[T.em[u'\xa0(elle est utilisée pour vous'
                                        ' identifier sur ce site)']]],

        if warnings:
            warnings = T.div(_class="warning")[' '.join(warnings)]
        
        return ctx.tag(_class="editable", render=self.render_rounded_box)[
            warnings,
            
            T.form(style="padding: 1ex", name="newlist",
                   action="/newlist", method="POST") [
            T.table[ 
              T.tr[T.td[T.b[u'Nom de la liste\xa0: ']],
                   T.td[T.input(type="text", id="listname",
                                name="list",  value=name)],
                   T.td[u'\xa0(par exemple\xa0: ',
                        T.em[u'Le Noël de Pierre'], u')']],
              email_form,
            ],
            T.input(type="submit", value=u'Créer cette liste',
                    style= 'margin-top: 0.5ex')
            ]]

        
    docFactory = loaders.stan(
        T.invisible(render=render_form)
    )


class NewList(base.BasePage):
    """ Creation of a new wish list """

    # pylint: disable-msg=E1101
    contentTags = T.invisible[
        T.h1[u'''Créer une nouvelle liste'''], NewListFragment()]
    
    title = u'Créer une liste'
    
