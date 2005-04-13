

# Imports: theDatabase

class App(): 

 def __init__(self):
  # Load application tabs anew from file
  theDatabase.deleteByFilter(lambda x:isinstance(x, HTMLApp))
  appTabDOM = LoadXML("apptabs.xml")
  # NEEDS: loop to construct HTMLApp tabs from DOM

  tabView = theDatabase.						      \
 	     filter(lambda x: isinstance(x, Feed) or isinstance(x, HTMLApp)). \
	     map(lambda x: isinstance(x, Feed) and FeedTab(x) or AppTab(x),   \
	         lambda x: None).                                             \
	     sort(lambda x,y: orderTuples(x.sortKey(), y.sortKey()))
  tabView.resetCursor()
  self.frame = MainFrame(tabView)

 class FeedTab(HTMLTab):
       def __init__(self, f):
       	   self.feed = f

       def getHTML(self, state):
       	   return fillTemplate("feed-tab-%s" % state, {"feed":self.feed})

       def start(self, frame):
           # NEEDS: sort
       	   d = DHTMLDisplay("feed",frame,theDatabase.filter(lambda x: isinstance(x, Item) and x.getFeed() is self.feed),{"feed":self.feed})
       	   frame.selectDisplay(d)

 class AppTab(HTMLTab):
       def __init__(self, app):
       	   self.app = app

       def getHTML(self, state):
       	   return fillTemplate("app-tab-%s" % state, {"app":self.app})

       def start(self, frame):
           # NEEDS: sort
       	   d = DHTMLDisplay("feed",frame,self.getView(),{"app":self.app})
       	   frame.selectDisplay(d)

# NEEDS: mark items seen
class DHTMLDisplay(HTMLDisplay):
      # NEEDS: doesn't handle following links to other pages

      def __init__(self, frame, templateName, records, keys={})
      	  self.filter = ''
	  self.frame = frame
	  self.records = records.filter(lambda x:itemContainsSubstring(x,self.filter))
	  self.objectsByTid = {} # NEEDS: populate
	  self.emptySetTids = {} # tid -> template HTML
	  self.nonemptySetTids = {} # tid -> template HTML
      	  theDatabase.beginRead()
	  # Need to map records to get template IDs
	  (html, self.itemStartTid, self.itemTemplate) = fillDynamicTemplate(templateName, self.records, keys)
	  records.addAddCallback(lambda x,y:self.onAdded(x,y));
	  records.addRemoveCallback(lambda x,y:self.onRemoved(x,y));
	  records.addUpdateCallback(lambda x,y:self.onUpdate(x,y));
	  theDatabase.endRead()

      def onAdded(self, what,where):
      	  tid = # get template ID for 'where'
      	  self.execJS("itemAdded(%s,%s)" % (fillImmediateTemplate(self.itemTemplate,what),tid))

      def onUpdated(self, what, where):
      	  tid = # get template ID for 'where'
      	  self.execJS("itemUpdated(%s,%s)" % (fillImmediateTemplate(self.itemTemplate,what),tid))

      def onRemoved(self, what, where):
      	  tid = # get template ID for 'where'
      	  self.execJS("itemRemoved(%s,%s)" % tid)

      # Perhaps we could just multiply inherit from Item?
      class ItemPlaylistItem(PlaylistItem):
      	    def __init__(self,item):
	    	self.item = item

	    def getTitle(self):
	    	self.item.getTitle()

	    def getPath(self):
	    	self.item.download.getPath()

	    def getLength(self):
	    	self.item.fileinfo.getApproxLengthInSeconds()

            def onViewed(self):
	    	markItemWatched(item)

      def onURLLoad(self, url):
      	  (action, parameters) = parseURL(url)
	  # needs: check that scheme is 'action'
	  # needs: case insensitive comparison
	  if action == 'downloaditem':
	     downloadItem(objectsByTid[parameters["id"]])
	  else if action == 'canceldownload':
	     cancelDownloadItem(objectsByTid[parameters["id"]])
	  else if action == 'saveitem':
	     saveItem(objectsByTid[parameters["id"]])
	  else if action == 'deleteitem':
	     deleteItem(objectsByTid[parameters["id"]])
	  else if action == 'clearitem':
	     clearItem(objectsByTid[parameters["id"]])
	  else if action == 'addfeed':
	     addFeed(parameters["url"])
	  else if action == 'removefeed':
	     removeFeed(objectsByTid[parameters["id"]])
	  else if action == 'setfeedtargetunwatcheditemscount': 
	     # 0, positive integer, 'unlimited' are legal	     
	     objectsByTid[parameters["id"]].setFeedTargetUnwatchedItemsCount(parameters["value"]
	  else if action == 'setfilter': # incremental search
	     # NEEDS: honor 'fields' parameter
	     self.filter = parameters["substring"]
	     self.records.recomputeFilter()
	  else if action == 'play': # play video
	     playlist = self.records.
	     	      filter(lambda x: isinstance(x,Item) and x.isPlayable()).
		      map(ItemPlaylistItem)
	     # NEEDS: get frame here
	     frame.selectDisplay(PlayerDisplay(playlist,self))
	  return 0

class PlayerDisplay(VideoDisplay):
      def __init__(self, playList, previousDisplay):
      	  self.previousDisplay = previousDisplay
	  VideoDisplay.__init__(self, playList)

      def onSelectedTabClicked(self, frame):
      	  frame.selectDisplay(self.previousDisplay)
    