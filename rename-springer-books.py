import csv
import os
import os.path
import re
import sys
import urllib
import urlparse

def main():
    with open(sys.argv[1], 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            title = row['Item Title']
            year = row['Publication Year']
            authors = row['Authors']
            full_title = "%s - %s (%s)" % (title, authors, year)
            result_filename = full_title + ".pdf"

            book_url = row['URL']
            pdf_url = re.sub(r'book', r'content/pdf', row['URL']) + ".pdf"

            t = pdf_url.split('/')
            pdf_filename = t[-1]

            if os.path.isfile(pdf_filename):
                print "Found %s, renaming to %s" % (pdf_filename, result_filename)
                os.rename(pdf_filename, result_filename)
            else:
                print "Didn't find %s, skipping" % (pdf_filename)

if __name__ == "__main__":
    main()
