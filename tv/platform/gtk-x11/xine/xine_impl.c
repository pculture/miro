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

#include "Python.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "xine_impl.h"
#include <gdk-pixbuf/gdk-pixbuf.h>
#include <xine/video_out.h>

const char *viz_available (_Xine* xine, const char *viz)
{
  int j;
  for (j = 0; xine->viz_available[j]; j++) {
    if (!strcmp(viz, xine->viz_available[j])) {
      return xine->viz_available[j];
    }
  }
  return NULL;
}

const char *const pref_viz[] = {
  "goom",
  "oscope",
  "fftscope",
  "fftgraph",
  NULL
};

static int Y_table[256];
static int RCr_table[256];
static int GCr_table[256];
static int GCb_table[256];
static int BCb_table[256];
static int tables_initialized = 0;

static void build_tables() {
  int i;
  if (tables_initialized)
    return;
  for (i = 0; i < 256; i++) {
    Y_table[i] = (i - 16) * 255 * 256 / 219;
    RCr_table[i] = (i - 128) * 127 * 256 * 1.402 / 112;
    GCr_table[i] = (i - 128) * 127 * 256 * -.714 / 112;
    GCb_table[i] = (i - 128) * 127 * 256 * -.344 / 112;
    BCb_table[i] = (i - 128) * 127 * 256 * 1.772 / 112;
  }
  tables_initialized = 1;
}

