# vlc.pyx Python binding for VLC based on KCEasy's simplevlc
# 
# Requires simplevlc.dll and simplevlc.h from KCEasy (GPL)
# http://sf.net/projects/kceasy/
cdef extern from "simplevlc.h":
    ctypedef struct SVlcInstance
    ctypedef SVlcInstance* HSVLC
    ctypedef SVlcCallbackFunc
    ctypedef enum SVlcPlaybackState:
        SVLC_CB_STATE_CHANGE    = 1
        SVLC_CB_DISPLAY_POPUP   = 2
        SVLC_CB_POSITION_CHANGE = 3
        SVLC_CB_KEY_PRESSED     = 4
    cdef int SVLC_Initialize()
    ctypedef struct SVlcStreamInfo
    ctypedef struct SVlcInterface:
        HSVLC (* create)(int verbosity)
        HSVLC (* destroy)(HSVLC svlc)
        int (* set_callback) (HSVLC, SVlcCallbackFunc, unsigned int)
        char * (* get_vlc_version)()
        void (* set_udata) (HSVLC, void *)
        void * (* get_udata) (HSVLC)
        int (* set_window) (HSVLC, unsigned int)
        int (* set_visualization) (HSVLC, char *)
        int (* set_fullscreen) (HSVLC, int)
        int (*get_fullscreen) (HSVLC)
        int (* set_fitwindow) (HSVLC, int)
        int (* get_fitwindow) (HSVLC)
        int (* set_zoom) (HSVLC, float)
        float (* get_zoom) (HSVLC)
        int (* set_volume) (HSVLC, float)
        float (* get_volume) (HSVLC)
        int (* set_mute) (HSVLC, int)
        int (* get_mute) (HSVLC)
        int (* play) (HSVLC, char *target)
        int (* stop) (HSVLC)
        int (* pause) (HSVLC, int)
        SVlcPlaybackState (* get_playback_state) (HSVLC)
        int (* set_position) (HSVLC, float)
        float (* get_position) (HSVLC)
        int (* is_seekable) (HSVLC)
        int (* get_duration) (HSVLC)
        int (* get_stream_info) (HSVLC, SVlcStreamInfo *)
    cdef int SVLC_GetInterface(SVlcInterface *)
    cdef void SVLC_Shutdown()

cdef extern from "stdlib.h":
    ctypedef unsigned int size_t
    cdef void * malloc(size_t)
    cdef void free(void *)

SVLC_Initialize()

# This is the class that actually exports SimpleVLC functionality See
# simplevlc.h for an explanation of what each of the functions
# actually do. 
#
# TODO: Callbacks, playback state info, and stream info
#
cdef class SimpleVLC:
    cdef HSVLC h
    cdef SVlcInterface *v
    def __new__(self):
        self.v = <SVlcInterface *>malloc(sizeof(SVlcInterface))
        SVLC_GetInterface(self.v)
        self.h = self.v.create(100)

    def __dealloc__(self):
        self.v.destroy(self.h)
        free(self.v)

    def getVersion(self):
        return self.v.get_vlc_version()
 
    def setWindow(self, unsigned int hwnd):
        return self.v.set_window(self.h, hwnd)

    def setVisualization(self, char *vis):
        return self.v.set_visualization(self.h, vis)

    def setFullscreen(self, int full):
        return self.v.set_fullscreen(self.h, full)

    def getFullscreen(self):
        return self.v.get_fullscreen(self.h)

    def setFitWindow(self, int fit):
        return self.v.set_fitwindow(self.h, fit)

    def getFitWindow(self):
        return self.v.get_fitwindow(self.h)

    def setZoom(self, float zoom):
        return self.v.set_zoom(self.h, zoom)

    def getZoom(self):
        return self.v.get_zoom(self.h)

    def setVolume(self, float vol):
        return self.v.set_volume(self.h, vol)

    def getVolume(self):
        return self.v.get_volume(self.h)

    def setMute(self, int mute):
        return self.v.set_mute(self.h, mute)

    def getMute(self):
        return self.v.get_mute(self.h)

    def play(self, char *target):
        return self.v.play(self.h, target)

    def stop(self):
        return self.v.stop(self.h)

    def pause(self, int pause):
        return self.v.pause(self.h, pause)

    def setPosition(self, float pos):
        return self.v.set_position(self.h, pos)

    def getPosition(self):
        return self.v.get_position(self.h)

    def isSeekable(self):
        return self.v.is_seekable(self.h)

    def getDuration(self):
        return self.v.get_duration(self.h)
