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
