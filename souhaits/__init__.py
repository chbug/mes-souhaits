"""
 - static/ and templates/ are extra data files needed for the application.
 - web/ is a sub-package containing the web pages

"""
import os

_PREFIX = os.path.dirname(__file__)

TEMPLATE_DIR = os.path.join(_PREFIX, 'templates')
STATIC_DIR = os.path.join(_PREFIX, 'static')
