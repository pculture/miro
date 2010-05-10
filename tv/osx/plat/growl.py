"""
A Python module that enables posting notifications to the Growl daemon.
See <http://growl.info/> for more information.
"""
__version__ = "0.7" 
__author__ = "Mark Rowe <bdash@users.sourceforge.net>"
__copyright__ = "(C) 2003 Mark Rowe <bdash@users.sourceforge.net>. Released under the BSD license."
__contributors__ = ["Ingmar J Stein (Growl Team)", 
					"Rui Carmo (http://the.taoofmac.com)",
					"Jeremy Rossi <jeremy@jeremyrossi.com>",
					"Peter Hosey <http://boredzo.org/> (Growl Team)",
				   ]

import _growl
import types
import struct
import hashlib
import socket

GROWL_UDP_PORT=9887
GROWL_PROTOCOL_VERSION=1
GROWL_TYPE_REGISTRATION=0
GROWL_TYPE_NOTIFICATION=1

GROWL_APP_NAME="ApplicationName"
GROWL_APP_ICON="ApplicationIcon"
GROWL_NOTIFICATIONS_DEFAULT="DefaultNotifications"
GROWL_NOTIFICATIONS_ALL="AllNotifications"
GROWL_NOTIFICATIONS_USER_SET="AllowedUserNotifications"

GROWL_NOTIFICATION_NAME="NotificationName"
GROWL_NOTIFICATION_TITLE="NotificationTitle"
GROWL_NOTIFICATION_DESCRIPTION="NotificationDescription"
GROWL_NOTIFICATION_ICON="NotificationIcon"
GROWL_NOTIFICATION_APP_ICON="NotificationAppIcon"
GROWL_NOTIFICATION_PRIORITY="NotificationPriority"
		
GROWL_NOTIFICATION_STICKY="NotificationSticky"

GROWL_APP_REGISTRATION="GrowlApplicationRegistrationNotification"
GROWL_APP_REGISTRATION_CONF="GrowlApplicationRegistrationConfirmationNotification"
GROWL_NOTIFICATION="GrowlNotification"
GROWL_SHUTDOWN="GrowlShutdown"
GROWL_PING="Honey, Mind Taking Out The Trash"
GROWL_PONG="What Do You Want From Me, Woman"
GROWL_IS_READY="Lend Me Some Sugar; I Am Your Neighbor!"

	
growlPriority = {"Very Low":-2,"Moderate":-1,"Normal":0,"High":1,"Emergency":2}

class netgrowl:
	"""Builds a Growl Network Registration packet.
	   Defaults to emulating the command-line growlnotify utility."""

	__notAllowed__ = [GROWL_APP_ICON, GROWL_NOTIFICATION_ICON, GROWL_NOTIFICATION_APP_ICON]

	def __init__(self, hostname, password ):
		self.hostname = hostname
		self.password = password
		self.socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

	def send(self, data):
		self.socket.sendto(data, (self.hostname, GROWL_UDP_PORT))
		
	def PostNotification(self, userInfo):
		if userInfo.has_key(GROWL_NOTIFICATION_PRIORITY):
			priority = userInfo[GROWL_NOTIFICATION_PRIORITY]
		else:
			priority = 0
		if userInfo.has_key(GROWL_NOTIFICATION_STICKY):
			sticky = userInfo[GROWL_NOTIFICATION_STICKY]
		else:
			sticky = False
		data = self.encodeNotify(userInfo[GROWL_APP_NAME],
								 userInfo[GROWL_NOTIFICATION_NAME],
								 userInfo[GROWL_NOTIFICATION_TITLE],
								 userInfo[GROWL_NOTIFICATION_DESCRIPTION],
								 priority,
								 sticky)
		return self.send(data)

	def PostRegistration(self, userInfo):
		data = self.encodeRegistration(userInfo[GROWL_APP_NAME],
									   userInfo[GROWL_NOTIFICATIONS_ALL],
									   userInfo[GROWL_NOTIFICATIONS_DEFAULT])
		return self.send(data)

	def encodeRegistration(self, application, notifications, defaultNotifications):
		data = struct.pack("!BBH",
						   GROWL_PROTOCOL_VERSION,
						   GROWL_TYPE_REGISTRATION,
						   len(application) )
		data += struct.pack("BB",
							len(notifications),
							len(defaultNotifications) )
		data += application
		for i in notifications:
			encoded = i.encode("utf-8")
			data += struct.pack("!H", len(encoded))
			data += encoded
		for i in defaultNotifications:
			data += struct.pack("B", i)
		return self.encodePassword(data)

	def encodeNotify(self, application, notification, title, description,
					 priority = 0, sticky = False):

		application  = application.encode("utf-8")
		notification = notification.encode("utf-8")
		title		= title.encode("utf-8")
		description  = description.encode("utf-8")
		flags = (priority & 0x07) * 2
		if priority < 0: 
			flags |= 0x08
		if sticky: 
			flags = flags | 0x0001
		data = struct.pack("!BBHHHHH",
						   GROWL_PROTOCOL_VERSION,
						   GROWL_TYPE_NOTIFICATION,
						   flags,
						   len(notification),
						   len(title),
						   len(description),
						   len(application) )
		data += notification
		data += title
		data += description
		data += application
		return self.encodePassword(data)

	def encodePassword(self, data):
		checksum = hashlib.md5()
		checksum.update(data)
		if self.password:
		   checksum.update(self.password)
		data += checksum.digest()
		return data

