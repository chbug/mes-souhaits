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
"""This module serves lots of pages...

(it's going to be split into submodules in souhaits.web)
"""

from nevow import loaders, inevow
from nevow.inevow import IRequest

from twisted.web import static
from twisted.python import log

from nevow import tags as T, url

from souhaits import session, TEMPLATE_DIR, STATIC_DIR, core, format
from souhaits.core import IService

from souhaits.web import arg
from souhaits.web import theme
from souhaits.web.list import NewList, NewListFragment
from souhaits.web.invite import Invite
from souhaits.web import login
from souhaits.web import widget

from souhaits.web.base import BasePage
from souhaits.web.errors import The404Page, The500Page

from souhaits.session import must_user, maybe_user, message

import os, re


def owns_list(avatar, lst):
    """Returns True iff avatar owns the list lst."""
    return (not avatar.anonymous
            and avatar.user.id == lst.owner)


def manages_list(ctx, avatar, lst):
    """Returns True iff avatar can manage list lst."""
    # pylint: disable-msg=E1101
    return (not avatar.anonymous
            and IService(ctx).managesList(avatar.user, lst))


def process_default(ctx, default):
    """Replace default arg values with the empty string."""
    args = {}
    for k in default.keys():
        v = ctx.arg(k) or ''
        v = v.strip().decode('utf-8')

        if not v or v == default[k]:
            args[k] = ''
        else:
            args[k] = v
    return args
    
# ==================================================

class About(BasePage):
    """Serves /about."""
    contentTemplateFile = 'about.xml'


class Login(BasePage):
    """Serves /login."""
    contentTemplateFile = 'login.xml'

    def data_login_info(self, ctx, _):
        """Collect all login info from the context."""
        return login.login_info_from_context(ctx)

    def render_login(self, ctx, data):
        """Render the login box."""
        return ctx.tag[login.LoginFragment(original=data)]


class Logout(BasePage):
    """Serves /logout."""
    contentTemplateFile = 'logout.xml'

    def renderHTTP(self, ctx):  # pylint: disable-msg=C0103
        """Handle HTTP requests."""
        request = IRequest(ctx)

        if request.method == 'POST':  # pylint: disable-msg=E1101
            session.destroy_session(ctx)
            request.redirect('/')
            return ''
        return BasePage.renderHTTP(self, ctx)

    
class Challenge(BasePage):
    """Serve /challenge/... pages."""

    def __init__(self, challenge):
        BasePage.__init__(self)

        self.challenge = challenge
        return

    def renderHTTP(self, ctx):
        """Handle HTTP requests."""
        srv = IService(ctx)
        request = IRequest(ctx)

        current = must_user(ctx)
        user = srv.validate_challenge(  # pylint: disable-msg=E1101
            self.challenge, current.session)

        if user:
            message(ctx, u'Bienvenue, %s' % (user.email,))
            request.redirect ("/")
            request.finish ()
            return ''

        # Some people simply reuse invitations: don't complain if they
        # are already connected, just redirect them to the main page.
        avatar = maybe_user(ctx)
        if avatar.identified:
            request.redirect("/")
            request.finish()
            return ''

        # pylint: disable-msg=E1101
        self.contentTags = [
            T.h1[u"Cette clé n'est pas valable"],
            T.p[u"Vous pouvez obtenir une nouvelle clé par e-mail.",
                T.div(_class="editable bl")[
                T.div(_class="br")[
                T.div(_class="tl")[
                T.div(_class="tr")[
                T.div(_class="edcontent")[
                    login.LoginFragment(
                        original=login.LoginInfo(force_reconnect=True))],
                ]
            ]]]]]

        return BasePage.renderHTTP(self, ctx)

# ==================================================


class ListUnsubscribe(BasePage):
    """Serve /some_list/unsubscribe."""
    contentTemplateFile = 'listunsubscribe.xml'

    def __init__(self, lst):
        BasePage.__init__(self, lst.name or 'Liste sans nom')
        self.list = lst

    def render_list_title (self, ctx, _):
        """Render the list title."""
        return ctx.tag[self.list.name or u'Liste sans titre']

    def child_confirm(self, ctx):
        """Handle the confirmation that a list is dropped."""
        srv = IService(ctx)
        avatar = must_user(ctx)
        
        srv.remove_from_friend(  # pylint: disable-msg=E1101
            avatar.user, self.list)

        message(ctx, u'Vous ne suivez plus cette liste.')
        
        return url.URL.fromString("/")
    

