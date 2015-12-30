# -*- coding: utf-8 -*-

import argparse
import bs4
import codecs
import collections
import csv
import hashlib
import operator
import os
import re
import requests
import requests_cache
import sys
import urllib
import urllib2

clean_titles = {
    '10.1007/978-1-4612-5142-2': 'SL_2(R)',
    '10.1007/BFb0058395': 'Les Foncteurs Dérivés de lim<- et leurs Applications en Théorie des Modules',
    '10.1007/BFb0096358': 'New Classes of L^P−spaces',
}

def cleanup_title(raw_title, doi):
    if doi in clean_titles:
        return clean_titles[doi].decode('utf8', 'strict')
    return raw_title.decode('utf8', 'strict')

def cleanup_authors(raw_authors):
    authors = raw_authors

    # Handle this as a special case to avoid catching initials.
    authors = re.sub(r"Jr\.([A-Z])", r'Jr., \1', authors)

    # This won't work for names that have mixed casing, but that seems
    # to be rare, except for initials.
    authors = re.sub(r"([^- '’.A-Z])([A-Z])", r'\1, \2', authors)
    return authors.decode('utf8', 'strict')

def build_full_title(raw_title, year, raw_authors, doi):
    title = cleanup_title(raw_title, doi)
    authors = cleanup_authors(raw_authors)
    doi_suffix = doi.split('/')[1]
    if len(authors) > 0:
        full_title = "%s - %s (%s) (%s)" % (title, authors, year, doi_suffix)
    else:
        full_title = "%s (%s) (%s)" % (title, year, doi_suffix)
    return full_title

def build_filename(raw_title, year, raw_authors, doi):
    full_title = build_full_title(raw_title, year, raw_authors, doi)
    filename = "%s.pdf" % (full_title)
    return filename

def build_pdf_url(doi):
    pdf_url = "http://link.springer.com/content/pdf/%s.pdf" % (doi)
    return pdf_url

def build_old_filenames(raw_title, year, raw_authors, doi):
    # v1, just glom the raw title, year, and raw authors together.
    old_filenames = []
    old_filenames.append(("%s - %s (%s).pdf" % (raw_title, raw_authors, year)).decode('utf8', 'strict'))

    # v2, clean up title and authors before glomming together
    # (ignoring the case where authors is empty).
    #
    # TODO: Handle old author-splitting method.
    title = cleanup_title(raw_title, doi)
    authors = cleanup_authors(raw_authors)
    old_filenames.append("%s - %s (%s).pdf" % (title, authors, year))

    # v3, omit dash when authors is empty.
    if len(authors) == 0:
        old_filenames.append("%s (%s).pdf" % (title, year))

    return old_filenames

def rename(raw_title, year, raw_authors, doi, url):
    candidate_filenames = build_old_filenames(raw_title, year, raw_authors, doi)
    filename = build_filename(raw_title, year, raw_authors, doi)

    # The DOI in the URL is usually escaped.
    t = url.split('/')
    pdf_filename = t[-1] + '.pdf'
    candidate_filenames.insert(0, pdf_filename)

    for candidate in candidate_filenames:
        if os.path.isfile(candidate):
            print "Found %s, renaming to %s" % (candidate, filename)
            os.rename(candidate, filename)
            break

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
                doi = link.get('doi')
                clean_title = re.sub(u'\s+', u' ', title)
                abs_url = u"http://link.springer.com%s" % url
                sections.append((clean_title, abs_url, doi))
                i += 1
    return sections

def list_files(crawl_session, raw_title, year, raw_authors, doi, url):
    full_title = build_full_title(raw_title, year, raw_authors, doi)

    pdf_url = build_pdf_url(doi)

    if url_exists(crawl_session, pdf_url):
        print u"[%s](%s)\n" % (full_title, pdf_url)
    else:
        sections = get_sections(crawl_session, url)
        i = 1
        link_strs = []
        for (title, url, doi) in sections:
            link_strs.append(u'<a href="%s" title="%s">[%d]</a>' % (url, title, i))
            i += 1

        all_link_str = u', '.join(link_strs)
        print (u"%s (%s)\n" % (full_title, all_link_str))

def compute_file_md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()

def file_matches_headers(path, headers, checkmd5):
    expected_size = int(headers['Content-Length'])
    size = os.path.getsize(path)
    if expected_size != size:
        return False
    if checkmd5:
        etag = headers['ETag']
        expected_md5 = etag.strip(' \t\n\r"').split(':')[0]
        md5 = compute_file_md5(path)
        if expected_md5 != md5:
            return False
    return True

