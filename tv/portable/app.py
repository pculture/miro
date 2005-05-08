from xml.dom.minidom import parse, parseString
import frontend
import template
import database
import item
import downloader
import re
import random
import copy
import resource
import cgi
import types
import feed
import traceback
import config
import datetime
import autodler

###############################################################################
#### TemplateDisplay: a HTML-template-driven right-hand display panel      ####
###############################################################################

class TemplateDisplay(frontend.HTMLDisplay):

    def __init__(self, templateName, data, homeTemplate=None, homeData=None, frameHint=None):
	"'templateName' is the name of the inital template file. 'data' is keys for the template. If given, 'homeTemplate' and 'homeData' indicate the template to return to when onSelectedTabClicked is called."

	self.templateName = templateName
	self.templateData = data
	self.homeTemplate = homeTemplate
	self.homeData = homeData
	(html, self.templateHandle) = template.fillTemplate(templateName, data, lambda js:self.execJS(js))
 	frontend.HTMLDisplay.__init__(self, html, frameHint=frameHint)

    def onSelectedTabClicked(self):
	if self.homeTemplate:
	    self.currentFrame.setTabListActive(True)
	    self.currentFrame.selectDisplay(TemplateDisplay(self.homeTemplate, self.homeData, frameHint=self.currentFrame))

    def onURLLoad(self, url):
	print url
	try:
	    # Switching to a new template in this tab
	    match = re.compile(r"^template:(.*)$").match(url)
	    if match:
		# Graphically indicate that we're not at the home
		# template anymore
		self.currentFrame.setTabListActive(False)
		
		# Compute where onSelectedTabClicked should go when it
		# is pressed in the new display
		newHomeTemplate = None
		newHomeData = None
		if self.homeTemplate:
		    newHomeTemplate = self.homeTemplate
		    newHomeData = self.homeData
		else:
		    newHomeTemplate = self.templateName
		    newHomeData = self.templateData

		# Switch to new template. It get the same variable
		# dictionary as we have.
		self.currentFrame.selectDisplay(TemplateDisplay(match.group(1), self.templateData, newHomeTemplate, newHomeData, frameHint=self.currentFrame))
		return False
		
	    if url == "action:goHome":
		self.onSelectedTabClicked()
		return False

	    match = re.compile(r"^action:setViewFilter\?(.*)$").match(url)
	    if match:
		# Parse arguments
		(name, fieldKey, funcKey, parameter, invert) = getURLParameters('setViewFilter', match.group(1), 'viewName', 'fieldKey', 'functionKey', 'parameter', 'invert')
		invert = stringToBoolean(invert)
	    	    
		# Change the filter
		namedView = self.templateHandle.findNamedView(name)
		namedView.setFilter(fieldKey, funcKey, parameter, invert)
		database.defaultDatabase.recomputeFilters()
		return False

	    match = re.compile(r"^action:changeFeedSettings\?(.*)$").match(url)
	    if match:
		# Parse arguments
		(myFeed,maxnew,fallbehind,automatic,expireDays,expireHours,expire,getEverything) = getURLParameters('setViewFilter', match.group(1), 'feed', 'maxnew', 'fallbehind', 'automatic', 'expireDays','expireHours','expire','getEverything')

		database.defaultDatabase.saveCursor()
		for obj in database.defaultDatabase:
		    if obj.getID() == int(myFeed):
			obj.saveSettings(automatic,maxnew,fallbehind,expire,expireDays,expireHours,getEverything)
			break
		database.defaultDatabase.restoreCursor()


	    match = re.compile(r"^action:setViewSort\?(.*)$").match(url)
	    if match:
		# Parse arguments
		(name, fieldKey, funcKey, reverse) = getURLParameters('setViewSort', match.group(1), 'viewName', 'fieldKey', 'functionKey', 'reverse')
		reverse = stringToBoolean(reverse)
		
		# Change the sort
		namedView = self.templateHandle.findNamedView(name)
		namedView.setSort(fieldKey, funcKey, reverse)
		database.defaultDatabase.recomputeFilters()
		return False

	    match = re.compile(r"^action:playFile\?(.*)$").match(url)
	    if match:
		# Parse arguments
		(filename, ) = getURLParameters('playFile', match.group(1), 'filename')
		print "Playing "+filename
		# Use a quick hack to play the file. (NEEDS)
		frontend.playVideoFileHack(filename)
		return False

	    match = re.compile(r"^action:playView\?(.*)$").match(url)
	    if match:
		# Parse arguments
		(viewName, firstItemId) = getURLParameters('playView', match.group(1), 'viewName', 'firstItemId')

		# Find the database view that we're supposed to be
		# playing; take out items that aren't playable video
		# clips and put it in the format the frontend expects.
		namedView = self.templateHandle.findNamedView(viewName)
		view = namedView.getView()
		view = view.filter(mappableToPlaylistItem)
		view = view.map(mapToPlaylistItem)

		# Move the cursor to the requested item; if there's no
		# such item in the view, move the cursor to the first
		# item
		view.resetCursor()
		while True:
		    cur = view.getNext()
		    if cur == None:
			# Item not found in view. Put cursor at the first
			# item, if any.
			view.resetCursor()
			view.getNext()
			break
		    if str(cur.getID()) == firstItemId:
			# The cursor is now on the requested item.
			break

		# Construct playback display and switch to it, arranging
		# to switch back to ourself when playback mode is exited
		self.currentFrame.selectDisplay(frontend.VideoDisplay(view, self))
		return False

	    match = re.compile(r"^action:startDownload\?(.*)$").match(url)
	    if match:
		(myitem,) = getURLParameters('startDownload', match.group(1), 'item')
		database.defaultDatabase.saveCursor()
		for obj in database.defaultDatabase:
		    if obj.getID() == int(myitem):
			obj.download()
			break
		database.defaultDatabase.restoreCursor()
		return False

	    match = re.compile(r"^action:addFeed\?(.*)$").match(url)
	    if match:
		(url,) = getURLParameters('addFeed', match.group(1), 'url')
		exists = False
		database.defaultDatabase.saveCursor()
		for obj in database.defaultDatabase:
		    if isinstance(obj,feed.Feed) and obj.getURL() == url:
			exists = True
			break
		database.defaultDatabase.restoreCursor()
		if not exists:
		    myFeed = feed.RSSFeed(url)
		print self.templateData
		self.templateData = {'global' : {
		    'database': database.defaultDatabase,
		    'filter': globalFilterList,
		    'sort': globalSortList },
				     'feed' : myFeed}
		self.execJS('document.location.href = "template:feed-settings";')
		return False

	    match = re.compile(r"^action:removeFeed\?(.*)$").match(url)
	    if match:
		(url,) = getURLParameters('removeFeed', match.group(1), 'url')
		database.defaultDatabase.removeMatching(lambda x: isinstance(x,feed.Feed) and x.getURL() == url)

	    match = re.compile(r"^action:stopDownload\?(.*)$").match(url)
	    if match:
		(myitem,) = getURLParameters('stopDownload', match.group(1), 'item')
		database.defaultDatabase.saveCursor()
		for obj in database.defaultDatabase:
		    if obj.getID() == int(myitem):
			obj.stopDownload()
			break
		database.defaultDatabase.restoreCursor()
		return False

	    # Following are just for debugging/testing.
	    match = re.compile(r"^action:deleteTab\?(.*)$").match(url)
	    if match:
		(base, ) = getURLParameters('deleteTab', match.group(1), 'base')
		database.defaultDatabase.removeMatching(lambda x: isinstance(x, StaticTab) and x.tabTemplateBase == base)
		return False

	    match = re.compile(r"^action:createTab\?(.*)$").match(url)
	    if match:
		(tabTemplateBase, contentsTemplate, order) = getURLParameters('createTab', match.group(1), 'tabTemplateBase', 'contentsTemplate', 'order')
		order = int(order)
		StaticTab(tabTemplateBase, contentsTemplate, order)
		return False

	    match = re.compile(r"^action:recomputeFilters(\?(.*))?$").match(url)
	    if match:
		database.defaultDatabase.recomputeFilters()
		return False

	    match = re.compile(r"^action:addCollection\?(.*)$").match(url)
	    if match:
		(title,) = getURLParameters('addCollection', match.group(1), 'title')
		x = feed.Collection(title)

	    match = re.compile(r"^action:removeCollection\?(.*)$").match(url)
	    if match:
		(id,) = getURLParameters('removeCollection', match.group(1), 'id')
		database.defaultDatabase.removeMatching(lambda x: isinstance(x, feed.Collection) and x.getID() == int(id))

	    match = re.compile(r"^action:addToCollection\?(.*)$").match(url)
	    if match:
		(id,myitem) = getURLParameters('addToCollection', match.group(1), 'id','item')
		obj = None
		for x in database.defaultDatabase:
		    if isinstance(x,feed.Collection) and x.getID() == int(id):
			obj = x
			break
		if obj != None:
		    for x in database.defaultDatabase:
			if isinstance(x,item.Item) and x.getID() == int(myitem):
			    obj.addItem(x)

	    match = re.compile(r"^action:removeFromCollection\?(.*)$").match(url)
	    if match:
		(id,myitem) = getURLParameters('removeFromCollection', match.group(1), 'id','item')
		obj = None
		for x in database.defaultDatabase:
		    if isinstance(x,feed.Collection) and x.getID() == int(id):
			obj = x
			break
		if obj != None:
		    for x in database.defaultDatabase:
			if isinstance(x,item.Item) and x.getID() == int(myitem):
			    obj.removeItem(x)

	    match = re.compile(r"^action:moveInCollection\?(.*)$").match(url)
	    if match:
		(id,myitem,pos) = getURLParameters('moveInCollection', match.group(1), 'id','item','pos')
		obj = None
		for x in database.defaultDatabase:
		    if isinstance(x,feed.Collection) and x.getID() == int(id):
			obj = x
			break
		if obj != None:
		    for x in database.defaultDatabase:
			if isinstance(x,item.Item) and x.getID() == int(myitem):
			    obj.moveItem(x,int(pos))
	except:
	    print "Exception in URL action handler (for URL '%s'):" % url
	    traceback.print_exc()

	# print "Template display URL action: '%s'" % url
	return True

