import eventloop

def makeMenu(items):
    """Convenience function to create a list of MenuItems given on a list of
    (callback, label) tuples.
    """

    return [MenuItem(callback, label) for callback, label in items]

class MenuItem:
    """A single menu item in a context menu."""

    def __init__(self, callback, label):
        self.label = label
        self.callback = callback

    def activate(self):
        """Run this menu item's callback in the backend event loop."""

        eventloop.addUrgentCall(self.callback, "context menu callback")
