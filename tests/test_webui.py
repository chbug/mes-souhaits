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
import email
import uts

from souhaits import core

def setup_module(m):
    uts.startDaemon()

def teardown_module(m):
    uts.stopDaemon()


class TestWithFreshBrowser(object):

    def setup_method(self, m):
        self.cx = uts.resetDB()
        self.cu = self.cx.cursor()
        uts.resetMail()

        self.u = uts.SouhaitUser()

    def teardown_method(self, m):
        self.u.stop()

    def test_BasicSessions(self):
        # Hitting the front page creates no session
        self.u.open()
        self.cu.execute('SELECT COUNT(*) FROM session')
        assert self.cu.fetchone()[0] == 0

        # Try to use the login button
        self.u.open()
        self.u.siteLogin('email@host.com')
        assert self.u.location() == uts.url()
        self.u.openChallenge()

        # try to logout immediately after
        self.u.siteLogout()
        self.cu.execute('SELECT * FROM session')
        r = self.cu.fetchall()
        assert len(r) == 0


class SharedSelenium(object):

    def setup_class(cls):
        cls.u = uts.SouhaitUser()

    def teardown_class(cls):
        cls.u.stop()


class TestWithOneUser(SharedSelenium):

    def setup_method(self, m):
        self.cx = uts.resetDB()
        self.cu = self.cx.cursor()
        uts.resetMail()

    def teardown_method(self, m):
        self.u.siteLogout()

    def test_CreateListAsGuest(self):
        """ Create a list as a new  user. You then get a mail and are pre-logged """
        
        self.u.open()
        self.u.createList('Ma nouvelle liste', 'gobry@pybliographer.org')

        # the user received a nice mail to get logged, while he is
        # directed to the list's page.
        assert self.u.location() ==  uts.url('/ma-nouvelle-liste')
        
        # from that point, there is a challenge, a user and a session
        # in the system
        self.cu.execute('SELECT COUNT (*) FROM session')
        assert self.cu.fetchone()[0] == 1
        
        self.cu.execute('SELECT key FROM user')
        r = self.cu.fetchall()
        assert len(r) == 1

        user, = r[0]
        
        self.cu.execute('SELECT COUNT (*) FROM wishlist')
        assert self.cu.fetchone()[0] == 1

        # when the user follows the link, the challenge is accepted,
        # and the user's email is validated
        self.u.openChallenge()

        self.cu.execute('SELECT email FROM user WHERE key = ?', (user,))
        address = self.cu.fetchone()[0]

        assert address == 'gobry@pybliographer.org'
        
        self.cu.execute('SELECT COUNT (*) FROM wishlist')
        assert self.cu.fetchone()[0] == 1

    def test_ForceUserToProvideListInfo(self):
        """ Check that the email and the list name are completed """

        self.u.open()
        self.u.createList('Ma nouvelle liste')

        assert self.u.location() == uts.url('/newlist')

        # just add the email, as the listname should still be here
        self.u.createList(None, 'foo@h.com')
        assert self.u.location() ==  uts.url('/ma-nouvelle-liste')


    def test_DetectMissingListInfo(self):
        """ For an anonymous user, it is necessary to provide both email and list name """
        
        self.u.open()
        self.u.createList(None, 'foo@h.com')
        assert self.u.location() == uts.url('/newlist')

    def test_SendAgain(self):
        """ It is possible to ask for a second email, possibly
        changing the email address in the process. """

        self.u.open()
        self.u.siteLogin('a@h.com')
        uts.resetMail()

        self.u.siteLogin('b@h.com')
        self.u.openChallenge()

        self.srv = core.Service(uts.url())
        self.srv.startService()
        
        assert not self.srv.getUserByEmail('a@h.com')
        assert self.srv.getUserByEmail('b@h.com')

    def test_reject_invalid_login(self):
        self.u.open()
        self.u.siteLogin('a@b')  # missing tld

        # we're still on the login page
        assert self.u.location() == uts.url('/login')
        self.cu.execute('SELECT COUNT (*) FROM challenge')
        assert self.cu.fetchone()[0] == 0

    def test_reject_invalid_email_in_list(self):
        self.u.open()
        self.u.createList('foo', 'a@b')  # missing tld

        # we're still on the new list page
        assert self.u.location() == uts.url('/newlist')
        self.cu.execute('SELECT COUNT (*) FROM wishlist')
        assert self.cu.fetchone()[0] == 0


