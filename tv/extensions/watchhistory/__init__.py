from watchhistory import main

WATCHER = None

def load():
    """Loads the watchhistory module.
    """
    global WATCHER
    WATCHER = main.WatchHistory()

def unload():
    pass
