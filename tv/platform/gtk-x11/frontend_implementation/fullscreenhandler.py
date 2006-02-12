import gtk
import gobject

class FullscreenHandler(object):
    """Handle the main window when it's fullscreen.  This means tracking when
    the user is watching a video and not moving the mouse.  In this case, we
    hide all UI elements except the video display.

    Member variables:

    pointerIdle -- True if the pointer hasn't moved in a while.  (We hide all
            GUI widgets except the video output in this case)
    """

    def __init__(self, widgetTree, windowChanger, hideDelay = 3000):
        """Contruct a FullscreenHandler.

        hideDelay is the time, in milliseconds, that must pass without the
        pointer moving before pointerIdle is set to True
        """

        self.widgetTree = widgetTree
        self.windowChanger = windowChanger
        self.pointerIdle = False
        self.timeoutId = None
        self.motionHandlerId = None
        self.hideDelay = hideDelay

    def enable(self):
        self.motionHandlerId = self.widgetTree['main-window'].connect(
                'motion-notify-event', self.onMotion)
        self.timeoutId = gobject.timeout_add(self.hideDelay, self.onTimeout)

    def disable(self):
        if self.timeoutId is not None:
            gobject.source_remove(self.timeoutId)
            self.timeoutId = None
        if self.motionHandlerId is not None:
            self.widgetTree['main-window'].disconnect(self.motionHandlerId)
            self.motionHandlerId = None

    def resetTimer(self):
        if self.timeoutId is not None:
            gobject.source_remove(self.timeoutId)
        self.timeoutId = gobject.timeout_add(self.hideDelay, self.onTimeout)

    def onTimeout(self):
        self.windowChanger.changeState(
                self.windowChanger.VIDEO_ONLY_FULLSCREEN)
        self.pointerIdle = True
        self.timeoutId = None
        return False

    def onMotion(self, window, event):
        self.windowChanger.changeState(self.windowChanger.VIDEO_FULLSCREEN)
        self.pointerIdle = False
        self.resetTimer()

