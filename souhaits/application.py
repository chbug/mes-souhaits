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
"""Setup the webserver."""

from twisted.application import service
from twisted.application import internet

from nevow import appserver, vhost

from souhaits import core, pages

PORT = 7707

def prepare(debug):
    """Bind together the webserver components.

    Args:
      debug: bool, if True run in debug mode
    
    Returns:
      service.Application
    """
    application = service.Application("mes-souhaits")

    if debug:
        url = 'http://127.0.0.1:%d' % PORT
    else:
        url = 'http://mes-souhaits.net'

    srv = core.Service(url, debug=debug)    
    srv.setServiceParent(application)

    root = pages.RootPage(srv)
    root.putChild('vhost', vhost.VHostMonsterResource())
    
    site = appserver.NevowSite(root)

    server = internet.TCPServer(PORT, site)  # pylint: disable-msg=E1101
    server.setServiceParent(application)

    return application