class _ImageHook(type):
	def __getattribute__(self, attr):
		global Image
		if Image is self:
			from _growlImage import Image

		return getattr(Image, attr)

class Image(object):
	__metaclass__ = _ImageHook

class _RawImage(object):
	def __init__(self, data):  self.rawImageData = data

class GrowlNotifier(object):
	"""
	A class that abstracts the process of registering and posting
	notifications to the Growl daemon.

	You can either pass `applicationName', `notifications',
	`defaultNotifications' and `applicationIcon' to the constructor
	or you may define them as class-level variables in a sub-class.

	`defaultNotifications' is optional, and defaults to the value of
	`notifications'.  `applicationIcon' is also optional but defaults
	to a pointless icon so is better to be specified.
	"""

	applicationName = 'GrowlNotifier'
	notifications = []
	defaultNotifications = []
	applicationIcon = None
	_notifyMethod = _growl

	def __init__(self, applicationName=None, notifications=None, defaultNotifications=None, applicationIcon=None, hostname=None, password=None):
		if applicationName:
			self.applicationName = applicationName
		assert self.applicationName, 'An application name is required.'

		if notifications:
			self.notifications = list(notifications)
		assert self.notifications, 'A sequence of one or more notification names is required.'

		if defaultNotifications is not None:
			self.defaultNotifications = list(defaultNotifications)
		elif not self.defaultNotifications:
			self.defaultNotifications = list(self.notifications)

		if applicationIcon is not None:
			self.applicationIcon = self._checkIcon(applicationIcon)
		elif self.applicationIcon is not None:
			self.applicationIcon = self._checkIcon(self.applicationIcon)

		if hostname is not None and password is not None:
			self._notifyMethod = netgrowl(hostname, password)
		elif hostname is not None or password is not None:
			raise KeyError, "Hostname and Password are both required for a network notification"

	def _checkIcon(self, data):
		if isinstance(data, str):
			return _RawImage(data)
		else:
			return data

	def register(self):
		if self.applicationIcon is not None:
			self.applicationIcon = self._checkIcon(self.applicationIcon)

		regInfo = {GROWL_APP_NAME: self.applicationName,
				   GROWL_NOTIFICATIONS_ALL: self.notifications,
				   GROWL_NOTIFICATIONS_DEFAULT: self.defaultNotifications,
				   GROWL_APP_ICON:self.applicationIcon,
				  }
		self._notifyMethod.PostRegistration(regInfo)

	def notify(self, noteType, title, description, icon=None, sticky=False, priority=None):
		assert noteType in self.notifications
		notifyInfo = {GROWL_NOTIFICATION_NAME: noteType,
					  GROWL_APP_NAME: self.applicationName,
					  GROWL_NOTIFICATION_TITLE: title,
					  GROWL_NOTIFICATION_DESCRIPTION: description,
					 }
		if sticky:
			notifyInfo[GROWL_NOTIFICATION_STICKY] = 1

		if priority is not None:
			notifyInfo[GROWL_NOTIFICATION_PRIORITY] = priority

		if icon:
			notifyInfo[GROWL_NOTIFICATION_ICON] = self._checkIcon(icon)

		self._notifyMethod.PostNotification(notifyInfo)
