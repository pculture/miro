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
#define XINE_ENABLE_EXPERIMENTAL_FEATURES 1
#include <xine.h>

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
    } tester;
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
void xineAttach(_Xine* xine, const char* displayName, Drawable d);

/* Set the area that xine will draw to

xpos and ypos specifies the drawable's absolute screen position.
width and height specify the size of the area that xine will draw to.
*/
void xineSetArea(_Xine* xine, int xpos, int ypos, int width, int height);

/* Make Xine stop drawing to its X drawable.  */
void xineDetach(_Xine* xine);

/* Returns 1 if we can play a url, 0 if not (-1 on error) */
int xineCanPlayUrl(_Xine* xine ,const char* url);

/* Set the URL to play */
void xinePlayUrl(_Xine* xine, const char* url);

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
