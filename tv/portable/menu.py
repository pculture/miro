import eventloop

def makeMenu(items):
    """Convenience function to create a list of MenuItems given on a list of
    (callback, label) tuples.
    """

    return [MenuItem(callback, label) for callback, label in items]

class MenuItem:
    """A single menu item in a context menu.

    Normally frontends should display label as the text for this menu item,
    and if it's clicked on call activate().  One second case is if label is
    blank, in which case a separator should be show.  Another special case is
    if callback is None, in which case the label should be shown, but it
    shouldn't be clickable.  
    
    """

    def __init__(self, callback, label):
        self.label = label
        self.callback = callback

    def activate(self):
        """Run this menu item's callback in the backend event loop."""

        eventloop.addUrgentCall(self.callback, "context menu callback")