# Helper: parse the given URL queryString and find the arguments with
# the names given by the 'names' arguments. Return a tuple with those
# the values of those arguments in the order they were supplied. If a
# requested argument is not present, an empty string is returned for
# it. (The parser we're using now can't distinguish the two cases.)
# actionName should be the name of the action being invoked and is
# used only to format excetpion error messages.
def getURLParameters(actionName, queryString, *names):
    result = []
    args = cgi.parse_qs(queryString)
    for name in names:
	if not args.has_key(name):
	    # cgi.parse_qs unfortunately cannot distinguish between a
	    # missing argument and an argument that is present but set to
	    # the empty string
	    result.append("")
	elif len(args[name]) != 1:
	    raise template.TemplateError, "Multiple values of '%s' argument passend to '%s' action" % (name, actionName)
	else:
	    result.append(args[name][0])
    return tuple(result)

# Helper: liberally interpret the provided string as a boolean
def stringToBoolean(string):
    if string == "" or string == "0" or string == "false":
	return False
    else:
	return True

###############################################################################
#### The application object, managing startup and shutdown                 ####
###############################################################################

class Controller(frontend.Application):
    def OnStartup(self):
	try:
	    #Restoring
	    print "Restoring database..."
	    database.defaultDatabase.restore()
	    print "Recomputing filters..."
	    database.defaultDatabase.recomputeFilters()

	    reloadStaticTabs()
	    globalData = {
		'database': database.defaultDatabase,
		'filter': globalFilterList,
		'sort': globalSortList,
		'favoriteColor': 'azure', # NEEDS: test data, remove
	     }

	    # Set up tab list
	    mapFunc = makeMapToTabFunction(globalData)
	    self.tabs = database.defaultDatabase.filter(mappableToTab).map(mapFunc).sort(sortTabs)

	    # Put cursor on first tab to indicate that it should be initially
	    # selected
	    self.tabs.resetCursor()
	    self.tabs.getNext()

	    # Create a test array (NEEDS: remove)
 	    #[NameNumberObject() for i in range(0,50)]
            #testArray = database.DDBObject.dd.filter(lambda x: x.__class__ == NameNumberObject)
	    #globalData['testArray'] = testArray

	    print "Spawning first feed..."
	    hasFeed = False
	    for obj in database.defaultDatabase.objects:
		if obj[0].__class__.__name__ == 'RSSFeed':
		    hasFeed = True
		    break
	    if not hasFeed:
		f = feed.RSSFeed("http://blogtorrent.com/demo/rss.php")
	    
	    print "Spawning auto downloader..."
	    #Start the automatic downloader daemon
	    autodler.AutoDownloader()

	    print "Displaying main frame..."
	    self.frame = frontend.MainFrame(self.tabs,globalData)
	except:
	    print "Exception on startup:"
	    traceback.print_exc()

    def OnShutdown(self):
	print "Removing static tabs..."
	database.defaultDatabase.removeMatching(lambda x:str(x.__class__.__name__) == "StaticTab")
	#for item in database.defaultDatabase:
	#    print str(item.__class__.__name__) + " of id "+str(item.getID())
	print "Saving database..."
	database.defaultDatabase.save()

         #FIXME closing BitTorrent is slow and makes the application seem hung...
	print "Shutting down BitTorrent..."
	downloader.shutdownBTDownloader()

	print "Done shutting down."

