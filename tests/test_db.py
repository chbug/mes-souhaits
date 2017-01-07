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
import os

from souhaits import core

class TestDB(object):
    
    def setup_method(self, method):
        uts.resetDB()
        uts.resetMail()
        self.db = core.Service('http://localhost:7707', debug=True)
        self.db.startService()

    def teardown_method(self, method):
        self.db.stopService()

    def create_user_and_list(self, name):
        email = name + '@foo.com'
        user, cookie = self.db.createSessionUser()
        self.db.pretend_email_address(user, email)
        challenge = os.path.basename(uts.get_challenge())
        assert self.db.validate_challenge(challenge, cookie)

        list_o = self.db.createList(user, name)
        return self.db.getUserByEmail(email), list_o

    def test_double_donated_item(self):
        """Don't resend the 'item donated' email."""
        user_a, list_a = self.create_user_and_list(u'a')
        user_b, list_b = self.create_user_and_list(u'b')

        item_id = self.db.addNewItem(list_a, 'foo', 'foo', 'foo')
        item = self.db.getListItem(list_a, item_id)

        self.db.reserveItem(user_b, item)
        assert self.db.donatedItem(user_b, item)
        assert uts.read_email()

        # second time, no email
        assert self.db.donatedItem(user_b, item)
        assert not uts.read_email()
