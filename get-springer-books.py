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
import time
import urllib
import urllib2

clean_titles = {
    '10.1007/978-1-4612-5142-2': 'SL_2(R)',
    '10.1007/BFb0058395': 'Les Foncteurs Dérivés de lim<- et leurs Applications en Théorie des Modules',
    '10.1007/BFb0096358': 'New Classes of L^P−spaces',
    '10.1007/BFb0058801': 'Séminaire Bourbaki vol. 1968-69 Exposés 347-363',
    '10.1007/BFb0058820': 'Séminaire Bourbaki vol. 1969-70 Exposés 364–381',
    '10.1007/BFb0058692': 'Séminaire Bourbaki vol. 1970-71 Exposés 382–399',
    '10.1007/BFb0069272': 'Séminaire Bourbaki vol. 1971-72 Exposés 400–417',
    '10.1007/BFb0058692': 'Séminaire Bourbaki vol. 1970-71 Exposés 382–399',
    '10.1007/BFb0057298': 'Séminaire Bourbaki vol. 1972-73 Exposés 418–435',
    '10.1007/BFb0066360': 'Séminaire Bourbaki vol. 1973-74 Exposés 436–452',
    '10.1007/BFb0080053': 'Séminaire Bourbaki vol. 1974-75 Exposés 453–470',
    '10.1007/BFb0096057': 'Séminaire Bourbaki vol. 1975-76 Exposés 471–488',
    '10.1007/BFb0070748': 'Séminaire Bourbaki vol. 1976-77 Exposés 489–506',
    '10.1007/BFb0069969': 'Séminaire Bourbaki vol. 1977-78 Exposés 507–524',
    '10.1007/BFb0096231': 'Séminaire Bourbaki vol. 1978-79 Exposés 525 – 542',
    '10.1007/BFb0089923': 'Séminaire Bourbaki vol. 1979-80 Exposés 543 – 560',
    '10.1007/BFb0097185': 'Séminaire Bourbaki vol. 1980-81 Exposés 561–578',
    '10.1007/BFb0089463': 'Séminaire de Probabilités XIV 1978-79',
    '10.1007/BFb0075834': 'Séminaire de Probabilités XIX 1983-84',
    '10.1007/BFb0088355': 'Séminaire de Probabilités XV 1979-80',
    '10.1007/BFb0092765': 'Séminaire de Probabilités XVI 1980-81',
    '10.1007/BFb0092646': 'Séminaire de Probabilités XVI, 1980-81 Supplément: Géométrie Différentielle Stochastique',
    '10.1007/BFb0068294': 'Séminaire de Probabilités XVII 1981-82',
    '10.1007/BFb0100027': 'Séminaire de Probabilités XVIII 1982-83',
    '10.1007/BFb0075705': 'Séminaire de Probabilités XX 1984-85',
    '10.1007/BFb0083752': 'Séminaire de Probabilités XXIV 1988-89',
    '10.1007/BFb0077395': 'Séminaire Pierre Lelong (Analyse) Année 1973-74',
    '10.1007/BFb0077993': 'Séminaire Pierre Lelong (Analyse) Année 1974-75',
    '10.1007/BFb0091458': 'Séminaire Pierre Lelong (Analyse) Année 1975-76',
    '10.1007/BFb0097744': 'Séminaire Pierre Lelong - Henri Skoda (Analyse) Années 1978-79',
    '10.1007/BFb0063241': 'Séminaire Pierre Lelong — Henri Skoda (Analyse) Année 1976-77',
    '10.1007/BFb0097040': 'Séminaire Pierre Lelong-Henri Skoda (Analyse) Années 1980-81',
}

def cleanup_title(raw_title, doi):
    if doi in clean_titles:
        return clean_titles[doi].decode('utf8', 'strict')
    return raw_title.decode('utf8', 'strict')

too_many_authors = {
    '10.1007/BFb0070748',
}

