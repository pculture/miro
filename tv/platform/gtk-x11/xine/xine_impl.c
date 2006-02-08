/*************************************************************************

 * xine_impl.c
 *
 * Implementations for the Xine class's methods.
 *
 * Almost all the work for the Xine class gets done in xine_impl.c.  xine.pyx
 * then wraps the functions.  This keeps xine.pyx from overflowing with "cdef
 * extern ..." statements
 *
 **************************************************************************/

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "xine_impl.h"

_Xine* xineCreate(xine_event_listener_cb_t event_callback, 
        void* event_callback_data)
{
    _Xine* xine;
    xine = (_Xine*)malloc(sizeof(_Xine));
    if(xine == NULL) return NULL;
    xine->xine = xine_new();
    xine_init(xine->xine);
    xine->attached = 0;
    xine->frameInfo.lock = g_mutex_new();
    xine->frameInfo.xpos = 0;
    xine->frameInfo.ypos = 0;
    xine->frameInfo.width = 0;
    xine->frameInfo.height = 0;
    xine->event_callback = event_callback;
    xine->event_callback_data = event_callback_data;

    /* Create a second xine instance.  This one will be only used for testing
     * if we can play a file
     */
    xine->tester.xine = xine_new();
    xine_init(xine->tester.xine);
    xine->tester.videoPort = xine_open_video_driver(xine->xine, "auto", 
            XINE_VISUAL_TYPE_NONE, NULL);
    xine->tester.audioPort = xine_open_audio_driver(xine->xine, "auto", NULL);
    xine->tester.stream = xine_stream_new(xine->tester.xine,
            xine->tester.audioPort, xine->tester.videoPort);
    return xine;
}

void xineDestroy(_Xine* xine)
{
    xine_dispose(xine->tester.stream);
    xine_close_audio_driver(xine->tester.xine, xine->tester.audioPort);  
    xine_close_video_driver(xine->tester.xine, xine->tester.videoPort);  
    xine_exit(xine->tester.xine);

    if(xine->attached) {
        xineDetach(xine);
    }
    xine_exit(xine->xine);
    g_mutex_free(xine->frameInfo.lock);
    free(xine);
}

static void destSizeCallback(void *data, int video_width, int video_height, 
        double video_pixel_aspect, int *dest_width, int *dest_height, double
        *dest_pixel_aspect)  
{
    _Xine* xine = (_Xine*)data;
    /* Should take video_pixel_aspect into account here... */
    g_mutex_lock(xine->frameInfo.lock);
    *dest_width = xine->frameInfo.width;
    *dest_height = xine->frameInfo.height;
    g_mutex_unlock(xine->frameInfo.lock);
    *dest_pixel_aspect = xine->screenPixelAspect;
}

static void frameOutputCallback(void *data, int video_width, 
        int video_height, double video_pixel_aspect, int *dest_x, int *dest_y,
        int *dest_width, int *dest_height, double *dest_pixel_aspect, int
        *win_x, int *win_y)
{
    _Xine* xine = (_Xine*)data;
    *dest_x            = 0;
    *dest_y            = 0;
    g_mutex_lock(xine->frameInfo.lock);
    *win_x             = xine->frameInfo.xpos;
    *win_y             = xine->frameInfo.ypos;
    *dest_width        = xine->frameInfo.width;
    *dest_height       = xine->frameInfo.height;
    g_mutex_unlock(xine->frameInfo.lock);
    *dest_pixel_aspect = xine->screenPixelAspect;
}

