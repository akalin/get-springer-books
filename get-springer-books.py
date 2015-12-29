import argparse
import csv
import os
import re
import sys
import urllib

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

def rename(raw_title, year, raw_authors, url):
    title = cleanup_title(raw_title)
    authors = cleanup_authors(raw_authors)
    old_filename = "%s - %s (%s).pdf" % (raw_title, raw_authors, year)
    filename = "%s - %s (%s).pdf" % (title, authors, year)

    pdf_url = re.sub(r'book', r'content/pdf', url) + ".pdf"

    t = pdf_url.split('/')
    pdf_filename = t[-1]

    if os.path.isfile(pdf_filename):
        print "Found %s, renaming to %s" % (pdf_filename, filename)
        os.rename(pdf_filename, filename)
    elif old_filename != filename and os.path.isfile(old_filename):
        print "Found %s, renaming to %s" % (old_filename, filename)
        os.rename(old_filename, filename)

def download(raw_title, year, raw_authors, url):
    title = cleanup_title(raw_title)
    authors = cleanup_authors(raw_authors)
    filename = "%s - %s (%s).pdf" % (title, authors, year)

    pdf_url = re.sub(r'book', r'content/pdf', url) + ".pdf"

    print "Getting \"%s\" from %s" % (filename, pdf_url)
    urllib.urlretrieve(pdf_url, filename)

def main():
    parser = argparse.ArgumentParser(description='Get Springer books.')
    parser.add_argument('csvfile', metavar='/path/to/search-results.csv', help='the csv file with search results')
    parser.add_argument('--rename', help='look for existing files and rename them', action='store_true')
    args = parser.parse_args()

    with open(args.csvfile, 'rb') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            raw_title = row['Item Title']
            year = row['Publication Year']
            raw_authors = row['Authors']
            url = row['URL']
            if args.rename:
                rename(raw_title, year, raw_authors, url)
            else:
                download(raw_title, year, raw_authors, url)

if __name__ == "__main__":
    main()
