import re

def cleanup_title(raw_title):
    # Special case for Serge Lang's book:
    # http://link.springer.com/book/10.1007/978-1-4612-5142-2 .
    if raw_title == "SL\n          2(R)":
        return "SL_2(R)"
    return raw_title

def cleanup_authors(raw_authors):
    # Author names are just concatenated together. Try and split them
    # up. This won't work for names that have mixed casing, though.
    return re.sub(r'([a-z])([A-Z])', r'\1, \2', raw_authors)
