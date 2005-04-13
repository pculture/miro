###############################################################################
#### Main window                                                           ####
###############################################################################

# To be provided in platform package
class MainFrame():
      """Represents a main Frontend window."""
      def __init__(self, tabs):
      	  """'tabs' is a View containing Tab subclasses. The initially
	  selected tab is given by the cursor. The initially active display
	  will be an instance of NullDisplay."

      def selectDisplay(self, display):
      	  """Install the provided 'display' in the right-hand side
	  of the window."""

      def setTabListActive(self, active):
      	  """If active is true, show the tab list normally. If active is
	  false, show the tab list a different way to indicate that it
	  doesn't pertain directly to what is going on (for example, a
	  video is playing) but that it can still be clicked on."""

###############################################################################
#### Tabs                                                                  ####
###############################################################################

class Tab():
      """Base class for the records that makes up the list of left-hand
      tabs to show. Cannot be put into a MainFrame directly -- you must
      use a subclass, such as HTMLTab, that knows how to render itself."""

      def start(self, frame):
      	  """Called when the tab is clicked on in a MainFrame where it was
	  not already the selected tab (or when it becomes selected by other
	  means, eg, the selected tab was deleted and this tab has become
	  selected by default.) 'frame' is the MainFrame where the tab is
	  selected. Should usually result in a call to
	  frame.selectDisplay()."""

class HTMLTab():
      """A Tab whose appearance is defined by HTML."""

      def getHTML(self, state):
      	  """Get HTML giving the visual appearance of the tab. 'state' is
	  one of 'selected' (tab is currently selected), 'normal' (tab is
	  not selected), or 'selected-inactive' (tab is selected but
	  setTabListActive was called with a false value on the MainFrame
	  for which the tab is being rendered.)"""

###############################################################################
#### Right-hand pane displays                                              ####
###############################################################################

# To be provided in platform package
class Display():
      "Base class representing a display in a MainFrame's right-hand pane."

      def onSelected(self, frame):
      	  """Called when the Display is shown in the given MainFrame."""

      def onDeselected(self, frame):
      	  """Called when the Display is no longer shown in the given
	  MainFrame. This function is called on the Display losing the
	  selection before onSelected is called on the Display gaining the
	  selection."""

      def onSelectedTabClicked(self, frame):
      	  """Called on the Display shown in the given MainFrame when the
	  selected tab is clicked again by the user."""

# To be provided in platform package
class NullDisplay(Display):
      "Represents an empty right-hand area."

# To be provided in platform package
class HTMLDisplay(Display):
      "HTML browser that can be shown in a MainFrame's right-hand pane."

      def __init__(self, html):
      	  "'html' is the initial contents of the display, as a string."

      def execJS(self, js):
      	  "Execute the given Javascript code (provided as a string) in the
	  context of this HTML document."

      def onURLLoad(self, url):
          """Called when this HTML browser attempts to load a URL (either
	  through user action or Javascript.) The URL is provided as a
	  string. Return true to allow the URL to load, or false to cancel
	  the load (for example, because it was a magic URL that marks
	  an item to be downloaded.) Implementation in HTMLDisplay always
	  returns true; override in a subclass to implement special
	  behavior."""

# To be provided in platform package
class VideoDisplay(Display):
      "Video player that can be shown in a MainFrame's right-hand pane."

      def __init__(self, playlist):
       	  """'playlist' is a View giving the video items to play
	  as PlaylistItems. The cursor of the View indicates where playback
	  should start."""

class PlaylistItem():
      "The record that makes up VideoDisplay playlists."

      def getTitle(self):
      	  """Return the title of this item as a string, for visual presentation
	  to the user."""
	  raise NotImplementedError

      def getPath(self):
      	  """Return the full path in the local filesystem to the video file
	  to play."""
	  raise NotImplementedError

      def getLength(self):
      	  """Return the length of this item in seconds as a real number. This
	  is used only cosmetically, for telling the user the total length
	  of the current playlist and so on."""
	  raise NotImplementedError

      def onViewed(self):
      	  """Called by the frontend when a clip is at least partially watched
	  by the user. To handle this event, for example by marking the
	  item viewed in the database, override this method in a subclass."

###############################################################################
###############################################################################
