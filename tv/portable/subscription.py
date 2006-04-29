import re
import urllib2
import xml.dom.minidom

"""
This place's waiting for a little bit of documentation
"""

# =========================================================================

reflexiveAutoDiscoveryOpener = urllib2.urlopen

def parseFile(path):
    try:
        subscriptionFile = open(path, "r")
        content = subscriptionFile.read()
        subscriptionFile.close()
        return parseContent(content)
    except:
        pass

def parseContent(content):
    try:
        dom = xml.dom.minidom.parseString(content)
        root = dom.documentElement
        if root.nodeName == "rss":
            urls = _getSubscriptionsFromRSSChannel(root)
        elif root.nodeName == "feed":
            urls = _getSubscriptionsFromAtomFeed(root)
        elif root.nodeName == "opml":
            urls = _getSubscriptionsFromOPMLOutline(root)
        else:
            urls = None
        dom.unlink()
        return urls
    except:
        pass

# =========================================================================

def _getSubscriptionsFromRSSChannel(root):
    try:
        channel = root.getElementsByTagName("channel").pop()
        urls = _getSubscriptionsFromAtomLinkConstruct(channel)
        if urls is not None:
            return urls
        else:
            link = channel.getElementsByTagName("link").pop()
            href = link.firstChild.data
            return _getSubscriptionsFromReflexiveAutoDiscovery(href, "application/rss+xml")
    except:
        pass

def _getSubscriptionsFromAtomFeed(root):
    try:
        urls = _getSubscriptionsFromAtomLinkConstruct(root)
        if urls is not None:
            return urls
        else:
            link = _getAtomLink(root)
            rel = link.getAttribute("rel")
            if rel == "alternate":
                href = link.getAttribute("href")
                return _getSubscriptionsFromReflexiveAutoDiscovery(href, "application/atom+xml")
    except:
        pass

def _getSubscriptionsFromAtomLinkConstruct(node):
    try:
        link = _getAtomLink(node)
        if link.getAttribute("rel") in ("self", "start"):
            href = link.getAttribute("href")
            return [href]
    except:
        pass

def _getSubscriptionsFromReflexiveAutoDiscovery(url, ltype):
    urls = list()
    try:
        html = reflexiveAutoDiscoveryOpener(url).read()
        for match in re.findall("<link[^>]+>", html):
            altMatch = re.search("rel=\"alternate\"", match)
            typeMatch = re.search("type=\"%s\"" % re.escape(ltype), match)
            hrefMatch = re.search("href=\"([^\"]*)\"", match)
            if None not in (altMatch, typeMatch, hrefMatch):
                href = hrefMatch.group(1)
                urls.append(href)
    except:
        urls = None
    else:
        if len(urls) == 0:
            urls = None
    return urls

def _getAtomLink(node):
    return node.getElementsByTagNameNS("http://www.w3.org/2005/Atom", "link").pop()

# =========================================================================

def _getSubscriptionsFromOPMLOutline(root):
    return None

# =========================================================================
