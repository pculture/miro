import unittest
import os
import os.path
import glob

import httpclient
import eventloop

from test.framework import DownloaderTestCase

# In order to use this test, you must set the following environment variables
#
# BMACHINE_SERVER - the ssh location of the machine where you wish
#                   to install Broadcast Machine for testing ie
#                   "user@test.getdemocracy.com"
#
# BMACHINE_SERVER_LOCATION - the ssh location of the directory where
#                            you wish to install Broadcast Machine for
#                            testing. For example "/bmachine" will
#                            result in sshing to
#                            user@test.getdemocracy.com:/bmachine
#
# BMACHINE_SERVER_URL - the url of the above directory
#                       ie "http://test.getdemocracy.com/bmachine"
#
#
# BMACHINE_LOCATION - the location of Broadcast Machine on the testing
#                     computer ie "/home/user/bmachine"
#

class BroadcastMachineTest(DownloaderTestCase):
    def setUp(self):
        self.assert_(os.environ.has_key('BMACHINE_SERVER'))
        self.assert_(os.environ.has_key('BMACHINE_SERVER_LOCATION'))
        self.assert_(os.environ['BMACHINE_SERVER_LOCATION'].startswith('/'))
        self.assert_(os.environ.has_key('BMACHINE_SERVER_URL'))
        self.assert_(os.environ.has_key('BMACHINE_LOCATION'))
        self.loc = os.environ['BMACHINE_LOCATION']
        self.server = os.environ['BMACHINE_SERVER']
        self.server_loc = os.environ['BMACHINE_SERVER_LOCATION']
        self.url = os.environ['BMACHINE_SERVER_URL']
        DownloaderTestCase.setUp(self)
        self.dlError = False
        self.fixedPermissions = False
        
    def test(self):
        launchArgs = ["-C", "-q","-r"]
        launchArgs.extend(glob.glob(os.path.join(self.loc, '*')))
        launchArgs.append("%s:%s" % (self.server, self.server_loc))
        self.assertEqual(os.spawnvp(os.P_WAIT, "scp", launchArgs),0)
        httpclient.grabURL (self.url, self.setupCallback, self.errorCallback)
        self.runEventLoop()

    def fixPermissions(self):
        self.assert_(not self.fixedPermissions)
        self.fixedPermissions = True
        for d in ["torrents", "data", "publish", "thumbnails", "text"]:
            os.spawnlp(os.P_WAIT, "ssh", "-C", self.server, 'mkdir %s 2>&1' % os.path.join(self.server_loc, d))
            os.spawnlp(os.P_WAIT, "ssh", "-C", self.server, 'chmod 777 %s 2>&1' % os.path.join(self.server_loc, d))

    def setupCallback(self, info):
        self.info = info
        self.assertEqual(info['status'], 200)
        if info['body'].find("Before you can use Broadcast Machine, we need to create a few directories.  There are several ways to do this listed below.") != -1:
            self.fixPermissions()
            httpclient.grabURL (self.url, self.setupCallback, self.errorCallback)
        else:
            self.assertNotEqual(info['body'].find("This looks like your first time using Broadcast Machine."), -1)
            self.assertNotEqual(info['body'].find("You should create a new user account before continuing."), -1)
            httpclient.grabURL(info['redirected-url'], self.createAccountCallback,
                               self.errorCallback, method="POST",
                               postVariables = {"do_login" : "1",
                                                "email": "nassar@pculture.org",
                                                "username": "admin",
                                                "pass1": "PCF is cool",
                                                "pass2": "PCF is cool"})

    def makeBMCookies(self):
        return {'PHPSESSID':self.PHPSESSID,
                'bm_userhash': self.bm_userhash,
                'bm_username': self.bm_username}

    def storeBMCookie(self, cookies):
        self.assert_(cookies.has_key('bm_userhash'))
        self.assert_(cookies.has_key('bm_username'))
        self.assert_(cookies.has_key('PHPSESSID'))
        self.PHPSESSID = cookies['PHPSESSID']
        self.bm_userhash = cookies['bm_userhash']
        self.bm_username = cookies['bm_username']

    def createAccountCallback(self, info):
        self.assertNotEqual(info['body'].find("The account admin was added successfully."), -1)
        self.assertEqual(info['cookies']['bm_username']['Value'],'admin')
        self.storeBMCookie(info['cookies'])
        httpclient.grabURL(self.url+'admin.php', self.adminNoCookies,
                           self.errorCallback)

    def adminNoCookies(self, info):
        self.assert_(info['redirected-url'].endswith('/index.php'))
        httpclient.grabURL(self.url+'admin.php', self.adminLoad,
                           self.errorCallback, cookies = self.makeBMCookies())
        

    def adminLoad(self, info):
        self.assert_(info['redirected-url'].endswith('/admin.php'))
        self.assertNotEqual(info['body'].find('Dashboard'), -1)
        self.assertNotEqual(info['body'].find('admin'), -1)
        self.assertNotEqual(info['body'].find('nassar@pculture.org'), -1)
        self.assertNotEqual(info['body'].find('Go to Users'), -1)
        self.assertNotEqual(info['body'].find('Go to Files'), -1)
        self.storeBMCookie(info['cookies'])
        eventloop.quit()

    def errorCallback(self, error):
        print "Broadcast Machine URL load died with %s" % error
        self.dlError = True
        self.stopEventLoop()
