Prerequisites: requests, requests-cache, lxml, BeautifulSoup

```
pip install beautifulsoup4 lxml requests requests-cache
```

- Go to a search result page, like
http://link.springer.com/search?facet-series=%22666%22&facet-content-type=%22Book%22&showAll=false
.
- Make sure "Include Preview-Only content" is unchecked.
- Look for the down-arrow button on the upper right (next to the RSS
  icon) with the tooltip "Download search results (CSV)".
- Click it to download it somewhere on your local computer.
- Then run

```
python2.7 get-springer-books.py /path/to/SearchResults.csv
```

Note that the Springer website limits CSV results to 1000. You can
filter by year and download multiple batches and run

```
python2.7 get-springer-books.py /path/to/SearchResults1.csv /path/to/SearchResults2.csv ...
```

(Duplicate entries will be removed.)

If you already have a directory of PDFs with the ISBNs as filenames,
like 978-1-4684-0047-2.pdf , you can also run

```
python2.7 get-springer-books.py --rename /path/to/SearchResults.csv
```

to detect and rename those books.

Also, to build a markdown list, you can run

```
python2.7 get-springer-books.py --list /path/to/SearchResults.csv
```