_Xine* xineCreate(xine_event_listener_cb_t event_callback, 
        void* event_callback_data)
{
    _Xine* xine;
    int i;
    const char *const *video_plugins;

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
    xine->viz_available = xine_list_post_plugins_typed (xine->xine, XINE_POST_TYPE_AUDIO_VISUALIZATION);
    xine->viz_name = NULL;
    for (i = 0; pref_viz[i]; i++) {
      const char *viz = viz_available(xine, pref_viz[i]);
      if (viz) {
	xine->viz_name = viz;
	break;
      }
    }
    if (!xine->viz_name) {
      xine->viz_name = xine->viz_available [0];
    }
    xine->viz = NULL;

    /* Create a second xine instance.  This one will be only used for testing
     * if we can play a file
     */
    xine->tester.xine = xine_new();
    xine_init(xine->tester.xine);
    xine->tester.videoPort = xine_open_video_driver(xine->xine, "auto", 
            XINE_VISUAL_TYPE_NONE, NULL);
    xine->tester.audioPort = xine_open_audio_driver(xine->xine, "none", NULL);
    xine->tester.stream = xine_stream_new(xine->tester.xine,
            xine->tester.audioPort, xine->tester.videoPort);

    /* Create a third xine instance.  This one will be used for
       querying data about the movie */
    xine->data_mine.xine = xine_new();
    xine_init(xine->data_mine.xine);
    xine->data_mine.videoPort = xine_new_framegrab_video_port(xine->xine);
    xine->data_mine.audioPort = xine_open_audio_driver(xine->xine, "none", NULL);
    xine->data_mine.stream = xine_stream_new(xine->data_mine.xine,
            xine->data_mine.audioPort, xine->data_mine.videoPort);
    xine->data_mine.current_filename = NULL;

    video_plugins = xine_list_audio_output_plugins (xine->data_mine.xine) ;
    for (i = 0; video_plugins[i]; i++) {
      printf ("%s\n", video_plugins[i]);
    }

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

void _xineSwitchToViz(_Xine* xine)
{
  const char *const *inputs;
  xine_post_out_t *source;
  xine_post_in_t *sink;
  xine_audio_port_t *audios[] = { xine->audioPort, NULL };
  xine_video_port_t *videos[] = { xine->videoPort, NULL };

  if (xine->viz || !xine->viz_name)
    return;

  xine->viz = xine_post_init (xine->xine, xine->viz_name, 1, audios, videos);
  if (xine->viz) {
    inputs = xine_post_list_inputs(xine->viz);
    source = xine_get_audio_source (xine->stream);
    sink = xine_post_input(xine->viz, inputs[0]);
    xine_post_wire (source, sink);
  }
}

void _xineSwitchToNormal(_Xine* xine)
{
  xine_post_out_t *source;

  if (!xine->viz)
    return;

  source = xine_get_video_source (xine->stream);
  xine_post_wire_video_port(source, xine->videoPort);

  source = xine_get_audio_source (xine->stream);
  xine_post_wire_audio_port(source, xine->audioPort);

  xine_post_dispose (xine->xine, xine->viz);
  xine->viz = NULL;
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
    _xineSwitchToNormal (xine);
}

void xineDetach(_Xine* xine)
{
    xine_event_queue_t* eventQueue;

    if(!xine->attached) return;

    // This was a XINE_GUI_SEND_SELECT_VISUAL, but that was crashing
    // See ticket #3649
    xine_port_send_gui_data(xine->videoPort,
			    XINE_GUI_SEND_WILL_DESTROY_DRAWABLE, NULL);
    xine_close(xine->stream);
    xine_dispose(xine->stream);
    xine_close_audio_driver(xine->xine, xine->audioPort);
    xine_close_video_driver(xine->xine, xine->videoPort);
    XCloseDisplay(xine->display);
    xine->attached = 0;

    /* Save this so that no one accesses xine twice at once. */
    eventQueue = xine->eventQueue;
    /* Allow threads, since xine_event_dispose_queue joins on the queue thread. */
    Py_BEGIN_ALLOW_THREADS    
    xine_event_dispose_queue(eventQueue);
    Py_END_ALLOW_THREADS    
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

int xineCanPlayFile(_Xine* xine, const char* filename)
{
    /* Implementation note: The tester stream is not quite the same as the
     * xine stream that we use to play the files.  In particular, it has a NULL
     * visual, instead of visual that points to the window we will draw in.
     * This doesn't seem to produce bad results, however.
     */

    int rv;
    rv = xine_open(xine->tester.stream, filename);
    if(rv) {
        xine_close(xine->tester.stream);
    }
    return rv;
}

int xineDataMineFilename(_Xine* xine, const char* filename)
{
  int rv;
  if (xine->data_mine.current_filename) {
    if (!strcmp (filename, xine->data_mine.current_filename)) {
      return 1;
    }
    xineDataMineClose(xine);
  }
  rv = xine_open(xine->data_mine.stream, filename);
  if (rv) {
    xine->data_mine.current_filename = strdup (filename);
  }
  return rv;
}

int xineFileDuration(_Xine* xine, const char* filename)
{
    int rv;
    int duration;
    int dummy, dummy2;
    rv = xineDataMineFilename(xine, filename);
    if (rv == 0)
      return -1;
    rv = xine_get_pos_length(xine->data_mine.stream, &dummy, &dummy2, &duration);
    if (rv == 0)
      return -1;
    return duration;
}

static unsigned char normalize(int val) {
  if (val < 0)
    val = 0;
  if (val > (255 << 8))
    val = 255 << 8;
  val = val + 127;
  val = val >> 8;
  return val;
}

int xineFileScreenshot(_Xine *xine, const char* filename, const char *screenshot)
{
    int rv;
    int duration;
    xine_video_frame_t frame;
    int i, j;
    int CbOffset;
    int CrOffset;
    unsigned char *out_data;
    GdkPixbuf *pixbuf;
    xine_video_port_t *video_out;

    rv = xineDataMineFilename(xine, filename);
    if (rv == 0)
      return 1;
    duration = xineFileDuration(xine, filename);
    if(duration == -1)
      return 1;
    if (!xine_get_stream_info (xine->data_mine.stream, XINE_STREAM_INFO_HAS_VIDEO))
      return 1;
    rv = xine_play(xine->data_mine.stream, 0, duration / 2);
    if (rv == 0)
      return 1;
    video_out = xine->data_mine.videoPort;
    if (video_out->get_property (video_out, VO_PROP_NUM_STREAMS) == 0) {
        return 1;
    }
    rv = xine_get_next_video_frame (video_out, &frame);
    if (rv == 0)
      return 1;
    if (frame.colorspace != XINE_IMGFMT_YV12 &&
	frame.colorspace != XINE_IMGFMT_YUY2) {
      xine_free_video_frame (video_out, &frame);
      return 0;
    }
    build_tables();
    out_data = malloc (frame.width * frame.height * 3);
    switch (frame.colorspace) {
    case XINE_IMGFMT_YV12:
      CrOffset = frame.width * frame.height;
      CbOffset = frame.width * frame.height + (frame.width / 2) * (frame.height / 2);
      for (j = 0; j < frame.height; j++) {
	for (i = 0; i < frame.width; i++) {
	  int pixel = j * frame.width + i;
	  int subpixel = (j / 2) * (frame.width / 2) + (i / 2);
	  int Y = Y_table[frame.data[pixel]];
	  out_data[pixel * 3] =
	    normalize(Y +
		      RCr_table[frame.data[CrOffset + subpixel]]);
	  out_data[pixel * 3 + 1] =
	    normalize(Y +
		      GCr_table[frame.data[CrOffset + subpixel]] +
		      GCb_table[frame.data[CbOffset + subpixel]]);
	  out_data[pixel * 3 + 2] =
	    normalize(Y +
		      BCb_table[frame.data[CbOffset + subpixel]]);
	}
      }
      break;

    case XINE_IMGFMT_YUY2:
      CrOffset = 3;
      CbOffset = 1;
      for (j = 0; j < frame.height; j++) {
	for (i = 0; i < frame.width; i++) {
	  int pixel = j * frame.width + i;
	  int subpixel = (j * frame.width + i) / 2 * 4;
	  int Y = Y_table[frame.data[pixel * 2]];
	  out_data[pixel * 3] =
	    normalize(Y +
		      RCr_table[frame.data[CrOffset + subpixel]]);
	  out_data[pixel * 3 + 1] =
	    normalize(Y +
		      GCr_table[frame.data[CrOffset + subpixel]] +
		      GCb_table[frame.data[CbOffset + subpixel]]);
	  out_data[pixel * 3 + 2] =
	    normalize(Y +
		      BCb_table[frame.data[CbOffset + subpixel]]);
	}
      }
      break;
    }
    pixbuf = gdk_pixbuf_new_from_data (out_data, GDK_COLORSPACE_RGB, 0,
				       8, frame.width, frame.height, frame.width * 3,
				       NULL, NULL);
    gdk_pixbuf_save (pixbuf, screenshot, "png", NULL, NULL);
    gdk_pixbuf_unref (pixbuf);
    free (out_data);
    xine_free_video_frame (xine->data_mine.videoPort, &frame);
    return 1;
}

void xineDataMineClose(_Xine *xine)
{
  if (xine->data_mine.current_filename) {
    free (xine->data_mine.current_filename);
    xine->data_mine.current_filename = NULL;

    xine_close(xine->data_mine.stream);
    xine_dispose(xine->data_mine.stream);
    xine_close_audio_driver(xine->data_mine.xine, xine->data_mine.audioPort);
    xine_close_video_driver(xine->data_mine.xine, xine->data_mine.videoPort);

    xine->data_mine.videoPort = xine_new_framegrab_video_port(xine->xine);
    xine->data_mine.audioPort = xine_open_audio_driver(xine->xine, "none", NULL);
    xine->data_mine.stream = xine_stream_new(xine->data_mine.xine,
					     xine->data_mine.audioPort,
					     xine->data_mine.videoPort);
  }
}

void xineSelectFile(_Xine* xine, const char* filename)
{
    if(!xine->attached) return;
    xine_close(xine->stream);
    if (!xine_open(xine->stream, filename))
        printf("Unable to open file '%s'\n", filename);
    if (xine_get_stream_info (xine->stream, XINE_STREAM_INFO_HAS_VIDEO)) {
      _xineSwitchToNormal(xine);
    } else {
      _xineSwitchToViz(xine);
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

void xineSetViz (_Xine* xine, const char *viz)
{
  viz = viz_available (xine, viz);
  if (viz)
    xine->viz_name = viz;
}

void xineSetVolume(_Xine* xine, int volume)
{
    if(!xine->attached) return;
    xine_set_param(xine->stream, XINE_PARAM_AUDIO_AMP_LEVEL, volume);
}

int xineGetVolume(_Xine* xine)
{
    if(!xine->attached) return 0;
    return xine_get_param(xine->stream, XINE_PARAM_AUDIO_AMP_LEVEL);
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
    if(!xine->attached) {
        return 0; // This should cause an exception to be raised upstream
    }
    return xine_get_pos_length(xine->stream, &dummy, position, length);
}