void xineAttach(_Xine* xine, const char* displayName, Drawable d)
{
    x11_visual_t vis;
    double screenWidth, screenHeight;

    if(xine->attached) {
        xineDetach(xine);
    }

    /* Store drawable info in the */
    xine->drawable = d;

    if (!XInitThreads ()) {
        printf("Can't initialize X threads.  We will probably crash soon.\n");
    }
    xine->display = XOpenDisplay(displayName);
    xine->screen = XDefaultScreen(xine->display);
    screenWidth = (DisplayWidth(xine->display, xine->screen) * 1000 /
            DisplayWidthMM(xine->display, xine->screen));
    screenHeight = (DisplayHeight(xine->display, xine->screen) * 1000 /
            DisplayHeightMM(xine->display, xine->screen));
    xine->screenPixelAspect = screenHeight / screenWidth;

    /* filling in the xine visual struct */
    vis.display = xine->display;
    vis.screen = xine->screen;
    vis.d = d;
    vis.dest_size_cb = destSizeCallback;
    vis.frame_output_cb = frameOutputCallback;
    vis.user_data = xine;
  
    /* opening xine output ports */
    xine->videoPort = xine_open_video_driver(xine->xine, "auto", 
            XINE_VISUAL_TYPE_X11, (void *)&vis);
    xine->audioPort = xine_open_audio_driver(xine->xine, "auto", NULL);

    /* open a xine stream connected to these ports */
    xine->stream = xine_stream_new(xine->xine, xine->audioPort, 
            xine->videoPort);
    /* hook our event handler into the streams events */
    xine->eventQueue = xine_event_new_queue(xine->stream);
    xine_event_create_listener_thread(xine->eventQueue,
            xine->event_callback, xine->event_callback_data);

    xine_port_send_gui_data(xine->videoPort, XINE_GUI_SEND_DRAWABLE_CHANGED, 
            (void *)d);
    xine_port_send_gui_data(xine->videoPort, XINE_GUI_SEND_VIDEOWIN_VISIBLE, 
            (void *) 1);

    xine->attached = 1;
}

void xineDetach(_Xine* xine)
{
    if(!xine->attached) return;
    xine_port_send_gui_data(xine->videoPort, XINE_GUI_SEND_SELECT_VISUAL, 
            NULL);
    xine_close(xine->stream);
    xine_event_dispose_queue(xine->eventQueue);
    xine_dispose(xine->stream);
    xine_close_audio_driver(xine->xine, xine->audioPort);  
    xine_close_video_driver(xine->xine, xine->videoPort);  
    XCloseDisplay(xine->display);

    xine->attached = 0;
}

void xineSetArea(_Xine* xine, int xpos, int ypos, int width, int height)
{
    g_mutex_lock(xine->frameInfo.lock);
    xine->frameInfo.xpos = xpos;
    xine->frameInfo.ypos = ypos;
    xine->frameInfo.width = width;
    xine->frameInfo.height = height;
    g_mutex_unlock(xine->frameInfo.lock);
}

int xineCanPlayUrl(_Xine* xine, const char* url)
{
    /* Implementation note: The tester stream is not quite the same as the
     * xine stream that we use to play the urls.  In particular, it has a NULL
     * visual, instead of visual that points to the window we will draw in.
     * This doesn't seem to produce bad results, however.
     */

    int rv;
    rv = xine_open(xine->tester.stream, url);
    if(rv) {
        xine_close(xine->tester.stream);
    }
    return rv;
}

void xinePlayUrl(_Xine* xine, const char* url)
{
    if(!xine->attached) return;
    xine_close(xine->stream);
    if (!xine_open(xine->stream, url) || 
        !xine_play(xine->stream, 0, 0)) {
        printf("Unable to open mrl '%s'\n", url);
    }
}

void xineSeek(_Xine* xine, int position)
{
    if(!xine->attached) return;
    xine_play(xine->stream, 0, position);
}

void xineSetPlaying(_Xine* xine, int isPlaying)
{
    if(!xine->attached) return;
    if(isPlaying) {
        xine_set_param(xine->stream, XINE_PARAM_SPEED, XINE_SPEED_NORMAL);
    } else {
        xine_set_param(xine->stream, XINE_PARAM_SPEED, XINE_SPEED_PAUSE);
    }
}

void xineSetVolume(_Xine* xine, int volume)
{
    if(!xine->attached) return;
    xine_set_param(xine->stream, XINE_PARAM_AUDIO_VOLUME, volume);
}

int xineGetVolume(_Xine* xine)
{
    if(!xine->attached) return 0;
    return xine_get_param(xine->stream, XINE_PARAM_AUDIO_VOLUME);
}

void xineGotExposeEvent(_Xine* xine, int x, int y, int width, int height)
{
    XExposeEvent expose;

    if(!xine->attached) return;
    /* set as much of the XExposeEvent as we can.  Some fields like serial
     * won't be filled in, but this doesn't cause problems in practice.  Totem
     * doesn't fill in anything, so our method can't be too bad. */
    memset(&expose, 0, sizeof(XExposeEvent));
    expose.x = x;
    expose.y = y;
    expose.width = width;
    expose.height = height;
    expose.display = xine->display;
    expose.window = xine->drawable;
    xine_port_send_gui_data(xine->videoPort, XINE_GUI_SEND_EXPOSE_EVENT,
            &expose);
}

int xineGetPosLength(_Xine* xine, int* position, int* length)
{
    int dummy;
    return xine_get_pos_length(xine->stream, &dummy, position, length);
}