class ListDestroy(BasePage, widget.RoundedBoxMixin):
    """Serve /some_list/destroy."""
    contentTemplateFile = 'listdestroy.xml'

    def __init__ (self, lst):
        widget.RoundedBoxMixin.__init__(self)
        BasePage.__init__(self, lst.name or 'Liste sans nom')
        self.list = lst

    def render_list_title(self, ctx, _):
        """Render the list title."""
        return ctx.tag[self.list.name or u'Liste sans titre']

    def render_display_stats(self, ctx, _):
        """Display the number of watchers for this list."""
        srv = IService(ctx)

        t = ctx.tag
        
        r = len(srv.getListReservations(self.list))  # pylint: disable-msg=E1101
        if r:
            if r == 1:
                txt = 'une réservation'
            else:
                txt = '%d réservations' % r

            # pylint: disable-msg=E1101
            t = t[u'Il y a ', T.b[txt], u' sur cette liste.']

        return t

    def child_confirm(self, ctx):
        """Confirm that the list must be destroyed."""
        if not owns_list(must_user(ctx), self.list):
            return url.URL.fromContext (ctx).up ()

        if ctx.arg ('cancel'):
            message(ctx, u"L'opération a été annulée.")
            return url.URL.fromContext (ctx).up ()

        srv = IService(ctx)

        srv.destroyList (self.list)  # pylint: disable-msg=E1101
        
        message(ctx, u'Votre liste a bien été détruite.')
        
        return url.URL.fromString ("/")
    

class ListDescription(BasePage, widget.RoundedBoxMixin):
    """ Edit the parameters of a list """

    contentTemplateFile = 'listdescription.xml'

    defaultValues = {
        'listTitle': '',
        'listDesc': (u'Donnez une description de cette liste '
                     u'(anniversaire, Noël,...)'),
        'listUrl': '',
        'showRes': '',
        'coEditors': '',
        'theme': ''
        }

    def __init__ (self, lst):
        widget.RoundedBoxMixin.__init__(self)
        BasePage.__init__(self, lst.name or 'Liste sans nom')
        self.list = lst

    def theme(self):
        """Return the current theme."""
        return self.list.theme

    def render_listThemes(self, ctx, _):
        """Render the list of all themes."""
        all_themes = theme.themes.values()
        all_themes.sort(key=lambda t: t.name)

        results = []
        for a_theme in all_themes:
            # pylint: disable-msg=E1101
            field = T.input(type="radio", name="theme", value=a_theme.key)[
                u'\xa0' + a_theme.name]
            if a_theme == self.theme():
                field(checked="yes")
            results.append([field, T.br])
        return ctx.tag[results]
    
    def render_listTitle(self, ctx, _):
        """Render the list title."""
        return ctx.tag(value=self.list.name)

    def render_listDesc(self, ctx, _):
        """Render the list description."""
        return ctx.tag[
            self.list.desc or self.defaultValues['listDesc']
            ]

    def render_showRes(self, ctx, _):
        """Render the 'show reserved' checkbox."""
        if self.list.showres:
            return ctx.tag(checked=repr(self.list.showres))
        else:
            return ctx.tag

    def render_coEditors(self, ctx, _):
        """Render the list of co-editors."""
        # pylint: disable-msg=E1101
        coeds = IService(ctx).getCoEditors(self.list)

        return ctx.tag['\n'.join([u.email for u in coeds])]

    
    def render_listUrl(self, ctx, _):
        """Render the list's URL."""
        return ctx.tag(value=self.list.url)

    _coedsplit = re.compile(r'[ ,\n]+')

    def child_change(self, ctx):
        """Handle modification requests."""
        if not manages_list(ctx, must_user(ctx), self.list):
            message(ctx, u"Vous n'avez pas le droit de modifier cet objet.")
            return url.URL.fromContext (ctx).up ()

        if ctx.arg('cancel'):
            message(ctx, u'Les modifications ont été annulées.')
            return url.URL.fromContext (ctx).up()

        args = process_default(ctx, self.defaultValues)

        success = True
        updates = {'description': args['listDesc']}
        
        if not args['listTitle']:
            message(ctx, u'Il faut donner un titre à la liste.')
            success = False
        else:
            updates['title'] = args['listTitle']

        proposed = args['listUrl']

        if not proposed:
            message(ctx, u'Il faut donner une URL à la liste.')
            success = False
        else:
            # We only update the url if it actually changed !
            if proposed != self.list.url:
                updates['url'] = proposed
            else:
                proposed = None

        if args['showRes']:
            updates['showres'] = 1
        else:
            updates['showres'] = 0

        if (args['theme'] in theme.themes and
            self.theme().key != args['theme']):
            updates['theme_id'] = args['theme']

        srv = IService(ctx)

        # pylint: disable-msg=E1101
        current_coeds = srv.getCoEditors(self.list)

        # coEditors
        coeds = args['coEditors'].strip()

        if coeds:
            new_coeds = [x.strip() for x in
                         self._coedsplit.split(coeds)]

            if new_coeds != current_coeds:
                updates['coEditors'] = new_coeds

        # pylint: disable-msg=E1101
        new, unknown = srv.updateList(self.list, **updates) or self.list.url

        if unknown:
            missed = u', '.join(unknown)
            message(ctx, u"Les personnes suivantes ne sont pas connues\xa0: "
                    + missed)
            
            return url.URL.fromString('/').child(new).child('edit')
        
        if proposed and new != proposed:
            # We could not get the proposed URL, simply warn the user
            # pylint: disable-msg=E1101
            message(
                ctx,
                T.div[u"L'URL ", T.tt [
                '<http://mes-souhaits.net/' + proposed + '>'],
                " étant indisponible, ", T.tt[
                '<http://mes-souhaits.net/' + new + '>'],
                " a été utilisée à la place." ])
            
        if success:
            message(ctx, u'Les modifications ont été effectuées.')
            return url.URL.fromString('/').child(new)

        return url.URL.fromString('/').child(new).child('edit')

        

