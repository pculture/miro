from database import DDBObject
from os.path import expanduser, join
from os import makedirs
from threading import RLock

configData = {}
configLock = RLock()

def get(key):
    configLock.acquire()
    try:
	try:
	    ret = configData[key]
	except KeyError:
	    if key == 'DataDirectory':
		path = expanduser("~/Movies")
		try:
		    makedirs(join(path,'Incomplete Downloads'))
		except:
		    pass
		configData[key] = path
		ret = path
	    elif key == 'FreeSpaceTarget':
		configData[key] = '2000000000'
		ret = '2000000000'
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