def cleanup_authors(raw_authors, doi):
    authors = raw_authors

    if doi in too_many_authors:
        return u''

    # Handle this as a special case to avoid catching initials.
    authors = re.sub(r"Jr\.([A-Z])", r'Jr., \1', authors)

    # This won't work for names that have mixed casing, but that seems
    # to be rare, except for initials.
    authors = re.sub(r"([^- '’.A-Z])([A-Z])", r'\1, \2', authors)
    return authors.decode('utf8', 'strict')

def build_full_title(raw_title, year, raw_authors, doi):
    title = cleanup_title(raw_title, doi)
    authors = cleanup_authors(raw_authors, doi)
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
    authors = cleanup_authors(raw_authors, doi)
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

clean_section_titles = {
    '10.1007/BFb0060880': u'Functional interpretation of classical (AC)o-, (ωAC)-analysis with (ER)-qf and functional interpretation in the narrower sense of Heyting-analysis plus (ER)-qf, (MP), ... in T⋃BR',
    '10.1007/BFb0091368': u'Evaporation and condensation of a rarefied gas between its two parallel plane condensed phases with different temperatures and negative temperature-gradient phenomenon',
    '10.1007/BFb0077580': u'Asymptotic expressions for the remainders associated to expansions of type $$\\sum\\limits_{n = 0}^\\infty { c_n \\frac{{z^n }}{{n!}}, } \\sum\\limits_{n = 0}^\\infty { c_n z^n and } \\sum\\limits_{n = 0} { c_n n!z^n }$$',
    '10.1007/BFb0077925': u'A solution of the integral equation $$\\int_0^\\infty {(\\sin (\\frac{\\pi }{4} + \\theta )e^{ - \\theta y} + \\sin (\\frac{\\pi }{4} - \\theta )e^{\\theta y} )\\pi (x,y)dy = \\surd 2 cosh \\theta x}$$ in convolution form',
    '10.1007/BFb0099702': u'Der Begriff der charakteristischen Funktion. Nevanlinnas Charakterisierung rationaler Stellen',
    '10.1007/BFb0089525': u'On the boundary map K3(Δ over I) → K2(Δ,I)',
    '10.1007/BFb0089528': u'On a conjecture concerning K*(ZZ over p2)',
    '10.1007/BFb0083034': u'The RO(G)-graded equivariant ordinary cohomology of complex projective spaces with linear ℤ over p actions',
    '10.1007/BFb0087506': u'Lannes\' division functors on summands of H*(B(Z over p)r)',
    '10.1007/BFb0077797': u'Maps of BZ over pZ to BG',
    '10.1007/BFb0082258': u'Divisorial cycles on a normal projective variety V over k (dim(V)=r≥1)',
    '10.1007/BFb0096456': u'The zeros of Hurwitz\'s zeta-function on σ=1 over 2',
    '10.1007/BFb0093310': u'Uniform twin-convergence regions for continued fractions K(an over 1)',
    '10.1007/BFb0093315': u'Parameterizations and factorizations of element regions for continued fractions K(an over 1)',
    '10.1007/BFb0093305': u'Convergence acceleration for continued fractions K(an over 1) with lim an=0',
    '10.1007/BFb0093306': u'Truncation error analysis for continued fractions K(an over 1) where $$\\sqrt {\\left| {a_n } \\right|} + \\sqrt {\\left | {a_{n - 1} } \\right|} < 1$$',
    '10.1007/BFb0093307': u'A method for convergence acceleration of continued fractions K(an over 1)',
    '10.1007/BFb0075943': u'On the convergence of a certain class of continued fractions K(an over 1) with an→∞',
    '10.1007/BFb0075934': u'On the convergence of limit periodic continued fractions K(an over 1), where an→−1 over 4. Part II',
    '10.1007/BFb0075935': u'A theorem on simple convergence regions for continued fractions K(an over 1)',
    '10.1007/BFb0075937': u'Oval convergence regions and circular limit regions for continued fractions K(an over 1)',
    '10.1007/BFb0062370': u'Slow or fast decoupling for linear boundary value problems',
    '10.1007/BFb0085399': u'Universal unfolding of a singularity of a symmetric vector field with 7-jet C∞-equivalent to y ∂_x+(±x3 ±x6y) ∂_y',
    '10.1007/BFb0069190': u'A problem in the design of electrical circuits, a generalized subadditive inequality and the recurrence relation j(n,m)=j([n over 2],m)+j([n+1 over 2],m)+j(n,m–1)',
    '10.1007/BFb0099365': u'In characteristic p=2 the Veronese variety Vm ⊂ ℙm(m+3) over 2 and each of its generic projection is set-theoretic complete intersection',
    '10.1007/978-3-540-44885-3_6': u'6. Anisotropic linear over superlinear growth in the scalar case',
    '10.1007/BFb0075653': u'Remarks on the injectivity radius estimate for almost 1 over 4-pinched manifolds',
    '10.1007/BFb0073501': u'K over J inequalities and limiting embedding theorems',
    '10.1007/BFb0089866': u'L2(Γ over G, X)',
    '10.1007/BFb0089868': u'Spectral decomposition of eL2(Γ over G,X)',
    '10.1007/BFb0069227': u'Algebraic k-theory with coefficients $$\\underset{\\raise0.3em\\hbox{$\\smash{\\scriptscriptstyle\\thicksim}$}}{Z}$$  over p',
    '10.1007/BFb0092021': u'Classical 1 over 2 spin particles interacting with gravitational fields: A supersymmetric model',
    '10.1007/BFb0097473': u'Produits star sur certains G over K Kähleriens. equation de Yang-Baxter et produits star sur G',
    '10.1007/BFb0083630': u'Compact manifolds with 1 over 4-pinched negative curvature',
    '10.1007/BFb0101504': u'Vector fields and cohomology of G over P',
    '10.1007/BFb0076176': u'Some finite groups which appear as gal L over K, where K⊂Q(μn)',
    '10.1007/BFb0086588': u'Le noyau de la chaleur sur les espaces symetriques U(p,q) over U(p)×U(q)',
    '10.1007/BFb0064139': u'Comparison between I(RT:ST), WT(HN over HS+N), and JT(N, S+N) for gaussian signals and noise',
    '10.1007/BFb0062095': u'Differential or algebraic systems and matrix pencils',
    '10.1007/BFb0065296': u'Modular forms of weight 1 over 2',
    '10.1007/BFb0072655': u'Fas multigrid employing ILU or SIP smoothing: A robust fast solver for 3D transonic potential flow',
    '10.1007/BFb0090406': u'K-finite joint eigenfunctions of U(g)K on a non-riemannian semisimple symmetric space G over H',
    '10.1007/BFb0087923': u'Spherical functions in spin0(1,d) over Spin(d−1) for d=2,4 and 8',
    '10.1007/BFb0077579': u'Asymptotic expressions for the remainders associated to expansions of type $$\\sum\\limits_{n = 0}^\\infty { c_n \\frac{{z^n }}{{n!}}, } \\sum\\limits_{n = 0}^\\infty { c_n z^n and } \\sum\\limits_{n = 0} { c_n n!z^n }$$',
    '10.1007/BFb0064888': u'Automatic detection and treatment of oscillatory and or stiff ordinary differential equations',
    '10.1007/BFb0058574': u'Structure of (D) for D with c=1 over 2',
    '10.1007/BFb0090907': u'Analysis of a recursive 5-point over 9-point factorization method',
    '10.1007/BFb0068793': u'Relative consistency proof of ZTN with respect to ZTi over IN*',
    '10.1007/BFb0072415': u'On the convergence of limit periodic continued fractions K(an over 1), where a1 → −1 over 4',
    '10.1007/BFb0072463': u'Convergence acceleration for continued fractions K(an over 1), where an → ∞',
    '10.1007/BFb0076225': u'On the ordering of classes in high or low hierarchies',
    '10.1007/BFb0068428': u'Le Foncteur $$\\underline {Pic} _{\\tilde X over k}^\\# $$ Pour Un R-Schéma Propre X',
    '10.1007/BFb0058839': u'Table par noms d\'Auteurs [Séminaire Bourbaki, 1967-68 à 1969-70, Exposés 331 à 381]',
    '10.1007/BFb0064855': u'Relations entre la série de Betti d\'un anneau local de Gorenstein R et celle de l\'anneau R over Socle R',
    '10.1007/BFb0064842': u'Decomposition of exterior and symmetric powers of indecomposable Z over pZ-modules in characteristic p and relations to invariants',
    '10.1007/BFb0077407': u'Rectificatif concernant l’expose: “Un théorème d’image directe propre”, publié dans le Séminaire Pierre Lelong, 1972-73, N° 410',
    '10.1007/BFb0093747': u'Cellular or homology complexes: methods',
    '10.1007/BFb0072245': u'Der Grenzefall k=n+j+1 over 2',
    '10.1007/BFb0072246': u'Das holomorphe diskrete Spektrum von L 2(Γ n over G)',
    '10.1007/BFb0060047': u'On meromorphic solutions of the difference equation y(x+1)=y(x)+1+λ over y(x)',
    '10.1007/BFb0095839': u'The classification of three-dimensional homogeneous complex manifolds X=G over H where G is a complex lie group',
    '10.1007/BFb0095840': u'The classification of three-dimensional homogeneous complex manifolds X=G over H where G is a real lie group',
    '10.1007/BFb0072815': u'Free (ℤ over 2)k-actions and a problem in commutative algebra',
}