class ListBase(BasePage):
    """Base class for list-related pages."""

    defaultValues = {
        'title': u'Description brève',
        'description': u'Description plus détaillée',
        'url': u'http://...',
        'score': '2'
        }

    def theme(self):
        """Return the current theme."""
        return self.list.theme  # pylint: disable-msg=E1101

    def render_themeCss(self, ctx, _):
        """Render the theme-specific CSS link."""
        return ctx.tag(href="/themes/%s/screen.css" % self.theme().key)

    def _make_score(self, score):
        """Generate the stars corresponding to a score of 'score'."""
        score_code = []
        for value in (1, 2, 3):
            # pylint: disable-msg=E1101
            if value > score:
                score_code.append(T.img(src="/images/star-off.png"))
            else:
                score_code.append(T.img(src="/images/star-on.png"))
        return score_code

    def render_fullList(self, ctx, data):
        """Render all the info for a list entry."""
        # pylint: disable-msg=E1101
        title = data.title or T.em[u'(Pas de titre)']

        if data.res:
            if data.res:
                owner, _, email = data.res
                if owner:
                    if email:
                        res = u'Réservé par ' + email
                    else:
                        res = u'Réservé'
                else:
                    res = u'Réservé'
            img = self.theme().render_Lock(ctx, res)
        else:
            img = ''

        score = self._make_score(data.score)

        # pylint: disable-msg=E1101
        if data.url:
            link = data.url
            if len(link) > 50:
                link = link[:50] + '...'
            link = T.div(style="padding-top: 1ex")[
                u'» Voir\xa0: ', T.a (href=data.url, target='_blank')[link]]
        else:
            link = ''

        if data.description:
            desc = format.format_description(data.description)
        else:
            desc = T.em[u'(pas de description)']
            
        return ctx.tag[T.h2[img, title,
                            T.span(style="padding-left:1ex")[score]],
                       T.div(_class="itemdesc")[desc, link]]


