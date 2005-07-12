from database import DDBObject
from os.path import expanduser, join
from os import makedirs
from datetime import timedelta
import database

configData = {}
configLock = database.globalLock

def get(key):
    configLock.acquire()
    try:
	try:
	    ret = configData[key]
	except KeyError:
	    if key == 'DataDirectory':
		#FIXME add Windows support
		path = expanduser("~/Movies/DTV")
		try:
		    makedirs(join(path,'Incomplete Downloads'))
		except:
		    pass
		configData[key] = path
		ret = path
	    elif key == 'FreeSpaceTarget':
		configData[key] = '2000000000'
		ret = '2000000000'
	    elif key == 'DownloadsTarget':
		configData[key] = 3
		ret = 3
	    elif key == 'MaxManualDownloads':
		configData[key] = 10
		ret = 10
	    elif key == 'DefaultTimeUntilExpiration':
		configData[key] = timedelta(days=7)
		ret = timedelta(days=7)
	    else:
		raise KeyError
    finally:
	configLock.release()
    return ret

def set(key,value):
    configLock.acquire()
    try:
	configData[key]=value
    finally:
	configLock.release()
