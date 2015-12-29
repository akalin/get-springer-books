# -*- coding: utf-8 -*-

import argparse
import bs4
import codecs
import collections
import csv
import operator
import os
import re
import requests
import requests_cache
import sys
import urllib
import urllib2

clean_titles = {
    'http://link.springer.com/book/10.1007/978-1-4612-5142-2': 'SL_2(R)',
    'http://link.springer.com/book/10.1007/BFb0058395': 'Les Foncteurs Dérivés de lim<- et leurs Applications en Théorie des Modules',
    'http://link.springer.com/book/10.1007/BFb0096358': 'New Classes of L^P−spaces',
}

def cleanup_title(raw_title, url):
    if url in clean_titles:
        return clean_titles[url]
    return raw_title

def cleanup_authors(raw_authors):
    authors = raw_authors

    # Handle this as a special case to avoid catching initials.
    authors = re.sub(r"Jr\.([A-Z])", r'Jr., \1', authors)

    # This won't work for names that have mixed casing, but that seems
    # to be rare, except for initials.
    authors = re.sub(r"([^- '’.A-Z])([A-Z])", r'\1, \2', authors)
    return authors

def build_full_title(raw_title, year, raw_authors, url):
    title = cleanup_title(raw_title, url)
    authors = cleanup_authors(raw_authors)
    if len(authors) > 0:
        full_title = "%s - %s (%s)" % (title, authors, year)
    else:
        full_title = "%s (%s)" % (title, year)
    return full_title

def build_filename(raw_title, year, raw_authors, url):
    full_title = build_full_title(raw_title, year, raw_authors, url)
    filename = "%s.pdf" % (full_title)
    return filename

def rename(raw_title, year, raw_authors, url):
    old_filename = "%s - %s (%s).pdf" % (raw_title, raw_authors, year)
    filename = build_filename(raw_title, year, raw_authors, url)

    pdf_url = re.sub(r'book', r'content/pdf', url) + ".pdf"

    t = pdf_url.split('/')
    pdf_filename = t[-1]

    if os.path.isfile(pdf_filename):
        print "Found %s, renaming to %s" % (pdf_filename, filename)
        os.rename(pdf_filename, filename)
    elif old_filename != filename and os.path.isfile(old_filename):
        print "Found %s, renaming to %s" % (old_filename, filename)
        os.rename(old_filename, filename)

def build_pdf_url(url):
    pdf_url = re.sub(r'book', r'content/pdf', url) + ".pdf"
    return pdf_url

class HeadRequest(urllib2.Request):
    def get_method(self):
        return "HEAD"

def url_exists(url):
    response = requests.request('HEAD', url, allow_redirects=True)
    return response.status_code == 200

def list_files(raw_title, year, raw_authors, url):
    full_title = build_full_title(raw_title, year, raw_authors, url)
    ftu = full_title.decode('utf8', 'strict')

    pdf_url = build_pdf_url(url)

    if url_exists(pdf_url):
        print u"[%s](%s)\n" % (ftu, pdf_url)
    else:
        response = requests.get(url, allow_redirects=True)
        soup = bs4.BeautifulSoup(response.text, 'lxml')
        toc_items = soup.find_all('li', class_="toc-item")
        link_strs = []
        for item in toc_items:
            links = item.find_all('a')
            for link in links:
                url = link.get('href')
                if url.endswith('.pdf'):
                    title = link.get('title')
                    clean_title = re.sub(u'\s+', u' ', title)
                    abs_url = u"http://link.springer.com%s" % url
                    link_strs.append(u"[%s](%s)" % (clean_title, abs_url))

        all_link_str = u', '.join(link_strs)
        print (u"%s (%s)\n" % (ftu, all_link_str))

def download(raw_title, year, raw_authors, url):
    filename = build_filename(raw_title, year, raw_authors, url)

    pdf_url = re.sub(r'book', r'content/pdf', url) + ".pdf"

    print "Getting \"%s\" from %s" % (filename, pdf_url)
    urllib.urlretrieve(pdf_url, filename)
    
def main():
    UTF8Writer = codecs.getwriter('utf8')
    sys.stdout = UTF8Writer(sys.stdout)

    requests_cache.install_cache('/tmp/get-springer-books-cache', allowable_methods=('GET', 'HEAD'))

    parser = argparse.ArgumentParser(description='Get Springer books.')
    parser.add_argument('csvpaths', metavar='/path/to/search-results.csv', nargs='+', help='the csv file with search results')
    parser.add_argument('--rename', help='look for existing files and rename them', action='store_true')
    parser.add_argument('--list', help='build a markdown list of the titles and links', action='store_true')
    args = parser.parse_args()

    books = []
    urls = set()
    for csvpath in args.csvpaths:
        with open(csvpath, 'rb') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                raw_title = row['Item Title']
                year = row['Publication Year']
                raw_authors = row['Authors']
                url = row['URL']

                # Uniquify by URL.
                if url in urls:
                    continue
                urls.add(url)

                book = {
                    'raw_title': raw_title,
                    'year': year,
                    'raw_authors': raw_authors,
                    'url': url,
                }
                books.append(book)

    def sort_key(book):
        title = cleanup_title(book['raw_title'], book['url'])
        year = book['year']
        return (title, year)

    sorted_books = sorted(books, key=sort_key)

    for book in sorted_books:
        raw_title = book['raw_title']
        year = book['year']
        raw_authors = book['raw_authors']
        url = book['url']
        if args.rename:
            rename(raw_title, year, raw_authors, url)
        elif args.list:
            list_files(raw_title, year, raw_authors, url)
        else:
            download(raw_title, year, raw_authors, url)

if __name__ == "__main__":
    main()