def main():
    Controller().Run()

###############################################################################
#### Tabs                                                                  ####
###############################################################################

# Database object representing a static (non-feed-associated) tab.
class StaticTab(database.DDBObject):
    def __init__(self, tabTemplateBase, contentsTemplate, order):
	self.tabTemplateBase = tabTemplateBase
	self.contentsTemplate = contentsTemplate
	self.order = order
	database.DDBObject.__init__(self)

# Reload the StaticTabs in the database from the statictabs.xml resource file.
def reloadStaticTabs():
    # Wipe all of the StaticTabs currently in the database.
    database.defaultDatabase.removeMatching(lambda x: x.__class__ == StaticTab)

    # Load them anew from the resource file.
    # NEEDS: maybe better error reporting?
    document = parse(resource.path('statictabs.xml'))
    for n in document.getElementsByTagName('statictab'):
	tabTemplateBase = n.getAttribute('tabtemplatebase')
	contentsTemplate = n.getAttribute('contentstemplate')
	order = int(n.getAttribute('order'))
	StaticTab(tabTemplateBase, contentsTemplate, order)

# The HTMLTab subclass we use for presenting tabs to the frontend. This is
# where we define the logic to render and activate a tab.
class TemplateTab(frontend.HTMLTab):
    def __init__(self, tabTemplateBase, tabData, contentsTemplate, contentsData, sortKey, obj):
	self.tabTemplateBase = tabTemplateBase
	self.tabData = tabData
	self.contentsTemplate = contentsTemplate
	self.contentsData = contentsData
	self.sortKey = sortKey
	self.obj = obj # NEEDS: for redraw hack; make this go away
	frontend.HTMLTab.__init__(self)

    def getHTML(self, state):
	file = "%s-%s" % (self.tabTemplateBase, state)
	return template.fillStaticTemplate(file, self.tabData)

    def start(self, frame):
	frame.setTabListActive(True) 
	frame.selectDisplay(TemplateDisplay(self.contentsTemplate, self.contentsData, frameHint=frame))

    def redraw(self):
	self.obj.beginChange()
	self.obj.endChange()

