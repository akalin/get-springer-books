import csv
import re
import sys
import urllib
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

            filename = "%s - %s (%s).pdf" % (title, authors, year)

            book_url = row['URL']
            pdf_url = re.sub(r'book', r'content/pdf', row['URL']) + ".pdf"

            print "Getting \"%s\" from %s" % (filename, pdf_url)
            response = urllib.urlretrieve(pdf_url, filename)

if __name__ == "__main__":
    main()