class TestOneUserAndList(SharedSelenium):
    """Our initial state is a session with a user owning a list."""

    def setup_method(self, m):
        self.cx = uts.resetDB()
        self.cu = self.cx.cursor()
        uts.resetMail()

        self.u.open()
        self.u_list = self.u.createList('Ma nouvelle liste', 'b@h.com')
        self.u.openChallenge()

    def teardown_method(self, m):
        self.u.siteLogout()

    def testListMerging(self):
        # user b has a wish in his list
        self.u.open('/' + self.u_list)
        self.u.createItem(title='A test', description='blah...',
                          url='http://www/')

        # user a logs in and visits list b
        a = uts.SouhaitUser()
        a.open()
        a.siteLogin('a@h.com')
        a.openChallenge()
        a.open('/' + self.u_list)

        srv = core.Service(uts.url())
        srv.startService()

        a_id = srv.getUserByEmail('a@h.com')

        try:
            self.cu.execute('SELECT COUNT (*) FROM friend WHERE user = ?',
                            (a_id.id,))
            assert self.cu.fetchone()[0] == 1

            # a logs out, comes back to the list of b, logs in, visits the
            # page and confirms her identity after that.
            a.siteLogout()
            a.siteLogin('a@h.com')
            a.openChallenge()

            # we should not have a duplicate
            self.cu.execute('SELECT COUNT (*) FROM friend WHERE user = ?',
                            (a_id.id,))
            assert self.cu.fetchone()[0] == 1

        finally:
            a.stop()

    def testDetectMissingListInfo (self):
        """ For an logged user, it is necessary to provide a list name """

        self.u.open('/newlist')
        self.u.createList('')

        assert self.u.location() == uts.url('/newlist')
    
    def testNoNeedForEmail (self):
        """ For an logged user, no need to provide an email """
        
        uts.resetMail ()
        self.u.open('/newlist')
        self.u.createList('autre liste')

        assert self.u.location() == uts.url('/autre-liste')
        assert open('+mailbox').read() == ''
    
    def testMergeListForOldUser(self):
        """ Check that if a user logs out and creates a new list
        afterward, the two lists get properly merged"""

        self.u.siteLogout()
        self.u.open()
        
        self.u.createList ('Une autre liste', 'b@h.com')
        self.u.openChallenge()

        self.cu.execute ('SELECT COUNT (*) FROM user')
        assert self.cu.fetchone () [0] == 1
        
        self.cu.execute ('SELECT COUNT (*) FROM wishlist')
        assert self.cu.fetchone () [0] == 2

    def testCreateItem(self):
        self.u.open('/ma-nouvelle-liste')
        
        self.u.createItem(title='A test', description='blah...',
                          url='http://www/')

        assert self.u.location() == uts.url('/ma-nouvelle-liste')
        
        self.cu.execute('SELECT title, description, url FROM item')
        r = self.cu.fetchall()

        assert r == [('A test', 'blah...', 'http://www/')]

    def testUnicodeInURL(self):
        self.u.open('/ma-nouvelle-liste')

        url = u'http://www/héhé'
        self.u.createItem(title='A test', description='blah...',
                          url=url)
        
        assert self.u.b.get_text('//div[@class="item"]//a') == url

    def testDeleteItem (self):

        self.u.open('/ma-nouvelle-liste')
        
        self.u.createItem(title='A test', description='blah...',
                          url='http://www/')
        self.u.deleteItem()

        assert self.u.location() == uts.url('/ma-nouvelle-liste')

        self.cu.execute('SELECT title, description, url FROM item')
        assert len(self.cu.fetchall()) == 0
    

    def testModifyItem(self):
        self.u.open('/ma-nouvelle-liste')
        
        self.u.createItem(title='A test', description='blah...',
                          url='http://www/')

        self.cu.execute('SELECT key FROM item')
        key, = self.cu.fetchall()[0]

        self.u.open('/ma-nouvelle-liste/' + str (key))

        self.u.editItem(description='blih')

        self.cu.execute('SELECT title, description, url FROM item')
        r = self.cu.fetchall()

        assert r == [('A test', 'blih', 'http://www/')], repr (r)

    def testInviteUnknownPerson(self):
        """ Send an invitation to someone that never used the site."""

        srv = core.Service(uts.url())
        srv.startService()

        list_id = srv.getListByURL(self.u_list)

        self.u.inviteFriend('me', 'u@h.com', 'youyou', [list_id])
        o = uts.SouhaitUser()
        try:
            o.openChallenge()
        finally:
            o.stop()

        # the person should have a home page with a link to a's list
        u = srv.getUserByEmail('u@h.com')

        # We only keep the list info, not the freshness
        friends = [l[0] for l in srv.getFriendLists(u)]
        assert friends == [list_id]