# Return True if a tab should be shown for obj in the frontend. The filter
# used on the database to get the list of tabs.
def mappableToTab(obj):
    return isinstance(obj, StaticTab) or (isinstance(obj, feed.Feed) and obj.isVisible())

# Generate a function that, given an object for which mappableToTab
# returns true, return a HTMLTab subclass. This is used to turn the
# database objects that should be represented with tabs (the model)
# into frontend tab objects (the view.)
#
# By 'generate a function', we mean that you give makeMapToTabFunction
# the global data that you want to always be available in both the tab
# templates and the contents page template, and it returns a function
# that maps objects to tabs such that that request is satisified.
def makeMapToTabFunction(globalTemplateData):
    class MapToTab:
	def __init__(self, globalTemplateData):
	    self.globalTemplateData = globalTemplateData
	
	def mapToTab(self,obj):
	    data = {'global': self.globalTemplateData};
	    if isinstance(obj, StaticTab):
		return TemplateTab(obj.tabTemplateBase, data, obj.contentsTemplate, data, [obj.order], obj)
	    elif isinstance(obj, feed.Feed):
	    	data['feed'] = obj
		# Change this to sort feeds on a different value
		sortKey = obj.getTitle()
	    	return TemplateTab('feedtab', data, 'feed-start', data, [100, sortKey], obj)
	    else:
		assert(0) # NEEDS: clean up (signal internal error)

    return MapToTab(globalTemplateData).mapToTab

# The sort function used to order tabs in the tab list. Just use the sort
# keys provided when mapToTab created the TemplateTabs. These can be lists,
# which are tested left-to-right in the way you'd expect. Generally, the way
# this is used is that static tabs are assigned a numeric priority, and get
# a single-element list with that number as their sort key; feeds get a
# list with '100' in the first position, and a value that determines the
# order of the feeds in the second position. This way all of the feeds are
# together, and the static tabs can be positioned around them.
def sortTabs(x, y):
    if x.sortKey < y.sortKey:
	return -1
    elif x.sortKey > y.sortKey:
	return 1
    return 0

###############################################################################
#### Video clips                                                           ####
###############################################################################

def mappableToPlaylistItem(obj):
    if not isinstance(obj, item.Item):
	return False
    # NEEDS: check to see if the download has finished in a cleaner way
    if obj.downloadState() != "finished":
	return False
    return True

