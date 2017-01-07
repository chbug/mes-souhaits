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
from pysqlite2 import dbapi2 as sqlite

import email
import os
import re
import selenium
import signal
import sys
import time

sys.path.append ('..')

_link_re = re.compile(r'<(.*)>')

def url(url='/'):
    return 'http://127.0.0.1:7707' + url


def startDaemon():
    print "info: starting the server...",
    sys.stdout.flush ()

    try: os.unlink ('+mes-souhaits.db')
    except OSError: pass
    
    try: os.unlink ('twistd.log')
    except OSError: pass

    resetMail ()
    os.system ('PYTHONPATH=.. twistd -oy ../mes-souhaits-debug.tac')

    time.sleep (2)
    print "ok"
    return


def stopDaemon():
    print "info: stopping the server.",

    os.kill (int (open ('twistd.pid').read ()), signal.SIGINT)
    time.sleep (1)
    return


def resetMail():
    try: os.unlink ('+mailbox')
    except OSError: pass

    open ('+mailbox', 'w').close ()


def read_email():
    m = email.message_from_file(open('+mailbox'))
    text = m.get_payload(decode=True)
    resetMail()
    return text

def get_challenge():
    text = read_email()

    for line in text.split('\n'):
        m = _link_re.search(line)
        if not m: continue
        link = m.group(1)
        break
    else:
        assert False, 'cannot find link in mail'

    return link


def resetDB():

    cx = sqlite.connect ('+mes-souhaits.db')
    cu = cx.cursor ()

    for table in ['session', 'wishlist', 'user', 'challenge', 'item']:
        cu.execute ('DELETE FROM ' + table)

    cx.commit ()
    return cx


class SouhaitUser(object):
    """A proxy to a Selenium instance, with high-level functions.

    This class provides methods to log in, create lists,... on
    mes-souhaits.
    """

    try:
        FIREFOX_PATH = ' ' + os.environ['FIREFOX_BIN']
    except KeyError:
        FIREFOX_PATH = ''

    TIMEOUT_MS = 2000

    def __init__(self):
        self.b = selenium.selenium("localhost",  4444,
                                   "*firefox%s" % self.FIREFOX_PATH,
                                   "http://127.0.0.1:7707/")
        self.b.start()

    def stop(self):
        self.b.stop()

    def open(self, _url='/', raw=None):
        self.b.open(raw or url(_url))
        self.Wait()

    def location(self):
        return self.b.get_location()

    def siteLogin(self, email, go_to_login=True):
        if go_to_login:
            self.open('/login')
        if email:
            self.b.type('//div[@id="auth"]/form/input[@name="email"]', email)
        self.Submit('//div[@id="auth"]/form')

    def makeUserAndList(self, srv, suffix):

        self.open()

        # Create a list
        _url = self.createList('liste ' + suffix, suffix + '@h.com')
        a_list = srv.getListByURL(_url)

        self.openChallenge()

        a_user = srv.getUserByEmail(suffix + '@h.com')

        return a_user, a_list

    def openChallenge(self):
        link = get_challenge()
        self.b.open(link)
        self.Wait()
        return link

    def siteLogout(self):
        self.open('/logout')
        self.Submit('logout')

    def createList(self, name, mail=None):
        if mail is not None:
            self.b.type('listemail', mail)
        if name is not None:
            self.b.type('listname', name)

        self.Submit('newlist')

        # let's return the url of the list
        return self.b.get_location().split('/')[-1]

    def createItem(self, ** args):
        for k, v in args.items():
            self.b.type(k, v)
        self.Submit('add')

    def editItem (self, ** args):
        for k, v in args.items ():
            self.b.type(k, v)
        self.Submit('edit')

    def deleteItem(self):
        self.b.click("xpath=//a[contains(@href,'/delete')]")
        self.Wait()
        self.Submit('confirm')

    def inviteFriend(self, sender, email, msg, lists):
        self.open('/invite')

        def _Type(field, value):
            self.b.type('//form[@name="invite"]//input[@name="%s"]' % field,
                        value)

        _Type('email', email)
        _Type('sender', sender)
        self.b.type('//form[@name="invite"]//textarea[@name="body"]', msg)

        for l in lists:
            self.b.check('//form[@name="invite"]'
                         '//input[@type="checkbox" and @value="%s"]' % l.id)
        self.b.click('//form[@name="invite"]//input[@name="send"]')
        self.Wait()

    def Reserve(self):
        self.b.click("//input[@name='get']")
        self.Wait()

    def Giveup(self):
        self.b.click("//input[@name='giveup']")
        self.Wait()

    def Submit(self, locator):
        self.b.submit(locator)
        self.Wait()

    def Wait(self):
        self.b.wait_for_page_to_load(self.TIMEOUT_MS)
        
