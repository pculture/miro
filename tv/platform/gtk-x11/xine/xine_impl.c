/*
# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.
*/

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

#ifdef INCLUDE_XINE_DRIVER_HACK
static int miro_using_xv_driver_hack = 0;
#endif

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

#ifdef INCLUDE_XINE_DRIVER_HACK
static void miro_xine_list_recycle_elem(xine_list_t *list,  xine_list_elem_t *elem) {
  elem->next = list->free_elem_list;
  elem->prev = NULL;

  list->free_elem_list = elem;
  list->free_elem_list_size++;
}


void miro_xine_list_remove(xine_list_t *list, xine_list_iterator_t position) {
  xine_list_elem_t *elem = (xine_list_elem_t*)position;

  if (elem) {
    xine_list_elem_t *prev = elem->prev;
    xine_list_elem_t *next = elem->next;

    if (prev)
      prev->next = next;
    else
      list->elem_list_front = next;

    if (next)
      next->prev = prev;
    else
      list->elem_list_back = prev;

    miro_xine_list_recycle_elem(list, elem);
    list->elem_list_size--;
  }
}

xine_list_iterator_t miro_xine_list_front(xine_list_t *list) {
  return list->elem_list_front;
}
#endif

_Xine* xineCreate(xine_event_listener_cb_t event_callback, 
        void* event_callback_data)
{
    _Xine* xine;
    int i;
    /*    const char *const *video_plugins;*/

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

    return xine;
}

void xineDestroy(_Xine* xine)
{
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

void xineAttach(_Xine* xine, const char* displayName, Drawable d,
		const char *driver, int sync, int use_xv_hack)
{
    x11_visual_t vis;
    double screenWidth, screenHeight;

    if(xine->attached) {
        xineDetach(xine);
    }

    /* Store drawable info in the */
    xine->drawable = d;

    xine->display = XOpenDisplay(displayName);
    XSynchronize(xine->display, sync);

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
    // try to use char *driver for video, default to "auto" if NULL
    if (!driver) {
      driver = "auto";
    }

    xine->videoPort = xine_open_video_driver(xine->xine, driver,
         XINE_VISUAL_TYPE_X11, (void *)&vis);

#ifdef INCLUDE_XINE_DRIVER_HACK
    // by default, don't use the hack
    miro_using_xv_driver_hack = 0;
    if (xine->videoPort) {
      // if we're using the hack and the driver is "xv", then
      // we turn the hack on.
      if (use_xv_hack && !strncmp("xv", driver, 3)) {
        miro_using_xv_driver_hack = 1;
      }
    }
#endif

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
#ifdef INCLUDE_XINE_DRIVER_HACK
    xv_driver_t* driver;
    xine_list_iterator_t ite;
#endif

    if(!xine->attached) return;

#ifdef INCLUDE_XINE_DRIVER_HACK
    // HACK ALERT!  For some reason, setting the XV port attributes
    //causes problems with certain xine-lib/X11 combinations this
    //caused #7132

    if (miro_using_xv_driver_hack) {

      driver = (xv_driver_t*)xine->videoPort->driver;
  
      while ((ite = miro_xine_list_front(driver->port_attributes)) != NULL) {
        miro_xine_list_remove (driver->port_attributes, ite);
      }
    }
#endif

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

int xineSelectFile(_Xine* xine, const char* filename)
{
    if(!xine->attached) return;
    xine_close(xine->stream);
    if (!xine_open(xine->stream, filename)) {
        return 0;
    }
    if (xine_get_stream_info (xine->stream, XINE_STREAM_INFO_HAS_VIDEO)) {
      _xineSwitchToNormal(xine);
    } else {
      _xineSwitchToViz(xine);
    }
    return 1;
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
  if (!strcmp(viz, "none") || viz[0] == 0) {
    xine->viz_name = NULL;
  } else {
    viz = viz_available (xine, viz);
    if (viz)
      xine->viz_name = viz;
    else
      xine->viz_name = xine->viz_available [0];
  }
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

char *xineVersion()
{
    return xine_get_version_string();
}
