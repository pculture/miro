import re

# =============================================================================

# Purify a feed item data (usually its description) from ads. Returns the data
# untouched if no ad were found.
def purify(data):
    return _process(data, 'purify', data)

# Scrape ads from a feed item data (usually its description). Returns an empty
# string if no ad were found.
def scrape(data):
    return _process(data, 'scrape', '')

# =============================================================================

def _process(data, fkey, default):
    processed = None
    for funcs in FUNCS:
        process = funcs[fkey]
        processed = process(data)
        if processed is not None:
            break
    if processed is None:
        processed = default
    return processed

# =============================================================================

FEEDBURNER_AD_PATTERN = re.compile("""
    &lt;p&gt;                                                               # <p>
    &lt;a\shref="http://feeds\.feedburner\.com/~a/[^"]*"&gt;                # <a href="...">
    &lt;img\ssrc="http://feeds\.feedburner\.com/~a/[^"]*"\sborder="0"&gt;   # <img src="..." border="0">
    &lt;/img&gt;                                                            # </img>
    &lt;/a&gt;                                                              # </a>
    &lt;/p&gt;                                                              # </p>
    """, re.VERBOSE)
    
def _tryPurifyingFeedBurner(data):
    if FEEDBURNER_AD_PATTERN.search(data):
        return FEEDBURNER_AD_PATTERN.sub('', data)
    return None

def _tryScrapingFeedBurner(data):
    match = FEEDBURNER_AD_PATTERN.search(data)
    if match is not None:
        return match.group(0)
    return None

# =============================================================================

FUNCS = [
    {'purify': _tryPurifyingFeedBurner, 'scrape': _tryScrapingFeedBurner}
]