class TestGC(object):

    def setup_method(self, m):
        self.cx = uts.resetDB()
        self.cu = self.cx.cursor()

        self.srv = core.Service(uts.url())
        self.srv.startService()
        return

    def testGCUser(self):
        """ Sessions are destroyed at the same time as the corresponding user """

        self.cu.execute ('INSERT INTO user (key, creation, email) VALUES (?, ?, ?)', (
            1, core.hours_ago (8 * 24), None))
        self.cu.execute ('INSERT INTO session (key, creation, user) VALUES (?, ?, ?)', (
            "s", core.hours_ago (24), 1))
        self.cu.execute ('INSERT INTO challenge (creation, session, email, user) '
                         'VALUES (?, ?, ?, ?)', (
            core.hours_ago (24), "s", 'eeee', 1))
        
        self.cx.commit ()
        
        self.srv.garbageCollector ()

        self.cu.execute ('SELECT * FROM user')
        assert self.cu.fetchall () == []

        self.cu.execute ('SELECT * FROM session')
        assert self.cu.fetchall () == []

        self.cu.execute ('SELECT * FROM challenge')
        assert self.cu.fetchall () == []
    
    def testNoGCRegisteredUser(self):

        self.cu.execute ('INSERT INTO user (key, creation, email) VALUES (?, ?, ?)', (
            1, core.hours_ago (3 * 24), 'toto'))
        self.cu.execute ('INSERT INTO session (key, creation, user) VALUES (?, ?, ?)', (
            "s", core.hours_ago (24), 1))
        self.cu.execute ('INSERT INTO challenge (creation, session, email, user) '
                         'VALUES (?, ?, ?, ?)', (
            core.hours_ago (24), "s", 'eeee', 1))
        
        self.cx.commit ()
        
        self.srv.garbageCollector ()

        self.cu.execute ('SELECT * FROM user')
        assert len (self.cu.fetchall ()) == 1
        
    def testGCSession(self):
        
        self.cu.execute ('INSERT INTO session (creation, user, activity)'
                         ' VALUES (?, ?, ?)', (
            core.hours_ago (24 * 181), 1, core.hours_ago(24 * 181)))

        self.cx.commit ()
        
        self.srv.garbageCollector ()

        self.cu.execute ('SELECT * FROM session')
        assert self.cu.fetchall () == []

    def testGCConfirmedItems(self):
        self.cu.execute ('INSERT INTO user (key, email) VALUES (?, ?)', (
            1, None))
        self.cu.execute ('INSERT INTO wishlist (url, owner) VALUES (?, ?)', (
            'a', 1))
        self.cu.execute ('INSERT INTO item (key, list) VALUES (?, ?)', (
            10, 1))
        self.cu.execute ('INSERT INTO reservation (item, owner, status, confirmation) VALUES (?, ?, ?, ?)', (
            10, 2, 'D', core.hours_ago (24 * 29)))
        self.cx.commit ()
        
        self.srv.garbageCollector ()
        self.cu.execute ('SELECT * FROM item')
        assert len(self.cu.fetchall ()) == 1

        self.cu.execute('DELETE FROM reservation')
        self.cu.execute('INSERT INTO reservation (item, owner, status, confirmation) VALUES (?, ?, ?, ?)', (
            10, 2, 'D', core.hours_ago (24 * 30 + 10)))
        self.cx.commit ()

        self.srv.garbageCollector ()
        self.cu.execute ('SELECT * FROM item')
        assert len(self.cu.fetchall ()) == 0
        self.cu.execute ('SELECT * FROM reservation')
        assert len(self.cu.fetchall ()) == 0


