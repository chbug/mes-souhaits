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
import uts

from souhaits import format

class TestFormat(object):

    def testParagraph(self):
        p = format.format_description ('''\
hehe

enfin...

bon
''')
        assert len (p) == 3
        for c in p:
            assert c.tagName == 'p'

    def testURL(self):
        url = 'http://www.amazon.fr/exec/obidos/ASIN/2910946355/qid=1100455627/ref=sr_8_xs_ap_i1_xgl/171-4266604-3933853'
        
        p = format.format_description (u'Mon site \n %s' % url)

        link = p [0].children [1]

        assert link.tagName == 'a'
        assert link.attributes ['href'] == url, link

        assert link.children [0] == 'http://www.amazon.fr/...', link

        url = 'http://www.king-jouet33.com/kjhtml/produit/fiche_produit.asp?IDproduit=GU93580'

        p = format.format_description (u'Mon site \n %s' % url)

        link = p [0].children[1]
        assert link.tagName == 'a'
        assert link.attributes['href'] == url
        assert link.children [0] == 'http://www.king-jouet33.com/...'