class ListItemDonated(BasePage):
    """ Confirm that a wish has been given to its recipient. """
    
    contentTemplateFile = 'listitemdonated.xml'

    def __init__ (self, lst, item):
        if item.title:
            title = u'« %s » a été donné' % item.title
        else:
            title = u'Le cadeau a été donné'
        BasePage.__init__(self, title)
        self.list = lst
        self.item = item
        return

    def render_itemName(self, ctx, _):
        """Render the item's name."""
        return ctx.tag [ self.item.title or u'Cadeau sans nom' ]

    def render_owner(self, ctx, _):
        """Render the list owner's name."""
        srv = IService(ctx)
        user = srv.getUserByKey(self.list.owner)  # pylint: disable-msg=E1101
        return ctx.tag[user.email]

    def child_confirm(self, ctx):
        """Confirm that an item has been donated."""
        srv = IService(ctx)
        avatar = must_user(ctx)
        if not avatar.identified:
            message(ctx, u"Vous devez confirmer votre email d'abord.")
            return url.URL.fromContext(ctx).up().up()

        srv.donatedItem(avatar.user, self.item)  # pylint: disable-msg=E1101
        message(ctx, u"Votre modification est enregistrée.")
        return url.URL.fromContext(ctx).up().up()


class ListItem(ListBase, widget.RoundedBoxMixin):
    """ Display a single list item """

    contentTemplateFile = 'listitem.xml'

    def __init__(self, lst, item):
        widget.RoundedBoxMixin.__init__(self)
        ListBase.__init__ (self, item.title or '(Pas de titre)')

        self.list = lst
        self.item = item
        return

    def child_donated(self, _):
        """Handle /some_list/some_item/donated."""
        return ListItemDonated(self.list, self.item)

    def data_item(self, ctx, data):  # pylint: disable-msg=W0613
        """Return the corresponding item."""
        return self.item

    def render_maybeEdit(self, ctx, _):
        """Render the edit buttons if the item can be edited."""
        if manages_list(ctx, must_user(ctx), self.list):

            # pylint: disable-msg=E1101
            def _make_option(value, comment):
                """Build on choice of a score."""
                if value == self.item.score:
                    checked = 'yes'
                else:
                    checked = None
                return T.li[T.input(type="radio", name="score",
                                    value=str(value), checked=checked)[
                  T.span(style="padding-right:1ex")[
                    self._make_score(value)], comment]],

            scores = T.ul[
                _make_option(1, u'Pourquoi pas...'),
                _make_option(2, u'Chouette\xa0!'),
                _make_option(3, u'Oh oui, Oh oui\xa0!')]
            
            return ctx.tag(_class="editable", render=self.render_rounded_box)[
                T.form(name='edit', action=url.here.child('edit'),
                       method='POST')[
                T.input (type='text', name='title', _class='inputfield',
                         value=self.item.title or self.defaultValues['title']),
                T.br,
                T.textarea(name='description', _class='inputfield', rows='5')[
                self.item.description or self.defaultValues['description']],
                T.br,
                T.input(type='text', name='url', _class='inputfield',
                        value=self.item.url or self.defaultValues['url']),
                scores,
                T.input(type='submit', name='edit',
                        value=u'Enregistrer les modifications'),
                T.input(type='submit', name='cancel', value=u'Annuler'),
                ]]
        else:
            return ''

    def child_edit(self, ctx):
        """Handle edit requests."""
        if not manages_list(ctx, must_user(ctx), self.list):
            message(ctx, u"Vous n'avez pas le droit de modifier cet objet.")
            return url.URL.fromContext (ctx).up ()

        if ctx.arg ('cancel'):
            message(ctx, u'La modification a été annulée.')
            return url.URL.fromContext (ctx).up ()

        args = process_default(ctx, self.defaultValues)
        
        if not (args ['title'] or args ['description'] or
                args ['url'] or args['score']):
            return url.URL.fromContext(ctx)

        try:
            score = int(args['score'])
            if score > 3 or score < 1:
                raise ValueError
        except ValueError:
            score = 2
            
        srv = IService(ctx)
        srv.editItem(self.item,  # pylint: disable-msg=E1101
                     args['title'],
                     args['description'],
                     args['url'],
                     score)
        
        message(ctx, u'Votre souhait a bien été modifié.')
        
        return url.URL.fromContext (ctx).up ()

    def child_delete(self, _):
        """Render delete requests."""
        return DelItem(self.list, self.item)

    def child_get(self, ctx):
        """Handle reservation requests."""
        avatar = must_user(ctx)

        if owns_list(avatar, self.list):
            message(ctx, u"Vous ne pouvez pas réserver un de vos souhaits.")
            return url.URL.fromContext(ctx).up()

        # In any case, the item is reserved. It is up to the user to
        # possibly confirm his identity.
        if not avatar.anonymous:
            srv = IService(ctx)
            # pylint: disable-msg=E1101
            srv.reserveItem(avatar.user, self.item)
            message(ctx, u'Votre réservation est enregistrée.')
            return url.URL.fromContext(ctx).up()
        
        message(ctx, u'Votre réservation sera effective lorsque '
                u'vous vous serez identifié.')
        # redirect here after authentication
        referer = url.URL.fromContext(ctx).child('get')
        return url.URL.fromString('/login').add(name='referer', value=referer)

    def child_giveup(self, ctx):
        """Handle reservation cancellation requests."""
        srv = IService(ctx)
        user = must_user(ctx).user

        if ctx.arg('giveup'):
            srv.giveupItem(user, self.item)  # pylint: disable-msg=E1101
            message(ctx, u"Votre modification est enregistrée.")

        request = IRequest(ctx)
        referer = request.getHeader('referer')
        if referer:
            return url.URL.fromString(referer)
        return url.URL.fromContext(ctx).up()