def cleanup_section_title(raw_title, doi):
    if doi in clean_section_titles:
        return clean_section_titles[doi]
    clean_title = re.sub(u'\s+', u' ', raw_title)
    return clean_title

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
                clean_title = cleanup_section_title(title, doi)
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

def compare_file_with_headers(path, headers, checkmd5):
    expected_size = int(headers['Content-Length'])
    if checkmd5:
        etag = headers['ETag']
        expected_md5 = etag.strip(' \t\n\r"').split(':')[0]
        expected = (expected_size, expected_md5)
    else:
        expected = expected_size

    size = os.path.getsize(path)
    if checkmd5:
        md5 = compute_file_md5(path)
        actual = (size, md5)
    else:
        actual = size

    return (expected, actual)

def download_file(crawl_session, download_session, dry, checkmd5, url, path):
    # Always get response for now, to prime the cache.
    response = head_url(crawl_session, url)
    if os.path.exists(path):
        (expected, actual) = compare_file_with_headers(path, response.headers, checkmd5)
        if expected == actual:
            if checkmd5:
                print "Skipping \"%s\", already exists (sizes and md5s match)" % (path)
            else:
                print "Skipping \"%s\", already exists (sizes match)" % (path)
            return
        else:
            print "File exists, but doesn't match headers: expected %s, got %s" % (expected, actual)

    maxAttempts = 3
    delay = 3

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

            (expected, actual) = compare_file_with_headers(path, response.headers, True)
            if expected == actual:
                break

            # When the above test fails, it's usually because of a
            # different MD5. But the etag MD5 is the erroneous one --
            # trying again (with a brand-new invocation of the script)
            # gets the correct one!
            print "Downloaded file %s didn't match headers (expected %s, got %s), sleeping for %d seconds and retrying (attempt %d)" % (path, expected, actual, delay, i+1)
            time.sleep(delay)
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
    parser.add_argument('--crawl-cache', help='Location of crawl cache',
                        default='/tmp/get-springer-books-crawl-cache')
    args = parser.parse_args()

    if args.socks5:
        import socket
        import socks
        (host, port) = args.socks5.split(':')
        socks.set_default_proxy(socks.SOCKS5, host, int(port))
        socket.socket = socks.socksocket

        print "Using crawl cache at %s" % (args.crawl_cache)

    # Caches redirects, and also 404s so we cache url_exists queries.
    crawl_session = requests_cache.core.CachedSession(args.crawl_cache, allowable_methods=('GET', 'HEAD'), allowable_codes=(200,301,302,404))
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
