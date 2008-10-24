import urllib

from miro import app
from miro import config
from miro import prefs
from miro import xhtmltools


def share_email(item):
    url = "http://www.videobomb.com/index/democracyemail?url=%s" % (
        urllib.quote(item.file_url))
    app.widgetapp.open_url(url)

def share_video_bomb(item):
    param_list = {}
    param_list["title"] = item.name
    param_list["info_url"] = item.permalink
    param_list["hookup_url"] = item.payment_link
    if item.feed_url:
        param_list['rss_url'] = item.feed_url
    if item.thumbnail_url is not None:
        param_list["thumb_url"] = item.thumbnail_url

    # FIXME: add "explicit" and "tags" parameters when we get them in item

    param_string = ""
    glue = '?'

    # This should be first, since it's most important.
    url = item.file_url
    url.encode('utf-8', 'replace')
    if (not url.startswith('file:')):
        param_string = "?url=%s" % xhtmltools.urlencode(url)
        glue = '&'

    for key, value in param_list.iteritems():
        if value:
            param_string = "%s%s%s=%s" % (
                param_string, glue, key, xhtmltools.urlencode(value))

    # This should be last, so that if it's extra long it 
    # cut off all the other parameters
    description = item.description
    if description:
        param_string = "%s%sdescription=%s" % (
            param_string, glue,
            xhtmltools.urlencode(description))
    url = config.get(prefs.VIDEOBOMB_URL) + param_string
    app.widgetapp.open_url(url)

def share_delicious(item):
    url = "http://del.icio.us/post?v=4&noui&jump=close&url=%s&title=%s" % (
        urllib.quote(item.file_url), urllib.quote(item.name))
    app.widgetapp.open_url(url)

def share_digg(item):
    url = "http://digg.com/submit/?url=%s&media=video" % (
        urllib.quote(item.file_url))
    app.widgetapp.open_url(url)

def share_reddit(item):
    url = "http://reddit.com/submit?url=%s&title=%s" % (
        urllib.quote(item.file_url), urllib.quote(item.name))
    app.widgetapp.open_url(url)
