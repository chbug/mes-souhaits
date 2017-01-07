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
"""Theme handling."""

from nevow import tags as T
from souhaits.web import widget


class Theme(object):
    """Base class for UI themes."""
    name = None
    key = None

    def __eq__(self, other):
        """Check the equivalence between 2 themes."""
        return self.key == other.key


class Default(Theme, widget.RoundedBoxMixin):
    """Default theme (large rounded box around the title)."""

    key = 'default'
    name = 'Classique'

    def render_ListTitle(self, _, data):
        """Render the list title."""
        # pylint: disable-msg=E1101
        return T.div(render=self.render_small_rounded_box, _class="listtitle")[
            T.h1(style="color:white; padding: 1ex")[data]]

    def render_Lock(self, _, data):
        """Render the 'reserved' lock."""
        # pylint: disable-msg=E1101
        return T.img(src="/images/reserve.png", width="23", height="23",
                     alt=data, title=data, style="margin-right: 1ex")
        

class XMas(Theme):
    """Christmas theme."""

    key = 'xmas'
    name = u'Noël'

    def render_ListTitle(self, _, data):
        """Render the list title."""
        # pylint: disable-msg=E1101
        return [T.img(src="/themes/xmas/xmas.png",
                      align="right"), T.h1[data]]

    def render_Lock(self, _, data):
        """Render the 'reserved' lock."""
        # pylint: disable-msg=E1101
        return T.img(src="/themes/xmas/lock.png",
                     alt=data, title=data, style="margin-right: 1ex")
        
class Baby(Theme):
    """Baby theme."""

    key = 'baby'
    name = u'Naissance'

    def render_ListTitle(self, _, data):
        """Render the list title."""
        # pylint: disable-msg=E1101
        return [T.img(src="/themes/baby/baby.png",
                      align="right"), T.h1[data]]

    def render_Lock(self, _, data):
        """Render the 'reserved' lock."""
        # pylint: disable-msg=E1101
        return T.img(src="/themes/baby/coeur.png",
                     alt=data, title=data, style="margin-right: 1ex")
        

class Birthday(Theme):
    """Birthday theme."""

    key = 'bday'
    name = u'Anniversaire'

    def render_ListTitle(self, _, data):
        """Render the list title."""
        # pylint: disable-msg=E1101
        return [T.img(src="/themes/bday/bday.png",
                      align="right"), T.h1[data]]

    def render_Lock(self, _, data):
        """Render the 'reserved' lock."""
        # pylint: disable-msg=E1101
        return T.img(src="/themes/bday/lock.png",
                     alt=data, title=data, style="margin-right: 1ex")
        

class Doudou(Theme):
    """Doudou theme."""

    key = 'doudou'
    name = u'Doudou'

    def render_ListTitle(self, _, data):
        """Render the list title."""
        # pylint: disable-msg=E1101
        return [T.img(src="/themes/doudou/doudou.png",
                      align="right"), T.h1[data]]

    def render_Lock(self, _, data):
        """Render the 'reserved' lock."""
        # pylint: disable-msg=E1101
        return T.img(src="/themes/doudou/lock.png",
                     alt=data, title=data, style="margin-right: 1ex")
        

themes = {}
for theme in (Default, XMas, Baby, Birthday, Doudou):
    themes[theme.key] = theme()