class TestTwoUsers(object):

    def setup_class(cls):
        cls.a = uts.SouhaitUser()
        cls.b = uts.SouhaitUser()

    def teardown_class(cls):
        cls.a.stop()
        cls.b.stop()

    def setup_method(self, m):
        # Our initial state is a session with a user owning a list
        self.srv = core.Service(uts.url())
        self.srv.startService()
        
        self.cx = uts.resetDB()
        self.cu = self.cx.cursor()

        uts.resetMail()
        
        self.a_user, self.a_list = self.a.makeUserAndList(self.srv, 'a')
        self.b_user, self.b_list = self.b.makeUserAndList(self.srv, 'b')

        self.b.open('/liste-b')
        
        self.b.createItem(title='A test', description='blah...',
                          url='http://www/')

        self.b_item = self.srv.itemsForList(self.b_list)

    def testCoeditors(self):

        self.a.open('/liste-a/edit')
        self.a.b.type('coEditors', 'b@h.com')
        self.a.Submit('desc')

        # check that b can change the items too
        self.b.open('/liste-a')
        self.b.createItem(title='A test', description='blah...')

        assert len(self.srv.itemsForList(self.a_list)) == 1
        
    def testUnknownCoeditor(self):
        """Refuse to set an unknown user as coeditor."""
        self.a.open('/liste-a/edit')
        self.a.b.type('coEditors', 'z@h.com')
        self.a.Submit('desc')

        assert self.a.location() == uts.url('/liste-a/edit')

    def testReserveSimple(self):

        self.a.open('/liste-b')

        # Make a reservation
        self.a.Reserve()

        # We should be on the same page
        assert self.a.location() == uts.url('/liste-b')

        # ...and a has a reservation
        r = self.srv.getUserReservations(self.a_user)
        assert len(r) == 1
        
        # but now, the item is no more to be reserved
        try:
            self.a.Reserve()
            assert False, 'should not happen'
        except Exception:
            pass

        # on the other hand, it is in the "reserved" list
        self.a.open('/')
        self.a.Giveup()

        r = self.srv.getUserReservations(self.a_user)
        assert len(r) == 0


    def testGiveupFromList(self):
        self.a.open('/liste-b')

        # Make a reservation
        self.a.Reserve()
        self.a.Giveup()

        r = self.srv.getUserReservations(self.a_user)
        assert len(r) == 0

    def testNoDoubleReserve(self):
        assert self.srv.reserveItem(self.a_user, self.b_item[0])
        assert not self.srv.reserveItem(self.b_user, self.b_item[0])
    
    def testMergeReservation(self):
        """It is possible to reserve, and then login to an existing
        account."""
        
        # create a secondary user that will reserve an item
        self.b.siteLogout()
        self.b.open('/' + self.b_list.url)
        self.b.Reserve()

        # Suddenly, it occurs that x is in fact user a. It is
        # important that he uses the correct login box, as the
        # reservation hasn't been performed yet.
        self.b.siteLogin('a@h.com', go_to_login=False)
        self.b.openChallenge()

        # Then, the reservation must belong to user a.
        r = self.srv.getUserReservations(self.a_user)
        assert len(r) == 1

    def testDiscardIllegalReservation(self):
        # create a secondary user that will reserve an item
        
        self.b.siteLogout()
        self.b.open('/' + self.b_list.url)
        self.b.Reserve()

        # Suddenly, it occurs that x is in fact user b.
        self.b.open()
        self.b.siteLogin('b@h.com')
        self.b.openChallenge()

        # Then, the reservation cannot be kept, as b is the owner of
        # the list.
        r = self.srv.getUserReservations(self.b_user)
        assert len(r) == 0
    
    def testReserveAnonyme(self):
        """ To reserve an item as an anonymous user, you need to ask
        the identity of the user"""

        self.a.siteLogout()
        self.a.open('/liste-b')

        uts.resetMail()

        self.a.Reserve()
        assert self.a.location().startswith(uts.url('/login'))

    def testReserveAndDelete(self):
        """ The reserved item is deleted ! """

        self.a.open('/liste-b')

        # Make a reservation
        self.a.Reserve()

        # delete the item
        self.b.open('/liste-b')
        self.b.deleteItem()

        # and check that a has no reservation anymore, and an email in
        # return
        r = self.srv.getUserReservations(self.a_user)
        assert r == []
        
        m = email.message_from_file(open('+mailbox'))
        text = m.get_payload(decode=True)
        
    def testReserveAndDestroy(self):
        """ The complete list is destroyed """

        self.a.open('/liste-b')

        # Make a reservation
        self.a.Reserve()

        # delete the item
        self.b.open('/liste-b/destroy')
        self.b.Submit('confirm')
        self.b.Wait()

        # and check that a has no reservation anymore, and an email in
        # return
        r = self.srv.getUserReservations(self.a_user)
        assert r == []
        
        m = email.message_from_file(open('+mailbox'))
        text = m.get_payload(decode=True)
        
    def testInviteKnownPerson(self):
        
        self.a.inviteFriend('me', 'b@h.com', 'youyou', [self.a_list])
        self.b.openChallenge()
        
        # We only keep the list info, not the freshness
        friends = [l[0] for l in self.srv.getFriendLists(self.b_user)]
        assert friends == [self.a_list]

    def testInviteMultipleLists(self):

        self.a.open('/newlist')
        _url = self.a.createList('other')
        list_2 = self.srv.getListByURL(_url)
        
        self.a.inviteFriend('me', 'b@h.com', 'youyou', [self.a_list, list_2])

        self.b.openChallenge()

        # We only keep the list info, not the freshness
        friends = [l[0] for l in self.srv.getFriendLists(self.b_user)]
        assert friends == [self.a_list, list_2]
        
    def testReopenChallenge(self):
        self.a.inviteFriend('me', 'b@h.com', 'youyou', [self.a_list])

        challenge = self.b.openChallenge()

        # if someone else opens this page, he/she gets logged in
        o = uts.SouhaitUser()
        try:
            o.open(raw=challenge)
            assert o.location() == uts.url('/')
        finally:
            o.stop()

    def testFriendCanInvite(self):
        # now, b is a friend of a
        self.b.open('/liste-a')

        # check that b can invite for list a
        self.b.inviteFriend('me', 'other@h.com', 'blah', [self.a_list])

        o = uts.SouhaitUser()
        try:
            o.openChallenge()
            o_user = self.srv.getUserByEmail('other@h.com')
            assert [lst.id for lst, _ in self.srv.getFriendLists(o_user)] == \
                   [self.a_list.id]
        finally:
            o.stop()

