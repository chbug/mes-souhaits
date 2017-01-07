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
"""Various widgets to help in consistency and conciseness."""

from nevow import tags as T


class RoundedBoxMixin(object):
    """Mixing providing rounded boxes."""
    # pylint: disable-msg=E1101

    def render_rounded_box(self, ctx, _):
        """Place the current tag in a rounded box.

        This renderer will _replace_ the current div with a rounded
        box that will inherit the div's attributes.

        Args:
          ctx: the nevow context
          _: unused data

        Returns:
          the new stan tag
        """
        return self._make_fragment(ctx.tag, True)

    def render_small_rounded_box(self, ctx, _):
        """Place the current tag in a rounded box with no padding.

        This renderer will _replace_ the current div with a rounded
        box that will inherit the div's attributes.

        Args:
          ctx: the nevow context
          _: unused data

        Returns:
          the new stan tag
        """
        return self._make_fragment(ctx.tag, False)

    def _make_fragment(self, tag, add_padding):
        """Generate markup for a rounded box."""
        core = tag.children
        if add_padding:
            core = T.div(_class="boxcontent")[core]

        fragment = T.div[
            T.div(_class="br")[
            T.div(_class="tl")[
            T.div(_class="tr")[core]]]]

        # keep the parent's flags, but be careful to merge the class
        classes = [c for c in tag.attributes.get('class').split(' ') if c]
        classes.append('bl')
        fragment.attributes.update(tag.attributes)
        fragment.attributes['class'] = ' '.join(classes)
        return fragment
