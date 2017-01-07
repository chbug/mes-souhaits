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
"""Internal API of the application.

Provides database calls, entities,...
"""
from email import Header  # pylint: disable-msg=E0611
from email import MIMEText  # pylint: disable-msg=E0611

import md5
import random
import string  # pylint: disable-msg=W0402
import time
import re

try:
    import sqlite3 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite

from twisted.application import service
from twisted.mail import smtp
from twisted.internet import task
from twisted.python import log
from zope.interface import implements, Interface  # pylint: disable-msg=F0401

from souhaits.web import theme

# This dict will map some accented letters to their non-accented
# version
_UNI_TO_ASCII = {}
for _ss, _t in [
    (u'éèêë', 'e'),
    (u'àâ',   'a'),
    (u'îï',   'i'),
    (u'ôö',   'o'),
    (u'ùûü',  'u'),
    (u'ç',    'c'),
    ]:
    for _s in _ss:
        _UNI_TO_ASCII[ord(_s)] = unicode(_t)

# This string is suitable for a call to string.translate and only
# keeps alphanumeric symbols
_ALNUM_ONLY = ['-'] * 256

for l in string.ascii_lowercase + string.digits:
    _ALNUM_ONLY [ord (l)] = l

_ALNUM_ONLY = ''.join (_ALNUM_ONLY)


def _make_cookie():
    """Generate a new random cookie."""
    return md5.new ("%s_%s" % (
            str(random.random()),
            str(time.time()))).hexdigest()

# Reserved wishlist names
RESERVED = frozenset(('newlist', 'login', 'logout', 'challenge', 'invite',
                      'css', 'images', 'js', 'themes', 'about', 'help'))


def hours_ago(hours):
    """ Returns a timestamp from 'hours' hours ago """
    timestamp = time.time() - hours * 3600
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamp))


def normalize_url(url):
    """Return an URL with no invalid unicode character."""
    return url.lower().                \
           translate(_UNI_TO_ASCII).   \
           encode('ascii', 'replace'). \
           translate(_ALNUM_ONLY).     \
           strip('-')


def _validate_url(cursor, url):
    """Create a unique base url name from a name.

    This normalizes the string (lower case, no accents, no special
    symbols) and checks in the list of existing urls.

    Args:
      cursor: database cursor
      url: unicode, text to transform into an URL
    
    Returns:
      str, unique URL fragment
    """
    baseurl = normalize_url(url)

    suffix = None
    if baseurl in RESERVED:
        suffix = 1

    while 1:
        if suffix is None:
            url = baseurl
            suffix = 1
        else:
            url = baseurl + '-' + str (suffix)
            suffix += 1

        cursor.execute ('SELECT COUNT (*) FROM wishlist WHERE url = ?', (url,))
        if cursor.fetchone () [0] == 0:
            break

    return url


def validate_email(address):
    """Cleanup an email address. Return None if the address is invalid."""
    address = address.replace(' ', '').lower()
    m = re.match(r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,6}$', address)
    if m:
        return address
    return None


def _to_uni(text):
    """Ensure a string is in unicode."""
    if text is None:
        return ''
    return unicode(text)


def _to_str(text):
    """Ensure a string is in utf-8."""
    if text is None:
        return ''
    if isinstance(text, unicode):
        return text.encode('utf-8')
    return str(text)

    
class Wishlist(object):
    """A wish list."""

    def __init__(self, list_id, name, url, description, owner,
                 showres, theme_name=''):
        self.id      = list_id
        self.name    = _to_uni (name)
        self.url     = _to_str (url)
        self.desc    = _to_uni (description)
        self.owner   = owner
        self.showres = showres
        self.theme   = theme.themes.get(theme_name, theme.themes['default'])
        return

    def __repr__(self):
        return 'Wishlist (%s, %s, %s)' % (
            repr (self.id),
            repr (self.name),
            repr (self.url))

    def __eq__(self, other):
        return self.id == other.id

    
class User(object):
    """A user (registered or not)."""

    def __init__ (self, list_id, email):
        self.id = list_id
        self.email = _to_str(email).lower()

    
class Item(object):
    """A single wish in a wishlist."""

    def __init__ (self, key, wishlist, title, description, url, score):
        self.key         = key
        self.list        = wishlist
        self.title       = _to_uni(title)
        self.description = _to_uni(description)
        self.url         = _to_str(url)
        self.score       = score
        self.res = None

    def __repr__ (self):
        return 'Item %s' % repr (self.__dict__)