class playlistItemFromItem(frontend.PlaylistItem):
    def __init__(self, item):
	self.item = item

    def getTitle(self):
	# NEEDS
	return "Title here"

    def getPath(self):
	# NEEDS
	return "/Users/gschmidt/Movies/mahnamahna.mpeg"

    def getLength(self):
	# NEEDS
	return 42.42

    def onViewed(self):
	# NEEDS: I have no idea if this is right.
	#self.item.markItemSeen()
	None

    # Return the ID that is used by a template to indicate this item 
    def getID(self):
	return self.item.getID()

def mapToPlaylistItem(obj):
    return playlistItemFromItem(obj)

###############################################################################
#### The global set of filter and sort functions accessible from templates ####
###############################################################################

def compare(x, y):
    if x < y:
	return -1
    if x > y:
	return 1
    return 0

def itemSort(x,y):
    if x.getReleaseDate() < y.getReleaseDate():
	return -1
    elif x.getReleaseDate() > y.getReleaseDate():
	return 1
    elif x.getID() < y.getID():
	return -1
    elif x.getID() > y.getID():
	return 1
    else:
	return 0

def alphabeticalSort(x,y):
    if x.getTitle() < y.getTitle():
	return -1
    elif x.getTitle() > y.getTitle():
	return 1
    elif x.getDescription() < y.getDescription():
	return -1
    elif x.getDescription() > y.getDescription():
	return 1
    else:
	return 0

def downloadStartedSort(x,y):
    if x.getTitle() < y.getTitle():
	return -1
    elif x.getTitle() > y.getTitle():
	return 1
    elif x.getDescription() < y.getDescription():
	return -1
    elif x.getDescription() > y.getDescription():
	return 1
    else:
	return 0

globalSortList = {
    'item': itemSort,
    'alphabetical': alphabeticalSort,
    'downloadStarted': downloadStartedSort,
    'text': (lambda x, y: compare(str(x), str(y))),
    'number': (lambda x, y: compare(float(x), float(y))),
}

def filterClass(obj, parameter):
    if type(obj) != types.InstanceType:
	return False

    # Pull off any package name
    name = str(obj.__class__)
    match = re.compile(r"\.([^.]*)$").search(name)
    if match:
	name = match.group(1)

    return name == parameter

def filterHasKey(obj,parameter):
    try:
	obj[parameter]
    except KeyError:
	return False
    return True

globalFilterList = {
    'substring': (lambda x, y: str(y) in str(x)),
    'boolean': (lambda x, y: x),

    #FIXME make this look at the feed's time until expiration
    'recentItems': (lambda x, y: isinstance(x,item.Item) and x.getState() == 'finished' and x.getDownloadedTime()+config.get('DefaultTimeUntilExpiration')>datetime.datetime.now() and (str(y).lower() in x.getTitle().lower() or str(y).lower() in x.getDescription().lower())),
    'oldItems': (lambda x, y:  isinstance(x,item.Item) and x.getState() == 'finished' and x.getDownloadedTime()+config.get('DefaultTimeUntilExpiration')<=datetime.datetime.now() and (str(y).lower() in x.getTitle().lower() or str(y).lower() in x.getDescription().lower())),

    'downloadedItems': (lambda x, y: isinstance(x,item.Item) and x.getState() == 'finished' and (str(y).lower() in x.getTitle().lower() or str(y).lower() in x.getDescription().lower())),
    'unDownloadedItems': (lambda x, y: isinstance(x,item.Item) and (not x.getState() == 'finished') and (str(y).lower() in x.getTitle().lower() or str(y).lower() in x.getDescription().lower())),
    'downloadingItems': (lambda x, y: isinstance(x,item.Item) and x.getState() == 'downloading' and (str(y).lower() in x.getTitle().lower() or str(y).lower() in x.getDescription().lower())),
       
    'class': filterClass,
    'all': (lambda x, y: True),
    'hasKey':  filterHasKey,
}

###############################################################################
#### Test data                                                             ####
###############################################################################

class NameNumberObject(database.DDBObject):
    def __init__(self):
	parts = ["ae ", "thi", "ok ", "nin", "yt", "k'", "sem", "oo", "er", "p "]
	idx = [random.randint(0,len(parts)-1) for i in range(0,random.randint(3, 10))]
       	self.name = "".join([parts[i] for i in idx])
	self.number = random.randint(0,100000)
	database.DDBObject.__init__(self)

