import csv
import re
import sys
import urllib

def main():
    with open(sys.argv[1], 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            title = row['Item Title']
            year = row['Publication Year']
            authors = row['Authors']
            full_title = "%s - %s (%s)" % (title, authors, year)
            filename = full_title + ".pdf"

            book_url = row['URL']
            pdf_url = re.sub(r'book', r'content/pdf', row['URL']) + ".pdf"

            print "Getting \"%s\" from %s" % (full_title, pdf_url)
            response = urllib.urlretrieve(pdf_url, filename)

if __name__ == "__main__":
    main()