class DelItem(ListBase):
    """Serves /some_list/some_item/delete."""
    contentTemplateFile = 'listitem.xml'

    def __init__(self, lst, item):
        ListBase.__init__(self, item.title or '(Pas de titre)')

        self.list = lst
        self.item = item
        return

    def data_item(self, ctx, data):  # pylint: disable-msg=W0613
        """Return the item."""
        return self.item

    def render_fullList(self, ctx, data):
        """Render details of a single item."""
        tag = ListBase.render_fullList(self, ctx, data)

        srv = IService(ctx)

        # pylint: disable-msg=E1101
        if srv.isReserved(self.item):
            msg = u"""Ce souhait est déjà réservé par
            quelqu'un. Êtes-vous sûr de vouloir le supprimer\xa0?"""
        else:
            msg = u"""Vous êtes sur le point d'effacer un
            souhait. Cette opération est irréversible."""

        return T.div[
            T.table[T.tr[T.td[
            T.img (src = "/images/logo-danger.png", width = "35", height = "41",
                   style="margin-right: 1em", alt = "Attention"),
            ], T.td(valign="center")[msg]]],
            tag]
            
        
    def render_maybeEdit(self, ctx, _):
        """Render action buttons if available."""
        # pylint: disable-msg=E1101
        if manages_list(ctx, must_user(ctx), self.list):
            srv = IService(ctx)
            if srv.isReserved(self.item):
                notify = T.p[
                    T.input(type="checkbox",
                            name="notify",
                            value="1",
                            checked=""),
                    u"\xa0Avertir la personne qui l'a réservé"]
            else:
                notify = []
            return ctx.tag (_class="editable bl")[
                T.div(_class="br")[
                T.div(_class="tl")[
                T.div(_class="tr")[
                T.form(name='confirm', action=url.here.child('confirm'),
                       method='POST', _class="edcontent")[
                notify,
                T.input(type='submit', name='confirm',
                        value=u"Confirmer l'effacement"),
                T.input(type='submit', name='cancel',
                        value=u"Annuler"),
                ]]]]]
        else:
            return ''


    def child_confirm (self, ctx):
        """Handle .../confirm."""
        if not manages_list(ctx, must_user(ctx), self.list):
            message(ctx, u"Vous n'avez pas le droit de modifier cet objet.")
            return url.URL.fromContext (ctx).up ().up ()

        if ctx.arg ('cancel'):
            message(ctx, u"L'effacement a été annulé.")
            return url.URL.fromContext (ctx).up ().up ()

        srv = IService(ctx)
        # pylint: disable-msg=E1101
        srv.deleteItem(self.item, ctx.arg('notify'))
        message(ctx, u'Votre souhait a bien été supprimé.')
        return url.URL.fromContext (ctx).up ().up ()


