
VIDEO_EXTENSIONS = ['.mov', '.wmv', '.mp4', '.m4v', '.ogg', '.anx', '.mpg', '.avi', '.flv', '.mpeg', '.divx']
AUDIO_EXTENSIONS = ['.mp3', '.m4a', '.wma']

MIMETYPES_EXT_MAP = {
    'video/quicktime':  '.mov',
    'video/mpeg':       '.mpg',
    'video/mp4':        '.mp4',
    'video/flv':        '.flv',
    'video/x-flv':      '.flv',
    'video/x-ms-wmv':   '.wmv',
    'video/x-msvideo':  '.avi',
    'application/ogg':  '.ogg',
    
    'audio/mpeg':       '.mp3',
    'audio/mp4':        '.m4a',
    'audio/x-ms-wma':   '.wma',
    
    'application/x-bittorrent': '.torrent'
}

def isAllowedFilename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents video, audio or torrent.
    """
    return isVideoFilename(filename) or isAudioFilename(filename) or isTorrentFilename(filename)

def isVideoFilename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents a video file.
    """
    filename = filename.lower()
    for ext in VIDEO_EXTENSIONS:
        if filename.endswith(ext):
            return True
    return False

def isAudioFilename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents an audio file.
    """
    filename = filename.lower()
    for ext in AUDIO_EXTENSIONS:
        if filename.endswith(ext):
            return True
    return False

def isTorrentFilename(filename):
    """
    Pass a filename to this method and it will return a boolean
    saying if the filename represents a torrent file.
    """
    filename = filename.lower()
    return filename.endswith('.torrent')

def isVideoEnclosure(enclosure):
    """
    Pass an enclosure dictionary to this method and it will return a boolean
    saying if the enclosure is a video or not.
    """
    return (_hasVideoType(enclosure) or
            _hasVideoExtension(enclosure, 'url') or
            _hasVideoExtension(enclosure, 'href'))

def _hasVideoType(enclosure):
    return ('type' in enclosure and
            (enclosure['type'].startswith(u'video/') or
             enclosure['type'].startswith(u'audio/') or
             enclosure['type'] == u"application/ogg" or
             enclosure['type'] == u"application/x-annodex" or
             enclosure['type'] == u"application/x-bittorrent" or
             enclosure['type'] == u"application/x-shockwave-flash"))

def _hasVideoExtension(enclosure, key):
    return (key in enclosure and isAllowedFilename(enclosure[key]))

def guessExtension(mimetype):
    """
    Pass a mime type to this method and it will return a corresponding file
    extension, or None if it doesn't know about the type.
    """
    return MIMETYPES_EXT_MAP.get(mimetype)
