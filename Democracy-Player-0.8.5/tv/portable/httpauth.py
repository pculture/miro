from download_utils import parseURL
import dialogs
import eventloop
import views

def formatAuthString(auth):
    return "%s %s" % (auth.getAuthScheme(), auth.getAuthToken())

def findHTTPAuth(callback, host, path):
    """Find an HTTPAuthPassword object stored in the database.  Callback will
    be called with a string to use for the Authorization header or None if we
    can't find anything in the DB.
    """
    import downloader

    auth = downloader.findHTTPAuth(host, path)
    if auth is not None:
        auth = formatAuthString(auth)
    eventloop.addIdle(callback, "http auth callback", args=(auth,))

def askForHTTPAuth(callback, url, realm, authScheme):
    """Ask the user for a username and password to login to a site.  Callback
    will be called with a string to use for the Authorization header or None
    if the user clicks cancel.
    """

    scheme, host, port, path = parseURL(url)
    def handleLoginResponse(dialog):
        import downloader
        if dialog.choice == dialogs.BUTTON_OK:
            auth = downloader.HTTPAuthPassword(dialog.username,
                    dialog.password, host, realm, path, authScheme)
            callback(formatAuthString(auth))
        else:
            callback(None)
    dialogs.HTTPAuthDialog(url, realm).run(handleLoginResponse)
