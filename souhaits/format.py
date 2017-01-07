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
"""Helper functions to format text in HTML.

This is used to format user's description without letting them type in
HTML.
"""
from nevow import tags as T

import re

_PARA_RE = re.compile (r'\n\s*\n')
_HTTP_RE = re.compile (r"^(.*?)((?:http|ftp)s?://[\w.-]+)"
                       "(/[-_.!~*';/?:@&=+$,\w\d%]+)?(.*)$")


def enrich(text):
    """Transform a single line of text into enriched HTML."""
    text = text.replace('\n', ' ')
    parts = []
    
    while True:
        match = _HTTP_RE.search(text)
        if not match:
            parts.append(text)
            break

        pre, site, arg, text = match.groups('')
        
        parts.append(pre)
        # pylint: disable-msg=E1101
        parts.append(T.a(href=site + arg, target="_blank")[site + '/...'])
        
    return parts


def format_description(text):
    """Transform a paragraph into HTML."""
    text = text.strip()
    # pylint: disable-msg=E1101
    return [T.p[enrich(part)] for part in _PARA_RE.split (text)]
    
