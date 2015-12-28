import csv
import os
import os.path
import re
import string
import sys
import urllib
import urlparse
import util

def main():
    with open(sys.argv[1], 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            raw_title = row['Item Title']
            title = util.cleanup_title(raw_title)

            year = row['Publication Year']

            raw_authors = row['Authors']
            authors = util.cleanup_authors(raw_authors)

            old_filename = "%s - %s (%s).pdf" % (raw_title, raw_authors, year)
            filename = "%s - %s (%s).pdf" % (title, authors, year)

            book_url = row['URL']
            pdf_url = re.sub(r'book', r'content/pdf', row['URL']) + ".pdf"

            t = pdf_url.split('/')
            pdf_filename = t[-1]

            if os.path.isfile(pdf_filename):
                print "Found %s, renaming to %s" % (pdf_filename, filename)
                os.rename(pdf_filename, filename)
            elif old_filename != filename and os.path.isfile(old_filename):
                print "Found %s, renaming to %s" % (old_filename, filename)
                os.rename(old_filename, filename)

if __name__ == "__main__":
    main()