class IService(Interface):  # pylint: disable-msg=W0232
    """The service interface describes all database operations."""


class Service(service.Service):
    """Implementation of the database operations."""
    implements(IService)

    GC_PERIOD = 3600 * 8
    ADMIN = 'webmaster@mes-souhaits.net'
    
    def __init__ (self, base_url, debug=True):
        self.base_url = base_url
        self.gc_task = None
        self.cx = None
        self.debug = debug

    def startService(self):
        """Start the web service (database, GC task)."""
        log.msg('starting souhaits db, debug=%r' % (self.debug,))

        self.gc_task = task.LoopingCall(self.garbageCollector)
        self.cx = sqlite.connect('+mes-souhaits.db')

        cu = self.cx.cursor ()
        cu.execute ("SELECT COUNT (tbl_name) FROM sqlite_master")

        if cu.fetchone () [0] > 0:
            self.garbageCollector ()
            self.gc_task.start (self.GC_PERIOD)
            return
        
        log.msg ('starting a new database')

        # A session is the permanent object that identifies a given
        # physical user. This user can be already identified or not.
        
        cu.execute ("""
        CREATE TABLE session (
           key      STRING    PRIMARY KEY,
           creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           user     INTEGER   NOT NULL,
           activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cu.execute ('''CREATE INDEX sess_user ON session (user)''')
        
        # A wishlist is what people come here for
        cu.execute ("""
        CREATE TABLE wishlist (
           key          INTEGER   PRIMARY KEY AUTOINCREMENT,
           creation     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           url          STRING    UNIQUE,
           name         STRING,
           owner        INTEGER,
           description  STRING,
           showres      INTEGER,
           theme        STRING
        )
        """)

        cu.execute ('''CREATE INDEX wish_url   ON wishlist (url)''')
        cu.execute ('''CREATE INDEX wish_owner ON wishlist (owner)''')

        # A user is the entity owning a wishlist. It can exist before
        # it is actually bound to an email address, but his lifetime
        # is then shorter (ie, he has to identify himself quickly)
        cu.execute ("""
        CREATE TABLE user (
           key        INTEGER   PRIMARY KEY AUTOINCREMENT,
           creation   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           email      STRING    UNIQUE
        )
        """)
        cu.execute ('''CREATE INDEX user_email ON user (email)''')

        # A challenge is an attempt to bind an email with a
        # session. If the challenge can be answered by the user, his
        # session is linked to his email
        cu.execute ("""
        CREATE TABLE challenge (
           challenge  STRING    PRIMARY KEY,
           creation   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           session    STRING    NOT NULL,
           email      STRING    NOT NULL,
           user       INTEGER   NOT NULL,
           active     BOOLEAN
        )
        """)
        
        # An item is an element of a wish list. It belongs to a list
        # and contains the description of the wish.
        cu.execute ("""
        CREATE TABLE item (
           key          INTEGER   PRIMARY KEY AUTOINCREMENT,
           creation     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           list         INTEGER   NOT NULL,
           title        STRING,
           description  STRING,
           url          STRING,
           score        INTEGER
        )
        """)

        cu.execute ('''CREATE INDEX item_list ON item (list)''')

        # List of reservations from lists
        cu.execute ("""
        CREATE TABLE reservation (
           key         INTEGER   PRIMARY KEY AUTOINCREMENT,
           creation    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           item        INTEGER   UNIQUE NOT NULL,
           owner       INTEGER   NOT NULL,
           status      STRING    NOT NULL,
           confirmation TIMESTAMP
        )
        """)
        
        cu.execute ('''CREATE INDEX res_item  ON reservation (item)''')
        cu.execute ('''CREATE INDEX res_owner ON reservation (owner)''')
        
        # List of reservations from lists
        cu.execute ("""
        CREATE TABLE friend (
           key         INTEGER   PRIMARY KEY AUTOINCREMENT,
           visit       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           list        INTEGER   NOT NULL,
           user        INTEGER   NOT NULL
        )
        """)
        
        cu.execute ('''CREATE INDEX friend_user  ON friend (user)''')

        # List of co-editors for wishlists: a co-editor can manage the
        # items in a list, but cannot destroy the list itself.
        cu.execute("""
        CREATE TABLE coeditor (
           key        INTEGER PRIMARY KEY AUTOINCREMENT,
           list       INTEGER NOT NULL,
           user       INTEGER NOT NULL
        )
        """)
        
        cu.execute ('''CREATE INDEX coeditor_list ON coeditor (list)''')

        # =============================
        # COHERENCY CONSTRAINTS
        # =============================
        cu.execute ("""
        CREATE TRIGGER delete_wishlist AFTER DELETE ON wishlist
        BEGIN
          DELETE FROM item     WHERE list = old.key;
          DELETE FROM friend   WHERE list = old.key;
          DELETE FROM coeditor WHERE list = old.key;
        END;
        """)
        
        cu.execute ("""
        CREATE TRIGGER delete_user AFTER DELETE ON user
        BEGIN
          DELETE FROM wishlist    WHERE owner = old.key;
          DELETE FROM reservation WHERE owner = old.key;
          DELETE FROM session     WHERE user  = old.key;
          DELETE FROM challenge   WHERE user  = old.key;
          DELETE FROM friend      WHERE user  = old.key;
          DELETE FROM coeditor    WHERE user  = old.key;
        END;
        """)

        # Update the list's modification date 
        cu.execute ("""
        CREATE TRIGGER update_item AFTER UPDATE ON item
        BEGIN
          UPDATE wishlist SET modification = CURRENT_TIMESTAMP WHERE old.list = key;
          UPDATE item     SET modification = CURRENT_TIMESTAMP WHERE old.key  = key;
        END;
        """)
        
        cu.execute ("""
        CREATE TRIGGER delete_item AFTER DELETE ON item
        BEGIN
          UPDATE wishlist SET modification = CURRENT_TIMESTAMP WHERE old.list = key;
          DELETE from reservation WHERE item = old.key;
        END;
        """)
        
        cu.execute ("""
        CREATE TRIGGER create_item AFTER INSERT ON item
        BEGIN
          UPDATE wishlist SET modification = CURRENT_TIMESTAMP WHERE new.list = key;
        END;
        """)
        
        self.cx.commit()

        self.gc_task.start (self.GC_PERIOD)
        return

    
    def stopService(self):
        """Stop the service."""
        log.msg ('stopping souhaits db')
        self.gc_task.stop ()
        return

    def garbageCollector(self):
        """Clean old sessions, pending users,..."""
        cu = self.cx.cursor()

        # Drop sessions older than 6 months
        cu.execute ('DELETE FROM session WHERE activity < ?', (
            hours_ago(24 * 180),))

        # Discard users that did not manage to identify themselves in
        # 7 days
        cu.execute ('DELETE FROM user WHERE email IS NULL AND creation < ?', (
            hours_ago(7 * 24),))

        # Discard challenges that did not manage to identify
        # themselves in 7 days
        cu.execute ('DELETE FROM challenge WHERE creation < ? AND NOT active', (
            hours_ago(7 * 24),))

        # Discard items from confirmed reservations older than one month
        cu.execute("DELETE FROM item WHERE key IN ("
                   "SELECT j.key FROM item j, reservation r WHERE "
                   "j.key = r.item AND r.status = 'D' AND "
                   "r.confirmation < ?)", (hours_ago(24*30),))

        self.cx.commit()
        return

    def sendmail(self, _from, recipient, body):
        """Send an email message."""
        if self.debug:
            open('+mailbox', 'a').write(body)
        else:
            smtp.sendmail('localhost', _from, recipient, body)

    def build_and_send(self, recipient, subject, body,
                       from_name=u'Mes souhaits',
                       from_email=None):
        """Compose an email and send it."""
        # pylint: disable-msg=E1101
        msg = MIMEText.MIMEText(body.encode('utf-8'))

        if from_email is None:
            from_email = self.ADMIN
        else:
            msg['Sender'] = self.ADMIN
            # Ensure the recipient will be able to answer the mail
            msg ['Reply-To'] = from_email

        fromaddr = Header.Header('%s <%s>' % (from_name, from_email),
                                 'utf-8').encode()
        msg['From'] = fromaddr
        msg['User-Agent'] = 'Twisted Mail'
        msg['To'] = recipient
        msg['Subject'] = Header.Header(subject, 'utf-8')

        msg.set_charset('utf-8')
        self.sendmail(from_email, [recipient], msg.as_string())

    def createSessionUser(self):
        """Create a website user."""
        cookie = _make_cookie ()

        cu = self.cx.cursor ()

        # When we create a new session, it starts by being owned by
        # some fresh user. Only later will the user be authentified.
        cu.execute ("INSERT INTO USER (email) VALUES (NULL)")
        userid = cu.lastrowid
        
        cu.execute ("INSERT INTO session (key, user, activity)"
                    " VALUES (?, ?, datetime('now'))", (
                cookie, userid))
        self.cx.commit ()
        
        return User(userid, None), cookie


    def createList(self, user, name, email = None):
        """Create a new wish list that belongs to 'user'.

        It is possible to document the email of the session's owner in
        case it is not known.

        Args:
          user: User
          name: str
          email: str or None

        Returns:
          Wishlist
        """

        if not user.email and email:
            if not self.pretend_email_address(user, email):
                return None
        cu = self.cx.cursor()
        url = _validate_url(cu, name)
        cu.execute('INSERT INTO wishlist (name, url, owner) VALUES (?, ?, ?)', (
            name, url, user.id))
        self.cx.commit()

        return Wishlist(cu.lastrowid, name, url, '', user.id, False)

    def updateList(self, lst, title=None, url=None,
                   description=None, showres=None, coEditors=None,
                   theme_id=None):
        """Update the fields of a list."""
        cu = self.cx.cursor()
        if title is not None:
            cu.execute('UPDATE wishlist SET name = ? WHERE key = ?', (
                title, lst.id))
            
        if url is not None:
            url = _validate_url(cu, url)
            
            cu.execute('UPDATE wishlist SET url = ? WHERE key = ?', (
                url, lst.id))
        else:
            url = lst.url
            
        if description is not None:
            cu.execute('UPDATE wishlist SET description = ? WHERE key = ?', (
                description, lst.id))

        if showres is not None:
            cu.execute('UPDATE wishlist SET showres = ? WHERE key = ?', (
                showres, lst.id))

        if theme_id is not None:
            cu.execute('UPDATE wishlist SET theme = ? WHERE key = ?', (
                theme_id, lst.id))

        unknown = []
        if coEditors is not None:
            cu.execute('DELETE FROM coeditor WHERE list = ?', (
                lst.id,))

            for co in coEditors:
                uid = self.getUserByEmail(co)
                if uid is None:
                    unknown.append(co)
                    continue
                
                cu.execute('INSERT INTO coeditor (list, user) VALUES (?, ?)', (
                    lst.id, uid.id))
                
        self.cx.commit ()
        
        return url, unknown

    def pretendedEmail(self, user):
        """Return the email address a pending user has declared."""
        cu = self.cx.cursor ()
        cu.execute ('SELECT email FROM challenge WHERE user = ?', (
            user.id,))

        r = cu.fetchall ()
        if not r:
            return None

        return r [0] [0]


    def pretend_email_address(self, user, email):
        """Register a user's email address.

        The user told us his email address. As we are suspicious, we
        won't believe him immediately and send a challenge.

        Args:
          user: User
          email: str
        """

        cu = self.cx.cursor ()

        email = validate_email(email)
        if not email:
            return False

        challenge = _make_cookie()

        # Simply delete all the active challenges for this user, and
        # create a new non-active one.
        cu.execute('DELETE FROM challenge WHERE email = ? AND active = ?', (
                email, True))
        log.msg('creating new challenge for email %r' % (email,))
        # let's make a new user
        cu.execute ('INSERT INTO challenge (challenge, email, user, '
                    'session, active) VALUES (?, ?, ?, ?, ?)', (
                challenge, email, user.id, '-', False))
        self.cx.commit ()

        info = {'url': self.base_url + '/challenge/' + challenge}

        body = u"""\
Bonjour,

Voici votre clé personnelle pour entrer sur « Mes souhaits ». Cliquez
simplement sur le lien ci-dessous.

  <%(url)s>

Bonnes listes de cadeaux !

-- 
Votre webmaster@mes-souhaits.net
""" % info

        self.build_and_send(email, u'Votre clé pour « Mes souhaits »',
                            body)
        return True

    def managesList(self, user, lst):
        """Returns whether 'user' manages list 'lst'."""
        if lst.owner == user.id:
            return True

        cu = self.cx.cursor()
        cu.execute('SELECT key FROM coeditor WHERE list = ? AND user = ?', (
            lst.id, user.id))

        r = cu.fetchall()
        return len(r) == 1

    def getCoEditors(self, lst):
        """Get the list of co-editors of a list."""
        cu = self.cx.cursor()
        cu.execute('SELECT u.key, u.email FROM user u, coeditor c WHERE'
                   ' c.list = ? AND c.user = u.key', (lst.id,))

        return [User(*r) for r in cu.fetchall()]

    def getListByURL (self, url):
        """Get a list by its URL fragment."""
        cu = self.cx.cursor()
        cu.execute ('SELECT key, name, url, description, owner, showres, theme'
                    ' FROM wishlist WHERE url = ?', (url,))

        r = cu.fetchall()
        if not r:
            return None

        return Wishlist(*r[0])

    def getListByKey (self, key):
        """Get a list by its ID."""
        cu = self.cx.cursor()
        cu.execute('SELECT key, name, url, description, owner, showres, theme'
                   ' FROM wishlist WHERE key = ?', (key,))

        r = cu.fetchall ()
        if not r:
            return None

        return Wishlist(*r[0])

    def getSessionUser(self, cookie):
        """Get a user by its cookie."""
        cu = self.cx.cursor()
        cu.execute ('SELECT u.key, u.email FROM user u, session s'
                    ' WHERE s.key = ? AND s.user = u.key', (cookie,))

        r = cu.fetchall ()
        if not r:
            return None

        # update the session activity to extend its life
        cu.execute('UPDATE session SET activity = datetime("now")'
                   ' WHERE key = ?', (cookie,))
        self.cx.commit()

        return User(* r [0])

    def getUserByKey(self, key):
        """Get a user by its ID."""
        cu = self.cx.cursor ()
        cu.execute ('SELECT key, email FROM user WHERE key = ?', (key,))

        r = cu.fetchall ()
        if not r:
            return None
        
        return User(*r[0])

    def getUserByEmail(self, email):
        """Get a user by its email."""
        cu = self.cx.cursor()
        cu.execute ('SELECT key, email FROM user WHERE email = ?', (
            email.lower(),))

        r = cu.fetchall()
        if not r:
            return None
        
        return User(*r[0])

    def getListsOwnedBy(self, user):
        """Get the list of wishlists owned by 'user'."""
        cu = self.cx.cursor()
        cu.execute('SELECT key, name, url, description, owner, showres, theme'
                   ' FROM wishlist WHERE owner = ?', (user.id,))

        return [(Wishlist(* r), False) for r in cu.fetchall()]

    def addToFriend(self, user, lst):
        """Add a wishlist to the favorites of a user."""
        cu = self.cx.cursor ()

        cu.execute('UPDATE friend SET visit = CURRENT_TIMESTAMP '
                    'WHERE list = ? AND user = ?', (
            lst.id, user.id))

        if cu.rowcount == 0:
            cu.execute('INSERT INTO friend (list, user) VALUES (?, ?)', (
                lst.id, user.id))

        self.cx.commit()

    def remove_from_friend(self, user, lst):
        """Stop following a list."""

        cu = self.cx.cursor ()

        cu.execute ('DELETE FROM friend '
                    'WHERE list = ? AND user = ?', (
            lst.id, user.id))

        self.cx.commit ()

    def getFriendLists (self, user):
        """Returh the favorite lists of 'user'."""
        cu = self.cx.cursor()
        cu.execute('SELECT w.modification, f.visit, w.key, w.name, w.url,'
                   ' w.description, w.owner, w.showres, w.theme FROM'
                   ' wishlist w, friend f'
                   ' WHERE w.key = f.list AND f.user = ?', (
            user.id,))

        return [(Wishlist(*r[2:]), r[0] > r[1]) for r in cu.fetchall()]

    def itemsForList(self, lst, with_reservations=False):
        """Return the items comprising a list.

        Items are sorted by score (decreasing), then modification time
        (decreasing).
        """
        q = 'SELECT i.key, i.list, i.title, i.description, i.url, i.score'

        cu = self.cx.cursor ()
        cu.execute (q + " FROM item i LEFT JOIN reservation r ON r.item = i.key"
                    " WHERE i.list = ? AND"
                    " (r.status IS NULL or r.status <> 'D')"
                    " ORDER BY score DESC, modification DESC", (
            lst.id,))

        items = [Item(*r) for r in cu.fetchall()]

        if not with_reservations:
            return items

        res = self.getListReservations (lst)

        for i in items:
            i.res = res.get (i.key, None)
        
        return items

    def reserveItem(self, user, item):
        """Let 'user' reserve 'item'."""
        cu = self.cx.cursor ()

        try:
            cu.execute ("INSERT INTO reservation (item, owner, status) "
                        "VALUES (?, ?, 'R')", (item.key, user.id))

        except (sqlite.OperationalError, sqlite.IntegrityError):
            self.cx.rollback ()
            return False
        
        self.cx.commit ()
        return True

    def isReserved (self, item):
        """Retuns whether 'item' is reserved."""
        cu = self.cx.cursor ()

        cu.execute ("SELECT status FROM reservation WHERE item = ?"
                    " AND status = 'R'", (item.key,))
        r = cu.fetchall ()

        return r != []
        
    def giveupItem(self, user, item):
        """Cancel the reservation on 'item' by 'user'."""
        cu = self.cx.cursor ()
        cu.execute ("DELETE FROM reservation WHERE item = ?"
                    " AND owner = ? AND status = 'R'", (item.key, user.id))

        self.cx.commit()
    
    def donatedItem(self, user, item):
        """Mark an item as donated."""
        if not user.email:
            return False

        cu = self.cx.cursor()
        try:
            cu.execute("UPDATE reservation SET status = 'D',"
                       " confirmation = CURRENT_TIMESTAMP "
                       "WHERE item = ? AND owner = ? AND status = 'R'", (
                item.key, user.id))
        except (sqlite.OperationalError, sqlite.IntegrityError):
            self.cx.rollback ()
            return False

        if not cu.rowcount:
            log.msg('_not_ resending "donated" email')
            return True

        # notify the list owner that the item has been marked as donated
        lst = self.getListByKey(item.list)
        owner = self.getUserByKey(lst.owner)
        if owner.email:
            body = u"""
Bonjour,

%(user)s nous informe que vous avez bien reçu votre souhait

 « %(souhait)s »

Si ce n'est pas le cas, vous pouvez remettre ce souhait sur votre
liste en cliquant sur le lien suivant :

 <%(url)s>

Meilleurs messages,

-- 
L'équipe de « Mes souhaits »
""" % { 'user': user.email,
        'souhait': item.title or u'sans nom',
        'url': '/'.join([self.base_url, lst.url, str(item.key)]) }
            
            self.build_and_send(owner.email,
                                u'[Mes souhaits] cadeau livré !',
                                body)
        return True

    def userChallengeFragment(self, user):
        """Return a text with a challenge link for a connected user."""

        cu = self.cx.cursor()
        cu.execute('SELECT challenge FROM challenge WHERE email = ?'
                   ' AND active = ?', (user.email, True))
        results = cu.fetchone()
        if not results:
            return ''
        
        return u"""
PS : vous pouvez utiliser le lien personnel ci-dessous pour retrouver
vos listes et réservations

  %(url)s
""" % {'url': self.base_url + '/challenge/' + results[0]}

    def getListReservations (self, lst):
        """Get all the reservation for the specified list."""
        cu = self.cx.cursor ()
        cu.execute ("SELECT i.key, r.owner, r.status, u.email"
                    " FROM reservation r, item i, user u"
                    " WHERE i.list = ? AND r.item = i.key AND u.key = r.owner"
                    " AND r.status = 'R'", (lst.id,))

        res = {}
        for key, owner, status, email in cu.fetchall ():
            res [key] = (owner, status, email)
            
        return res

    def getUserReservations(self, user):
        """Get all the reservations made by 'user'."""
        cu = self.cx.cursor ()
        cu.execute ("SELECT r.status, i.key, i.list, i.title, i.description,"
                    " i.url, i.score FROM item i, reservation r WHERE"
                    " r.owner = ? AND r.item = i.key AND r.status = 'R'", (
            user.id,))

        rs = []
        for r in cu.fetchall ():
            i = Item(*r[1:])
            i.res = (user.id, r[0], user.email)

            rs.append (i)
            
        return rs
        
    def getListItem(self, lst, item):
        """Get a single list item."""
        cu = self.cx.cursor()
        cu.execute ('SELECT key, list, title, description, url, score'
                    ' FROM item WHERE list = ? AND key = ?', (lst.id, item))

        r = cu.fetchall ()
        if r:
            return Item(*r[0])
        return None

    def addNewItem(self, lst, title, description, url):
        """Add a new item."""
        rowid = None
        for _ in xrange(16):
            lid = random.randint(1, 2**31)
            
            try:
                cu = self.cx.cursor ()
                cu.execute ('INSERT INTO item (key, list, title, description,'
                            ' url, score) VALUES (?, ?, ?, ?, ?, ?)', (
                    lid, lst.id, title, description, url, 2))
                self.cx.commit()
                rowid = cu.lastrowid
                break
            
            except(sqlite.OperationalError, sqlite.IntegrityError):
                self.cx.rollback()
        else:
            raise sqlite.OperationalError(
                'could not allocate item id. is the db full?')
        return rowid

    def editItem(self, item, title, description, url, score):
        """Edit an item."""
        cu = self.cx.cursor ()
        cu.execute('UPDATE item SET title = ?, description = ?, url = ?,'
                   ' score = ? WHERE key = ?', (
            title, description, url, score, item.key))
        cu.execute("DELETE FROM reservation WHERE item = ? AND status = 'D'",
                   (item.key,))
        self.cx.commit ()

    def destroyList(self, lst):
        """Destroy a list."""
        cu = self.cx.cursor ()

        # Warn all the people that have a reservation on this list
        cu.execute ("SELECT r.owner, i.title FROM reservation r, item i WHERE "
                    "r.item = i.key AND i.list = ? AND r.status = 'R'", (
            lst.id,))

        usermap = {}
        
        for owner, title in cu.fetchall():
            usermap.setdefault (owner, []).append (title)

        for owner, titles in usermap.items():
            owner = self.getUserByKey(owner)

            if not owner.email:
                continue
            
            titles = '\n - '.join (titles)
            
            info = {
                'titles': titles,
                'list': lst.name or u'sans titre',
                'challenge': self.userChallengeFragment(owner)
                }

            body = u"""\
Bonjour,

La liste « %(list)s » a été détruite par la personne qui s'en
occupe. Pour information, vous y aviez réservés les souhaits
suivants :

 - %(titles)s

%(challenge)s

Meilleurs messages,
-- 
L'équipe de « Mes souhaits »
""" % info
            
            self.build_and_send(
                owner.email,
                u'[Mes souhaits] la liste « %s » a été détruite' % (
                    info ['list'],), body)

        cu.execute ('DELETE FROM wishlist WHERE key = ?', (
            lst.id,))

        self.cx.commit ()
    
    def deleteItem(self, item, warn=True):
        """Delete one item."""
        cu = self.cx.cursor ()

        # CAUTION: we need to warn the user before deleting the item,
        # as the reservations will be discarded automatically when the
        # item is deleted.

        cu.execute ('SELECT owner FROM reservation '
                    'WHERE item = ?', (item.key,))

        r = cu.fetchall ()

        if r:
            lst   = self.getListByKey(item.list)
            owner = self.getUserByKey(r[0][0])
            
            # notify this person and remove his reservation
            if owner.email and warn:
            
                info = {
                    'challenge': self.userChallengeFragment(owner),
                    'name': item.title,
                    'list': lst.name,
                }

                body = u"""\
Bonjour,

Vous avez réservé le cadeau suivant :

  %(name)s

Il a été effacé par la personne qui s'occupe de la
liste « %(list)s ».

%(challenge)s

Meilleurs messages,

-- 
L'équipe de « Mes souhaits »
""" % info

                self.build_and_send(
                    owner.email,
                    u'[Mes souhaits] un cadeau réservé a été supprimé',
                    body)
                

        cu.execute ('DELETE FROM item WHERE key = ?', (item.key,))

        self.cx.commit ()
        
    def destroySession(self, cookie):
        """Destroy a session."""
        log.msg ('deleting session %s' % cookie)
        
        cu = self.cx.cursor ()
        cu.execute ('DELETE FROM session WHERE key = ?', (cookie,))
        self.cx.commit ()
        
        return cu.rowcount > 0


    def inviteFriend(self, realName, user, lsts, email, body):
        """Invite friends to lists."""

        email = validate_email(email)
        if not email:
            return False

        log.msg ('user %s invites %s on list %s' % (user.id, email, repr(lsts)))

        cu = self.cx.cursor ()

        # To invite someone on a list, we create a temporary user, and
        # populate him with a friend list and a challenge so that when
        # he logs in, everything is set up properly. This should work
        # for users that had no account and for people that had one
        # too.

        cu.execute ("INSERT INTO USER (email) VALUES (NULL)")
        userid = cu.lastrowid

        challenge = _make_cookie()
        
        cu.execute ('INSERT INTO challenge (challenge, email, user,'
                    ' session, active) VALUES (?, ?, ?, ?, ?)', (
            challenge, email, userid, '-', False))

        for lst in lsts:
            cu.execute ('INSERT INTO friend (list, user) VALUES (?, ?)', (
                lst.id, userid))


        info = {
            'url': self.base_url + '/challenge/' + challenge,
            'body': body,
            'email': user.email,
            'name': realName
            }

        body = u"""\
%(body)s


Voici votre clé personnelle pour consulter les souhaits de %(name)s.

  <%(url)s>

Ce message vous été envoyé de la part de %(name)s <%(email)s>
par le site <http://mes-souhaits.net/>.

""" % info

        self.build_and_send(email, u'Mes souhaits !', body,
                            from_name=realName, from_email=user.email)
        self.cx.commit ()
        return True

    def validate_challenge(self, challenge, session):
        """Check if a challenge is valid."""
        cu = self.cx.cursor ()
        cu.execute ('SELECT email, user FROM challenge WHERE challenge = ?', (
            challenge,))

        r = cu.fetchall ()
        if not r:
            return False

        email, user = r[0]

        # This challenge has been validated, mark it as active so that
        # it doesn't get garbage-collected.  Transfer it to the real
        # user, so that he can reuse it at will.
        cu.execute('UPDATE challenge SET active = ? WHERE challenge = ?', (
                True, challenge))

        # Now, we are sure that the user has the given email
        # address. If there is already one with this address, we need
        # to merge them (and discard the one without the address)
        cu.execute ('SELECT key FROM user WHERE email = ?', (
            email,))
        
        r = cu.fetchall()

        if not r:
            # No, we are really a new user. Just update our own record
            log.msg ('user %d: confirmed email %s' % (user, email))
            
            cu.execute ('UPDATE user SET email = ? WHERE key = ?', (
                email, user))

            real = user
            
        else:
            real, = r[0]

            # Transfer the session to the correct user. Needs to be
            # done _before_ the old user is deleted
            cu.execute('UPDATE session SET user = ? WHERE key = ?', (
                real, session))

            if real == user:
                log.msg('user %d: reconnecting with old challenge' % (user,))

            else:
                log.msg ('user %d: merging into user %d' % (user, real))

                # Transfer the challenge to the old user
                cu.execute('UPDATE challenge SET user = ? WHERE'
                           ' challenge = ?', (real, challenge))

                # ...and transfer the lists that might have been
                # created in-between
                cu.execute ('UPDATE wishlist SET owner = ? WHERE owner = ?', (
                    real, user))

                # By simply renaming the friend list, we might end up with
                # multiple copies of the same list
                cu.execute('SELECT list FROM friend WHERE user = ?', (
                    user,))
                for lid, in cu.fetchall():
                    cu.execute('SELECT COUNT(*) FROM friend WHERE'
                               ' list = ? AND user = ?', (lid, real))
                    if cu.fetchone()[0] == 0:
                        cu.execute('INSERT INTO friend(list, user)'
                                   ' VALUES(?, ?)', (lid, real))

                # Transfer the reservations made. But be careful: the user
                # might have reserved one of his own wishes while he was
                # not identified.
                cu.execute ('UPDATE reservation SET owner = ?'
                            ' WHERE owner = ?', (real, user))

                cu.execute ('SELECT r.key FROM reservation r, wishlist w, '
                            'item i WHERE r.owner = ? AND r.item = i.key AND'
                            ' i.list = w.key AND w.owner = r.owner', (real,))

                cu.executemany('DELETE FROM reservation WHERE key = ?',
                               cu.fetchall())

                cu.execute ('DELETE FROM user WHERE key = ?', (user,))


        # In the case of an invitation, the user might have no session
        # key at all for the moment
        self.cx.commit()
        
        return self.getUserByKey(real)
