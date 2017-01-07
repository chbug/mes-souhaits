"""Implementation of the webpages."""

def arg(req, name, default=''):
    """Extract a single argument from a request, as a unicode string."""
    value = req.args.get(name, [default])[0].strip()
    if isinstance(value, str):
        try:
            value = value.decode('utf-8')
        except UnicodeError:
            value = value.decode('latin-1')
    return value
    