def download_file(crawl_session, download_session, dry, checkmd5, url, path):
    # Always get response for now, to prime the cache.
    response = head_url(crawl_session, url)
    if os.path.exists(path):
        if file_matches_headers(path, response.headers, checkmd5):
            if checkmd5:
                print "Skipping \"%s\", already exists (sizes and md5s match)" % (path)
            else:
                print "Skipping \"%s\", already exists (sizes match)" % (path)
            return

    maxAttempts = 3

    print "Getting \"%s\" from %s" % (path, url)
    if not dry:
        (dirname, filename) = os.path.split(path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)

        for i in xrange(0, maxAttempts):
            r = download_session.get(url)
            with open(path, 'wb') as fd:
                for chunk in r.iter_content(512 * 1024):
                    fd.write(chunk)

            if file_matches_headers(path, response.headers, True):
                break

            print "Downloaded file %s didn't match headers; retrying (attempt %d)" % (path, i+1)
        else:
            # Failed all attempts.
            raise Exception("Downloaded file %s didn't match headers after %d attempts" % (path, maxAttempts))

def download(crawl_session, download_session, dry, checkmd5, raw_title, year, raw_authors, doi, url, index, count):
    full_title = build_full_title(raw_title, year, raw_authors, doi)
    filename = build_filename(raw_title, year, raw_authors, doi)

    pdf_url = build_pdf_url(doi)

    print "(%d/%d)" % (index+1, count),

    if url_exists(crawl_session, pdf_url):
        download_file(crawl_session, download_session, dry, checkmd5, pdf_url, filename)
    else:
        sections = get_sections(crawl_session, url)
        i = 1
        link_strs = []
        for (title, url, doi) in sections:
            if doi:
                doi_suffix = doi.split('/')[1]
                filename = "%d - %s (%s).pdf" % (i, title, doi_suffix)
            else:
                filename = "%d - %s.pdf" % (i, title)
            path = os.path.join(full_title, filename)
            download_file(crawl_session, download_session, dry, checkmd5, url, path)
            i += 1
    
def main():
    UTF8Writer = codecs.getwriter('utf8')
    sys.stdout = UTF8Writer(sys.stdout)

    parser = argparse.ArgumentParser(description='Get Springer books.')
    parser.add_argument('csvpaths', metavar='/path/to/search-results.csv', nargs='+', help='the csv file with search results')
    parser.add_argument('--rename', help='look for existing files and rename them', action='store_true')
    parser.add_argument('--list', help='build a markdown list of the titles and links', action='store_true')
    parser.add_argument('--dry', help="don't actually download any PDFs", action='store_true')
    parser.add_argument('--checkmd5', help="check the MD5s of existing PDFs", action='store_true')
    parser.add_argument('--socks5', help='SOCKS5 proxy to use (host:port)')
    args = parser.parse_args()

    if args.socks5:
        import socket
        import socks
        (host, port) = args.socks5.split(':')
        socks.set_default_proxy(socks.SOCKS5, host, int(port))
        socket.socket = socks.socksocket

    # Caches redirects, and also 404s so we cache url_exists queries.
    crawl_session = requests_cache.core.CachedSession('/tmp/get-springer-books-crawl-cache', allowable_methods=('GET', 'HEAD'), allowable_codes=(200,301,302,404))
    download_session = requests.session()
    
    books = []
    dois = set()
    for csvpath in args.csvpaths:
        with open(csvpath, 'rb') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                raw_title = row['Item Title']
                year = row['Publication Year']
                raw_authors = row['Authors']
                doi = row['Item DOI']
                url = row['URL']

                # Uniquify by DOI.
                if doi in dois:
                    continue
                dois.add(doi)

                book = {
                    'raw_title': raw_title,
                    'year': year,
                    'raw_authors': raw_authors,
                    'doi': doi,
                    'url': url,
                }
                books.append(book)

    def sort_key(book):
        title = cleanup_title(book['raw_title'], book['doi'])
        year = book['year']
        return (title, year)

    sorted_books = sorted(books, key=sort_key)

    i = 0
    for book in sorted_books:
        raw_title = book['raw_title']
        year = book['year']
        raw_authors = book['raw_authors']
        doi = book['doi']
        url = book['url']
        if args.rename:
            rename(raw_title, year, raw_authors, doi, url)
        elif args.list:
            list_files(crawl_session, raw_title, year, raw_authors, doi, url)
        else:
            download(crawl_session, download_session, args.dry, args.checkmd5, raw_title, year, raw_authors, doi, url, i, len(sorted_books))
        i += 1

if __name__ == "__main__":
    main()
