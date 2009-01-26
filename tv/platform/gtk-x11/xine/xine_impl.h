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

/**************************************************************************
 * xine_impl.h
 *
 * Implementations for the Xine class's methods.
 *
 * Almost all the work for the Xine class gets done in xine_impl.c.  xine.pyx
 * then wraps the functions.  This keeps xine.pyx from overflowing with "cdef
 * extern ..." statements
 *
 **************************************************************************/

#include <glib.h>
#include <X11/Xlib.h>
#include <X11/extensions/XShm.h>
#include <X11/extensions/Xvlib.h>
#include <X11/Xutil.h>

#define XINE_ENABLE_EXPERIMENTAL_FEATURES 1
#include <xine/video_out.h>
#include <xine/configfile.h>
#include <xine/vo_scale.h>
#include <xine/alphablend.h>

// Taken from XINE headers
#ifdef INCLUDE_XINE_DRIVER_HACK
typedef struct xine_list_chunk_s xine_list_chunk_t;
typedef struct xine_list_s xine_list_t;
typedef void* xine_list_iterator_t;
typedef struct xine_list_elem_s xine_list_elem_t;

struct xine_list_chunk_s {
  xine_list_chunk_t *next_chunk;            /* singly linked list of chunks */

  xine_list_elem_t *elem_array;             /* the allocated elements */
  int chunk_size;                          /* element count in the chunk */
  int current_elem_id;                     /* next free elem in the chunk */
};

struct xine_list_s {
  /* list of chunks */
  xine_list_chunk_t *chunk_list;
  size_t            chunk_list_size;
  xine_list_chunk_t *last_chunk;

  /* list elements */
  xine_list_elem_t  *elem_list_front;
  xine_list_elem_t  *elem_list_back;
  size_t            elem_list_size;

  /* list of free elements */
  xine_list_elem_t  *free_elem_list;
  size_t            free_elem_list_size;
};

struct xine_list_elem_s {
  xine_list_elem_t *prev;
  xine_list_elem_t *next;
  void            *value;
};

typedef struct x11osd x11osd;

typedef struct xv_driver_s xv_driver_t;

typedef struct {
  vo_frame_t         vo_frame;

  int                width, height, format;
  double             ratio;

  XvImage           *image;
  XShmSegmentInfo    shminfo;

} xv_frame_t;

typedef struct {
  int                value;
  int                min;
  int                max;
  Atom               atom;

  cfg_entry_t       *entry;

  xv_driver_t       *this;
} xv_property_t;


struct xv_driver_s {

  vo_driver_t        vo_driver;

  config_values_t   *config;

  /* X11 / Xv related stuff */
  Display           *display;
  int                screen;
  Drawable           drawable;
  unsigned int       xv_format_yv12;
  unsigned int       xv_format_yuy2;
  XVisualInfo        vinfo;
  GC                 gc;
  XvPortID           xv_port;
  XColor             black;

  int                use_shm;
  int                use_pitch_alignment;
  xv_property_t      props[VO_NUM_PROPERTIES];
  uint32_t           capabilities;

  int                ovl_changed;
  xv_frame_t        *recent_frames[VO_NUM_RECENT_FRAMES];
  xv_frame_t        *cur_frame;
  x11osd            *xoverlay;

  /* all scaling information goes here */
  vo_scale_t         sc;

  xv_frame_t         deinterlace_frame;
  int                deinterlace_method;
  int                deinterlace_enabled;

  int                use_colorkey;
  uint32_t           colorkey;

  /* hold initial port attributes values to restore on exit */
  xine_list_t       *port_attributes;

  int              (*x11_old_error_handler)  (Display *, XErrorEvent *);

  xine_t            *xine;

  alphablend_t       alphablend_extra_data;

  void             (*lock_display) (void *);

  void             (*unlock_display) (void *);

  void              *user_data;

};
#else

typedef vo_driver_t xv_driver_t;

#endif

//End structures taken from internal xine headers

typedef struct {
    GMutex* lock;
    int xpos;
    int ypos;
    int width;
    int height;
} FrameInfo;

typedef struct {
    Display* display;
    int screen;
    Drawable drawable;
    double screenPixelAspect;
    FrameInfo frameInfo;
    int attached;
    xine_t* xine;
    xine_stream_t* stream;
    xine_video_port_t* videoPort;
    xine_audio_port_t* audioPort;
    const char *const* viz_available;
    const char *viz_name;
    xine_post_t* viz;
    xine_event_queue_t* eventQueue;
    xine_event_listener_cb_t event_callback;
    void* event_callback_data;
    struct {
        xine_t* xine;
        xine_stream_t* stream;
        xine_video_port_t* videoPort;
        xine_audio_port_t* audioPort;
        char *current_filename;
    } data_mine;
} _Xine;



/* Construct a Xine object */
_Xine* xineCreate(xine_event_listener_cb_t event_callback, 
        void* event_callback_data);

/* Destroy a Xine object */
void xineDestroy(_Xine* xine);

/* Set the X drawble that Xine outputs to */
void xineAttach(_Xine* xine, const char* displayName, Drawable d, const char*driver, int sync, int use_xv_hack);

/* Set the area that xine will draw to

xpos and ypos specifies the drawable's absolute screen position.
width and height specify the size of the area that xine will draw to.
*/
void xineSetArea(_Xine* xine, int xpos, int ypos, int width, int height);

/* Make Xine stop drawing to its X drawable.  */
void xineDetach(_Xine* xine);

/* Set the file to play.  Returns 1 if successfull, 0 if not. */
int xineSelectFile(_Xine* xine, const char* filename);

/* Close the data mine stream */
void xineDataMineClose(_Xine *xine);

/* Get the playback state of xine. */
int xineGetPlaying(_Xine* xine);

/* Set the playback state of xine. */
void xineSetPlaying(_Xine* xine, int isPlaying);

/* Set the viz plugin */
void xineSetViz (_Xine* xine, const char *viz);

/* Set the playback volume of xine (0, 100). */
void xineSetVolume(_Xine* xine, int volume);

/* Get the playback volume of xine (0, 100). */
int xineGetVolume(_Xine* xine);

/* Tell xine we received an expose event for the drawable it's attached to. */
void xineGotExposeEvent(_Xine* xine, int x, int y, int width, int height);

/* Seek to a time.  pos is in milliseconds */
void xineSeek(_Xine* xine, int position);

/* Get the current postion in the stream and its total length, both in
 * milliseconds.  Returns 1 on success, 0 on failure */
int xineGetPosLength(_Xine* xine, int* position, int* length);

/* Get Xine version.  Returns Xine version string. */
char *xineVersion();
