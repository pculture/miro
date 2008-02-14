import os
import sys
import tempfile
import glob

from miro import httpclient
from miro import config
from miro import prefs
from miro import dialogs
from miro.gtcache import gettext as _

def firefoxExecutable():
    if sys.platform == "darwin":
        import AppKit
        return AppKit.NSWorkspace.sharedWorkspace().fullPathForApplication_("Firefox")
    else:
        search_path = ["/usr/bin/firefox", "C:\\Program Files\\Mozilla Firefox\\firefox.exe"]
        for poss in search_path:
            if os.path.isfile(poss):
                return poss
    return None

def isFirefoxInstalled():
    return firefoxExecutable() != None

def isIHeartMiroInstalled():
    id = "{216ec66d-214a-43ea-92f0-5373f8405c88}"
    locations = ["~/.mozilla/firefox/*/extensions/" + id,
	             "~\\Application Data\\Mozilla\\Firefox\\Profiles\\*\\extensions\\" + id,
	            "~/Library/Application Support/Firefox/Profiles/*/extensions/" + id ]
    for location in locations:
        if glob.glob (os.path.expanduser(location)):
            return True
    return False

def installIHeartMiro():
    def httpSuccess(info):
        fd, filename = tempfile.mkstemp(suffix=".xpi", prefix="iHeartMiro-", text=False)
        output = os.fdopen(fd, "wb")
        output.write(info["body"])
        output.close()
        if sys.platform == "darwin":
            import AppKit
            AppKit.NSWorkspace.sharedWorkspace().openFile_withApplication_andDeactivate_(filename, "Firefox", True)
        else:
            exe = firefoxExecutable()
            os.spawnl(os.P_NOWAIT, exe, exe, filename)
    def httpFailure(error):
        print "error: %s" % (error,)
    httpclient.grabURL("http://www.iheartmiro.org/iHeartMiro-latest.xpi", httpSuccess, httpFailure)


# request_count makes it so that the second time you 
def checkIHeartMiroInstall():
    request_count = config.get(prefs.IHEARTMIRO_REQUEST_COUNT)

#    if request_count >= 2:
# Comment out these two lines to do testing.
    if request_count >= 1:
        return

    if isIHeartMiroInstalled() or not isFirefoxInstalled():
        config.set(prefs.IHEARTMIRO_REQUEST_COUNT, 2)
        return

    def callback(dialog):
        count = request_count
        if dialog.choice == dialogs.BUTTON_INSTALL_IHEARTMIRO:
            installIHeartMiro()

        if isinstance(dialog, dialogs.CheckboxDialog):
            if not dialog.checkbox_value:
                count = 2
            if dialog.checkbox_value:
                if count == 2:
                    count = 0
        else:
            count = count + 1
        config.set(prefs.IHEARTMIRO_REQUEST_COUNT, count)

    message = \
_("""An Effortless Way to Help Miro

Miro is open-source and built by a non-profit.  We need your help to continue our work.

I Heart Miro is a simple Firefox extension that gives a referral fee to the Miro organization when you shop at Amazon.  You'll never notice it, it doesn't cost you a thing, and it's easy to uninstall at any time.

If you click 'Install iHeartMiro' below, Firefox will launch and ask if it's ok.   Just say yes and you're done!   It takes about 7 seconds.  And thanks for your help.""")

    title = "Install iHeartMiro?"
#    again = _ ("Ask me again later")
#    dialog = dialogs.CheckboxDialog(title, message, again, request_count < 1,
#                                    dialogs.BUTTON_INSTALL_IHEARTMIRO, dialogs.BUTTON_DONT_INSTALL)
    dialog = dialogs.ChoiceDialog(title, message, dialogs.BUTTON_INSTALL_IHEARTMIRO, dialogs.BUTTON_DONT_INSTALL)
    dialog.run(callback)
