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
"""Handle the invitation page."""

from nevow import tags as T
from nevow.inevow import IRequest

from souhaits.session import must_user, maybe_user
from souhaits.core import IService

from souhaits.web.base import BasePage
from souhaits.web import arg
from souhaits.web import widget


def _my_lists(lsts, srv, user):
    """Return all the lists this user has acccess to."""
    all_lsts = srv.getListsOwnedBy(user)
    all_lsts += srv.getFriendLists(user)
    all_ids = set(lst.id for lst, _ in all_lsts)

    r = []
    for lid in lsts:
        try:
            lst = srv.getListByKey(int(lid))
        except ValueError:
            continue

        if not lst:
            continue

        if lst.id in all_ids:
            r.append(lst)
    return r
    

class Invite(BasePage, widget.RoundedBoxMixin):
    """Handle the /invite page."""

    contentTemplateFile = 'listinvite.xml'
    
    def __init__(self):
        BasePage.__init__(self, 'Envoyer des invitations')
        widget.RoundedBoxMixin.__init__(self)

    _defaults = {
                'lst': [],
                'warn': [],
                'msg': '',
                'email': '',
                'sender': '',
                'body': u'''\
Voilà ma liste de souhaits ! Pour la consulter, il suffit de suivre le
lien ci-dessous. Et si une idée te plaît, tu peux la réserver en
cliquant sur « Réserver ce souhait ».
'''
                }

    def data_form(self, ctx, _):
        """Return the options passed in the invitation form."""
        req = IRequest(ctx)

        warn = []
        vals = {'msg': ''}

        srv = IService(ctx)
        avatar = must_user(ctx)
        
        user = avatar.user
        # pylint: disable-msg=E1101
        if req.method == 'POST':

            if not arg(req, 'send'):
                req.redirect('/')
                req.finish()
                return self._defaults

            if not avatar.identified:
                warn.append(u"Vous n'avez pas encore activé votre compte.")
                
            vals['sender'] = arg(req, 'sender')
            if not vals['sender']:
                warn.append(u"Vous n'avez pas précisé votre nom.")

            vals['email'] = arg(req, 'email')
            if not vals['email']:
                warn.append(u"Vous n'avez pas précisé de destinataire.")

            vals['body'] = arg(req, 'body')
            if not vals['body']:
                warn.append(u"Votre message n'a pas de contenu.")


            # We simply filter out lists that don't belong to the
            # user.
            vals['lst'] = _my_lists(req.args.get('lst', []),
                                    srv, user)
                
            if not vals['lst']:
                warn.append(u"Choisissez au moins une liste ci-dessous.")

            vals['warn'] = warn

            if not warn:
                if not srv.inviteFriend(vals['sender'], user, vals['lst'],
                                        vals['email'], vals['body']):
                    warn.append(u"L'adresse <%s> n'est pas valide." % (
                        vals['email'],))

                else:
                    vals['msg'] = u'Votre invitation a été envoyée à %s' % (
                        vals['email'],)

                    # When we have sent properly, forget the previous
                    # emails, so we don't double-send by mistake.
                    vals['email'] = ''

        else:
            vals = self._defaults

            vals['lst'] = _my_lists(req.args.get('lst', []),
                                    srv, user)
        return vals
            
    def render_email(self, ctx, data):
        """Render the 'email' field'."""
        return ctx.tag(value=data['email'])
    
    def render_sender(self, ctx, data):
        """Render the 'sender' field."""
        return ctx.tag(value=data['sender'])
    
    def render_body(self, ctx, data):
        """Render the invitation body."""
        return ctx.tag[data['body']]

    def render_info(self, ctx, data):
        """Render any error or warning messages."""
        content = []
        # pylint: disable-msg=E1101        
        if data['msg']:
            content.append(T.div(_class="message")[data['msg']])

        if data['warn']:
            li = [T.li[msg] for msg in data['warn']]
            content.append(T.div(_class="warning")[
                T.p[u"L'invitation n'est pas partie\xa0:", T.ul[li]]])
            
        return ctx.tag[content]

    def render_myLists(self, ctx, data):
        """Render the 'sender' field."""
        selected = {}
        for l in data['lst']:
            selected[l.id] = True
        # pylint: disable-msg=E1101
        srv = IService(ctx)
        user = must_user(ctx).user
        lsts = srv.getListsOwnedBy(user)
        lsts += srv.getFriendLists(user)
                 
        checkbox = []

        for lst, _ in lsts:
            name = lst.name or T.i[u'Liste sans nom']

            args = {
                'type':"checkbox",
                'name':"lst",
                'value': lst.id
                }
            
            if lst.id in selected:
                args['checked'] = '1'

            checkbox.append(T.div(style="margin-left:2em")[
                T.input(**args)[u'\xa0' + name]])
            
        return ctx.tag[checkbox]