class List(ListBase):

    """ Display of a wish list """

    contentTemplateFile = 'list.xml'

    def __init__(self, lst):
        ListBase.__init__(self, lst.name or 'Liste sans nom')

        self.list = lst

    def beforeRender(self, ctx):
        """Called before the page is actually rendered."""
        # If we are connected, we can put this list in our "friends" list
        avatar = maybe_user(ctx)
        if not avatar.identified or owns_list(avatar, self.list):
            return
        # pylint: disable-msg=E1101
        IService(ctx).addToFriend(avatar.user, self.list)
    
    def render_listname(self, ctx, _):
        """Render the name of the list."""
        return self.theme().render_ListTitle(
            ctx, self.list.name or 'Liste sans nom')

    def render_listDesc(self, ctx, _):
        """Render the list's description."""
        avatar = maybe_user(ctx)
        editable = manages_list(ctx, avatar, self.list)

        # pylint: disable-msg=E1101
        desc = self.list.desc or T.em['(pas de description)']

        if editable:
            invite = url.URL.fromString("/invite")
            invite = invite.add('lst', str(self.list.id))

            srv = IService(ctx)
            name = self.list.name or 'ma liste'

            action = """
            url=encodeURIComponent(location.href);location.href='%s?url='+url+'&title='+encodeURIComponent(document.title)+'&back='+url
            """ % (srv.base_url + '/' + self.list.url)
            action = re.sub('\s+', ' ', action.strip())
            desc = [desc,
                    T.div(_class="listaction")[
                u'» ',
                T.b[T.a(href=invite)[u'Inviter']],
                ' :: ',
                T.a(href=url.here.child('edit'))[u'Modifier'],
                ' :: ',
                T.a(href=url.here.child('destroy'))[u'Détruire'],
                ],
                    T.div(_class="listaction")[
                T.em[u'Glisse moi dans tes bookmarks\xa0! '],
                    T.a(href='javascript:'+action)[u'» %s' % name]]
                ]
        elif avatar.identified:
            desc = [desc,
                    T.div(_class="listaction")[
                u'» ', T.a(href=url.here.child('unsubscribe'))[u'Ignorer'],]]
            
        return ctx.tag[desc]


    def data_listContent(self, ctx, _):
        """Return the list's content (ie the items)."""
        avatar = maybe_user(ctx)
        editable = manages_list(ctx, avatar, self.list)

        needs_reservation = not editable or self.list.showres

        srv = IService(ctx)

        # pylint: disable-msg=E1101
        items = srv.itemsForList(self.list, needs_reservation)

        # The list admin needs to see all the items, for other users,
        # discard items reserved by someone else
        if not editable:
            # Simple users have the "reserved" tag, but cannot see by
            # whom
            if avatar.anonymous:
                user = None
            else:
                user = avatar.user.id
                
            items = [ item for item in items if
                      item.res is None or item.res [0] == user ]

            # discard the info about who reserved
            for i in items:
                if i.res:
                    i.res = (i.res [0], i.res [1], None)
        return items

    def render_possibleActions (self, ctx, data):
        """Render the buttons under am item."""
        # pylint: disable-msg=E1101
        avatar = maybe_user(ctx)
        if manages_list(ctx, avatar, self.list):
            child = url.here.child(str(data.key))

            modify = T.div(_class="listaction")[
                u'» ',  T.a(href=child)[u'Modifier'],
                ' :: ', T.a(href=child.child('delete'))[u'Effacer']]
                                   
        else:
            if not data.res:
                # the object is not yet reserved, so it can be for us
                k = str (data.key)
                modify = T.form (action=url.here.child (k).child('get'),
                                 id='item-' + k, _class='item-op',
                                 method='POST')[
                    T.input(type='submit',
                            name='get',
                            value=u'Réserver cette idée')]
            else:
                if avatar.anonymous:
                    user = None
                else:
                    user = avatar.user.id
                    
                if data.res [0] == user:
                    k = str (data.key)
                    donated = T.a(
                        href=url.here.child(k).child('donated'),
                        style="margin-left:2em")[
                        u"»\xa0Vous avez donné le cadeau\xa0?"]
                    modify = T.form(action=url.here.child(k).child('giveup'),
                                    id='item-' + k, _class='item-op',
                                    method='POST')[
                        T.input(type='submit',
                                name='giveup',
                                value=u'Abandonner cette idée'),
                        donated]
                else:
                    modify = ''

        return ctx.tag [ modify ]

    def render_maybeAdd (self, ctx, _):
        """Render the 'new item' form if the user can change the list."""
        avatar = maybe_user(ctx)

        if manages_list(ctx, avatar, self.list):
            req = IRequest(ctx)
            if ctx.arg('back'):
                back = u'Ajouter ce souhait et revenir au site précédent'
            else:
                back = u'Ajouter ce souhait'
            # pylint: disable-msg=E1101
            return T.div(_class="editable bl")[
                T.div(_class="br")[
                T.div(_class="tl")[
                T.div(_class="tr")[
                T.div(_class="edcontent")[
                u'Ajouter un souhait\xa0:',
                T.form(name='add', action=url.here.child('add'),
                        method='POST', _class="edititem")[
                T.input(type='text', name='title', _class='inputfield',
                        value=arg(req, 'title', self.defaultValues['title'])),
                T.br,
                T.textarea(name='description', _class='inputfield', rows='5')[
                self.defaultValues ['description'] ],
                T.br,
                T.input(type='text', name='url', _class='inputfield',
                        value=arg(req, 'url', self.defaultValues['url'])),
                T.br,
                T.input(type='hidden', name='back',
                        value=arg(req, 'back', '')),
                T.input(type='submit', name='add', value=back)
                ]]]]]]
        else:
            return ''

    def child_edit (self, _):
        """Handle the .../edit page."""
        return ListDescription(self.list)

    def child_unsubscribe (self, _):
        """Handle the .../unsubscribe page."""
        return ListUnsubscribe(self.list)

    def child_destroy(self, _):
        """Handle the .../destroy page."""
        return ListDestroy(self.list)

    def child_add(self, ctx):
        """Handle the .../add page."""
        avatar = must_user(ctx)
        
        if not manages_list(ctx, avatar, self.list):
            log.msg ('unauthorized access to the list/add method')
            return url.URL.fromContext (ctx)

        args = {}
        for k in self.defaultValues.keys ():
            v = ctx.arg (k) or ''
            v = v.strip ().decode ('utf-8')

            if not v or \
                   v == self.defaultValues[k]:
                args [k] = ''
            else:
                args [k] = v
        
        if not (args ['title'] or args ['description'] or args ['url']):
            return url.URL.fromContext (ctx)

        srv = IService(ctx)
        srv.addNewItem(self.list, args['title'],  # pylint: disable-msg=E1101
                       args['description'], args['url'])
        message(ctx, u'Votre souhait a bien été enregistré.')

        back = ctx.arg('back')
        if back:
            back = url.URL.fromString(back)
        else:
            back = url.URL.fromContext(ctx)
        return back

    def childFactory (self, ctx, name):
        """Handle all the others sub pages (ie, the items)."""
        srv = IService(ctx)

        wl = srv.getListItem (self.list, name)  # pylint: disable-msg=E1101
        
        if wl:
            return ListItem(self.list, wl)
        
        return None
        
        
