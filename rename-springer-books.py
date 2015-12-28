import csv
import os
import os.path
import re
import string
import sys
import urllib
import urlparse

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

def main():
    with open(sys.argv[1], 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            raw_title = row['Item Title']
            title = cleanup_title(raw_title)

            year = row['Publication Year']

            raw_authors = row['Authors']
            authors = cleanup_authors(raw_authors)

            old_result_filename = "%s - %s (%s).pdf" % (raw_title, raw_authors, year)
            result_filename = "%s - %s (%s).pdf" % (title, authors, year)

            book_url = row['URL']
            pdf_url = re.sub(r'book', r'content/pdf', row['URL']) + ".pdf"

            t = pdf_url.split('/')
            pdf_filename = t[-1]

            if os.path.isfile(pdf_filename):
                print "Found %s, renaming to %s" % (pdf_filename, result_filename)
                os.rename(pdf_filename, result_filename)
            elif old_result_filename != result_filename and os.path.isfile(old_result_filename):
                print "Found %s, renaming to %s" % (old_result_filename, result_filename)
                os.rename(old_result_filename, result_filename)

if __name__ == "__main__":
    main()
