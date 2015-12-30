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

def head_url(crawl_session, url):
    request = crawl_session.prepare_request(requests.Request('HEAD', url))
    response = crawl_session.send(request, allow_redirects=True)
    if response.url.find('no-access=true') >= 0:
        # Don't cache this response.
        k = crawl_session.cache.create_key(request)
        crawl_session.cache.delete(k)
        raise Exception("access denied to %s" % url)
    return response

def url_exists(crawl_session, url):
    response = head_url(crawl_session, url)
    return response.status_code == 200

def get_sections(crawl_session, url):
    response = crawl_session.get(url, allow_redirects=True)
    soup = bs4.BeautifulSoup(response.text, 'lxml')
    toc_items = soup.find_all('li', class_="toc-item")
    sections = []
    i = 1
    for item in toc_items:
        links = item.find_all('a')
        for link in links:
            url = link.get('href')
            if url.endswith('.pdf'):
                title = link.get('title')
                clean_title = re.sub(u'\s+', u' ', title)
                abs_url = u"http://link.springer.com%s" % url
                sections.append((clean_title, abs_url))
                i += 1
    return sections

def list_files(crawl_session, raw_title, year, raw_authors, url):
    full_title = build_full_title(raw_title, year, raw_authors, url)
    ftu = full_title.decode('utf8', 'strict')

    pdf_url = build_pdf_url(url)

    if url_exists(crawl_session, pdf_url):
        print u"[%s](%s)\n" % (ftu, pdf_url)
    else:
        sections = get_sections(crawl_session, url)
        i = 1
        link_strs = []
        for section in sections:
            link_strs.append(u'<a href="%s" title="%s">[%d]</a>' % (section[1], section[0], i))
            i += 1

        all_link_str = u', '.join(link_strs)
        print (u"%s (%s)\n" % (ftu, all_link_str))

def download_file(crawl_session, download_session, dry, url, path):
    # Always get response for now, to prime the cache.
    response = head_url(crawl_session, url)
    if os.path.exists(path):
        expected_size = int(response.headers['Content-Length'])
        # TODO: Compare ETag to md5.
        size = os.path.getsize(path)
        if expected_size == size:
            print "Skipping \"%s\", already exists (sizes match)" % (path)
            return

    print "Getting \"%s\" from %s" % (path, url)
    if not dry:
        (dirname, filename) = os.path.split(path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)
        r = download_session.get(url)
        with open(path, 'wb') as fd:
            for chunk in r.iter_content(512 * 1024):
                fd.write(chunk)

def download(crawl_session, download_session, dry, raw_title, year, raw_authors, url):
    full_title = build_full_title(raw_title, year, raw_authors, url)
    ftu = full_title.decode('utf8', 'strict')
    filename = build_filename(raw_title, year, raw_authors, url)
    fu = filename.decode('utf8', 'strict')

    pdf_url = build_pdf_url(url)

    if url_exists(crawl_session, pdf_url):
        download_file(crawl_session, download_session, dry, pdf_url, fu)
    else:
        sections = get_sections(crawl_session, url)
        i = 1
        link_strs = []
        for section in sections:
            filename = "%d - %s.pdf" % (i, section[0])
            path = os.path.join(ftu, filename)
            download_file(crawl_session, download_session, dry, section[1], path)
            i += 1
    
def main():
    UTF8Writer = codecs.getwriter('utf8')
    sys.stdout = UTF8Writer(sys.stdout)

    parser = argparse.ArgumentParser(description='Get Springer books.')
    parser.add_argument('csvpaths', metavar='/path/to/search-results.csv', nargs='+', help='the csv file with search results')
    parser.add_argument('--rename', help='look for existing files and rename them', action='store_true')
    parser.add_argument('--list', help='build a markdown list of the titles and links', action='store_true')
    parser.add_argument('--dry', help="don't actually download any PDFs", action='store_true')
    parser.add_argument('--socks5', help='SOCKS5 proxy to use (host:port)')
    args = parser.parse_args()

    if args.socks5:
        import socket
        import socks
        (host, port) = args.socks5.split(':')
        socks.set_default_proxy(socks.SOCKS5, host, int(port))
        socket.socket = socks.socksocket

    crawl_session = requests_cache.core.CachedSession('/tmp/get-springer-books-crawl-cache', allowable_methods=('GET', 'HEAD'), allowable_codes=(200,301,302))
    download_session = requests.session()
    
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
            list_files(crawl_session, raw_title, year, raw_authors, url)
        else:
            download(crawl_session, download_session, args.dry, raw_title, year, raw_authors, url)

if __name__ == "__main__":
    main()