# ==================================================

class RootPage(ListBase, widget.RoundedBoxMixin):

    """ Root page of the site """

    addSlash = True
    
    contentTemplateFile = 'welcome.xml'

    def __init__(self, srv):
        ListBase.__init__ (self)
        widget.RoundedBoxMixin.__init__(self)

        self.remember(srv, core.IService)

    def theme(self):
        """Return the current theme."""
        return theme.themes['default']

    def render_login(self, ctx, _):
        """Render the login box."""
        info = login.LoginInfo(warnings=False, force_reconnect=True)
        return ctx.tag[login.LoginFragment(original=info)]

    def render_content(self, ctx, _):
        """Render the body of the main page."""
        avatar = maybe_user(ctx)

        if avatar.identified:
            tmpl = 'welcome_again.xml'
        elif avatar.pending:
            tmpl = 'welcome_pending.xml'
        else:
            tmpl = 'welcome.xml'
        
        return loaders.xmlfile (templateDir=TEMPLATE_DIR,
                                template=tmpl)

    def render_newUser(self, ctx, _):
        """Render the 'I'm a new user' fragment."""
        if maybe_user(ctx).pending:
            return ''
        return ctx.tag

    def render_newlistform(self, ctx, data):
        """Render the 'create new list' form."""
        return ctx.tag[NewListFragment(data)]

    def data_listResa(self, ctx, _):
        """Return the user's reservations."""
        user = maybe_user(ctx).user
        srv = IService(ctx)

        # pylint: disable-msg=E1101
        items = [item for item in srv.getUserReservations(user)
                 if item.res[1] == 'R']

        for i in items:
            i.res = (i.res [0], i.res [1], None)

        return items
    
    def render_emailValue(self, ctx, _):
        """Render the 'email' field."""
        srv = IService(ctx)
        user = maybe_user(ctx).user
        
        email = srv.pretendedEmail(user)  # pylint: disable-msg=E1101

        return ctx.tag(value=email)

    def render_infoLists (self, ctx, data):
        """Render some info about the lists followed."""
        if data:
            return ctx.tag [u'''Vous suivez les listes suivantes\xa0:''']
        else:
            return ctx.tag [u'''Vous ne suivez aucune liste pour le moment.''']
        
    def render_infoResa(self, ctx, data):
        """Render some info about reservations."""
        if data:
            return ctx.tag[
                u"""Si vous ne voulez plus d'une idée, n'oubliez pas
                de cliquer sur """,
                T.em[u'Abandonner cette idée'],  # pylint: disable-msg=E1101
                u""" pour qu'une autre personne puisse la prendre à
                votre place."""
                ]
        else:
            return ctx.tag[u"""Vous n'avez pas de réservations
            pour le moment.""" ]
    
    def render_possibleActions(self, ctx, data):
        """Render the buttons with the possible actions."""
        # pylint: disable-msg=E1101
        srv = IService(ctx)
        lst = srv.getListByKey(data.list)
        
        action = url.here.child(lst.url).child(data.key)

        donated = T.a(href=action.child('donated'),
                      style="margin-left:2em")[
            u"»\xa0Vous avez donné le cadeau\xa0?"]
        
        modify = T.form(action=action.child('giveup'),
                        name='giveup',
                        _class='item-op',
                        method='POST')[
            T.input(type='submit',
                    name='giveup',
                    value=u'Abandonner cette idée'),
            donated]
        
        return ctx.tag [ modify ]

        
    def childFactory (self, ctx, name):
        """Serve specific lists."""
        srv = IService(ctx)
        name = name.decode('utf-8')
        
        # pylint: disable-msg=E1101
        wl = srv.getListByURL(name)
        if wl:
            return List(wl)

        # Be nice to the user: if he introduced capitals or other
        # symbols, try with the normalized form too.
        norm = core.normalize_url(name)

        if norm != name:
            wl = srv.getListByURL(norm)
            if wl:
                return url.URL.fromContext(ctx).sibling(wl.url)
            
        return None
    
    def locateChild(self, ctx, segments):
        """Handle the URL hierarchy at the root point."""
        ctx.remember (The404Page(), inevow.ICanHandleNotFound)
        ctx.remember (The500Page(), inevow.ICanHandleException)
        
        if segments [0] == 'challenge' and len (segments) == 2:
            return Challenge(segments [1]), []

        return BasePage.locateChild(self, ctx, segments)
    
    child_newlist = NewList()
    child_logout = Logout()
    child_login  = Login()
    child_invite = Invite()
    child_about  = About()
    child_css    = static.File(os.path.join(STATIC_DIR, 'css'))
    child_images = static.File(os.path.join(STATIC_DIR, 'images'))
    child_js     = static.File(os.path.join(STATIC_DIR, 'js'))
    child_themes = static.File(os.path.join(STATIC_DIR, 'themes'))

