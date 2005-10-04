/*****************************************************************************
 * simplevlc.h: a simple shared library wrapper around libvlc
 *****************************************************************************
 * Copyright (C) 2004 Markus Kern <mkern@users.sourceforge.net>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PUROSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111, USA.
 *****************************************************************************/

#ifndef __SIMPLEVLC_H
#define __SIMPLEVLC_H


/* TODO: porting */
#define SVLC_EXPORT __declspec(dllexport)
#ifndef __C_PLUS_PLUS  /* DTV: Added check for C compiler */
#define SVLC_CC 
#else
#define SVLC_CC __cdecl
#endif


/**
 * Library version this header belongs to
 */
#define SVLC_VERSION_MAJOR	0
#define SVLC_VERSION_MINOR	1
#define SVLC_VERSION_MICRO	0


/**
 * Handle for simplevlc instance.
 */
struct _SVlcInstance; /* opaque to user, defined in svlc_instance.h */
typedef struct _SVlcInstance SVlcInstance;

/* convenient handle */
typedef SVlcInstance* HSVLC;


/**
 * Possible playback states.
 */
typedef enum
{
	SVLC_PLAYBACK_CLOSED  = 0,
	SVLC_PLAYBACK_LOADING = 1,
	SVLC_PLAYBACK_OPEN    = 2,
	SVLC_PLAYBACK_PLAYING = 3,
	SVLC_PLAYBACK_PAUSED  = 4,
	SVLC_PLAYBACK_STOPPED = 5,
	SVLC_PLAYBACK_ERROR   = 6, /* implies SVLC_PLAYBACK_CLOSED */

	/* force 32bit enum */
	SVLC_PLAYBACK_FORCE_SIZE = 0xFFFFFFFF
} SVlcPlaybackState;


/***
 * Info about open stream
 */
typedef struct
{
	int audio_streams;      /* number of audio streams */
	int video_streams;      /* number of video streams */

#if 0
	/* TODO */
	int audio_bitrate;      /* kbps */
	int audio_samplerate;   /* sample rate in Hz */
	char audio_codec[5];    /* codec string */

	int video_width;
	int video_height;
	char video_codec[5];    /* codec string */
#endif
} SVlcStreamInfo;


/**
 * Callback events and their associated data structures
 */
typedef enum
{
	SVLC_CB_STATE_CHANGE    = 0x01, /* The playback state has changed */
	SVLC_CB_DISPLAY_POPUP   = 0x02, /* The popup should be opened/closed */
	SVLC_CB_POSITION_CHANGE = 0x03, /* The playback postion has changed */
	SVLC_CB_KEY_PRESSED     = 0x04, /* A key was pressed on the display */

	/* force 32bit enum */
	SVLC_CB_FORCE_SIZE = 0xFFFFFFFF
} SVlcCallbackEvent;

/* SVLC_CB_STATE_CHANGE */

typedef struct
{
	SVlcPlaybackState old_state;
	SVlcPlaybackState new_state;
} SVlcCbStateData;

/* SVLC_CB_DISPLAY_POPUP */

typedef struct
{
	int show;                /* 1: show popup, 0: hide popup */
} SVlcCbDisplayPopupData;

/* SVLC_CB_POSITION_CHANGE */

typedef struct
{
	float position;          /* new position [0,1] */
	unsigned int duration;   /* total play length in ms */
} SVlcCbPositionChangeData;

/* SVLC_CB_KEY_PRESSED */

typedef struct
{
	int key;                 /* VLC key ID */
} SVlcCbKeyPressedData;

/* Key IDs from vlc */
#define SVLC_KEY_MODIFIER         0xFF000000
#define SVLC_KEY_MODIFIER_ALT     0x01000000
#define SVLC_KEY_MODIFIER_SHIFT   0x02000000
#define SVLC_KEY_MODIFIER_CTRL    0x04000000
#define SVLC_KEY_MODIFIER_META    0x08000000
#define SVLC_KEY_MODIFIER_COMMAND 0x10000000

#define SVLC_KEY_SPECIAL          0x00FF0000
#define SVLC_KEY_LEFT             0x00010000
#define SVLC_KEY_RIGHT            0x00020000
#define SVLC_KEY_UP               0x00030000
#define SVLC_KEY_DOWN             0x00040000
#define SVLC_KEY_SPACE            0x00050000
#define SVLC_KEY_ENTER            0x00060000
#define SVLC_KEY_F1               0x00070000
#define SVLC_KEY_F2               0x00080000
#define SVLC_KEY_F3               0x00090000
#define SVLC_KEY_F4               0x000A0000
#define SVLC_KEY_F5               0x000B0000
#define SVLC_KEY_F6               0x000C0000
#define SVLC_KEY_F7               0x000D0000
#define SVLC_KEY_F8               0x000E0000
#define SVLC_KEY_F9               0x000F0000
#define SVLC_KEY_F10              0x00100000
#define SVLC_KEY_F11              0x00110000
#define SVLC_KEY_F12              0x00120000
#define SVLC_KEY_HOME             0x00130000
#define SVLC_KEY_END              0x00140000
#define SVLC_KEY_MENU             0x00150000
#define SVLC_KEY_ESC              0x00160000
#define SVLC_KEY_PAGEUP           0x00170000
#define SVLC_KEY_PAGEDOWN         0x00180000
#define SVLC_KEY_TAB              0x00190000
#define SVLC_KEY_BACKSPACE        0x001A0000
#define SVLC_KEY_MOUSEWHEELUP     0x001B0000
#define SVLC_KEY_MOUSEWHEELDOWN   0x001C0000

#define SVLC_KEY_ASCII            0x0000007F
#define SVLC_KEY_UNSET            0


/**
 * Function implemented by the user to receive callbacks.
 * This may be called from various different threads inside VLC which means
 * you have to keep your callbacks as short as possible!
 *
 * @param svlc   Handle to simplevlc instance.
 * @param event  Reason the callback was raised.
 * @param edata  Pointer to additional event specific data.
 * @param udata  Pointer set by set_udata.
 */
typedef void SVLC_CC (*SVlcCallbackFunc) (HSVLC svlc, SVlcCallbackEvent event, void *edata, void *udata);


/**
 * Our interface. The user passes this struct in GetInterface() to retrieve
 * the function entry points.
 */
typedef struct
{
	/***************************************
	 * Instance management
	 ***************************************/

	/**
	 * Create simplevlc instance.
	 *
	 * @param verbosity  >= 0 Logging verbosity.
	 *                     -1 Quiet, don't log anything.
	 *
	 * @return  Handle  to instance on success.
	 *          NULL on error.
	 */
	HSVLC SVLC_CC (*create) (int verbosity);

	/**
	 * Destroy simplevlc instance.
	 */
	void SVLC_CC (*destroy) (HSVLC svlc);

	/**
	 * Set callback function.
	 *
	 * @param callback  The function that should be called.
	 * @param events    The events you want to be notified about.
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*set_callback) (HSVLC svlc, SVlcCallbackFunc callback, unsigned int events);

	/**
	 * Return static VLC version string.
	 */
	char const * SVLC_CC (*get_vlc_version) (void);

	/**
	 * Attach user data.
	 */
	void SVLC_CC (*set_udata) (HSVLC svlc, void *udata);

	/**
	 * Retrieve user data.
	 */
	void * SVLC_CC (*get_udata) (HSVLC svlc);


	/***************************************
	 * Video output
	 ***************************************/

	/**
	 * Set video output window.
	 *
	 * @param window  Window for video output (HWND on windows).
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*set_window) (HSVLC svlc, unsigned int window);

	/**
	 * Set visualization plugin used for audio playback.
	 *
	 * @param name  Name of the visualization plugin, e.g. "goom". NULL removes
	 *              anything previously set.
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*set_visualization) (HSVLC svlc, const char *name);

	/**
	 * Set fullscreen mode. This merely maximizes the output window on windows
	 * (probably other platforms too) so you need to set fitwindow to true and
	 * the window set with set_window must have no (non-maximized) parents.
	 *
	 * @param fullscreen  1 Switch fullscreen on
	 *                    0 Switch fullscreen off
	 *                   -1 Toggle fullscreen
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*set_fullscreen) (HSVLC svlc, int fullscreen);

	/**
	 * Get fullscreen mode.
	 *
	 * @return  1 Fullscreen on.
	 *          0 Fullscreen off.
	 *         -1 Error.
	 */
	int SVLC_CC (*get_fullscreen) (HSVLC svlc);

	/**
	 * Scale video output to match window size.
	 *
	 * @param fullscreen  1 Fit to window.
	 *                    0 Don't fit to window.
	 *                   -1 Toggle fit.
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*set_fitwindow) (HSVLC svlc, int fit);

	/**
	 * Get fit to window mode.
	 *
	 * @return  1 Fitting on.
	 *          0 Fitting off.
	 *         -1 Error.
	 */
	int SVLC_CC (*get_fitwindow) (HSVLC svlc);

	/**
	 * Zoom video. This only has an effect if fitwindow is false.
	 *
	 * @param zoom  Zoom factor (e.g. 0.5, 1.0, 1.5, 2.0).
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*set_zoom) (HSVLC svlc, float zoom);

	/**
	 * Get current zoom factor.
	 *
	 * @return >= 0 Current zoom factor.
	 *           -1 Error.
	 */
	float SVLC_CC (*get_zoom) (HSVLC svlc);


	/***************************************
	 * Audio output
	 ***************************************/

	/**
	 * Set audio volume.
	 *
	 * @param volume  Volume in [0,1].
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*set_volume) (HSVLC svlc, float volume);

	/**
	 * Get audio volume.
	 *
	 * @return >= 0 Current volume in [0,1].
	 *           -1 Error.
	 */
	float SVLC_CC (*get_volume) (HSVLC svlc);

	/**
	 * Set audio mute.
	 *
	 * @param mute  1 Mute audio
	 *              0 Unmute audio
	 *             -1 Toggle mute
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*set_mute) (HSVLC svlc, int mute);

	/**
	 * Get audio mute.
	 *
	 * @return  1 Muted.
	 *          0 Not muted.
	 *         -1 Error.
	 */
	int SVLC_CC (*get_mute) (HSVLC svlc);


	/***************************************
	 * Playback
	 ***************************************/

	/**
	 * Play target.
	 *
	 * @param target  Target to play, e.g. filename.
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*play) (HSVLC svlc, const char *target);

	/**
	 * Stop playback and remove any targets.
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*stop) (HSVLC svlc);

	/**
	 * Set pause.
	 *
	 * @param pause  1 Pause playback
	 *               0 Resume playback
	 *              -1 Toggle pause
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*pause) (HSVLC svlc, int pause);

	/**
	 * Retrieve playback state.
	 *
	 * @return  See declaration of SVlcPlaybackState
	 */
	SVlcPlaybackState SVLC_CC (*get_playback_state) (HSVLC svlc);

	/**
	 * Seek to new stream position (if seekable).
	 *
	 * @param position  Position in [0,1] to seek to.
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*set_position) (HSVLC svlc, float position);

	/**
	 * Get current stream position.
	 *
	 * @return >= 0 Current postition in [0,1].
	 *           -1 Error.
	 */
	float SVLC_CC (*get_position) (HSVLC svlc);

	/**
	 * Get seekability of current stream.
	 *
	 * @return  1 Current stream is seekable
	 *          0 Current stream is not seekable
	 *         -1 Error.
	 */
	int SVLC_CC (*is_seekable) (HSVLC svlc);

	/**
	 * Get play length of current stream.
	 *
	 * @return > 0 Stream duration in milliseconds.
	 *           0 No time data available for this stream.
	 *          -1 Error.
	 */
	int SVLC_CC (*get_duration) (HSVLC svlc);

	/**
	 * Get information about an the currently opened stream.
	 *
	 * @param info  Pointer to SVlcStreamInfo which is filled with the data.
	 *
	 * @return  0 Success.
	 *         -1 Error.
	 */
	int SVLC_CC (*get_stream_info) (HSVLC svlc, SVlcStreamInfo *info);

} SVlcInterface;


/**
 * Fill the passed interface struct with function entry points.
 *
 * @return  0 for success.
 *         -1 on error.
 */
SVLC_EXPORT int SVLC_CC SVLC_GetInterface(SVlcInterface *intf);


/**
 * Called by the user to retrieve interface version.
 * micro changes are binary compatible.
 * minor changes are source compatible.
 * major changes break stuff.
 */
SVLC_EXPORT void SVLC_CC SVLC_GetVersion(int *major, int *minor, int *micro);


/**
 * Called by the user once after loading the library.
 * Do not use the library if this fails.
 *
 * @return  0 for success.
 *         -1 on error.
 */
SVLC_EXPORT int SVLC_CC SVLC_Initialize(void);


/**
 * Called by the user before unloading the library.
 */
SVLC_EXPORT void SVLC_CC SVLC_Shutdown(void);


/**
 * Convenience typedefs for pointers to exported functions.
 */
typedef int  SVLC_CC (*SVLC_GetInterface_t) (SVlcInterface *intf);
typedef void SVLC_CC (*SVLC_GetVersion_t)   (int *major, int *minor, int *micro);
typedef int  SVLC_CC (*SVLC_Initialize_t)   (void);
typedef void SVLC_CC (*SVLC_Shutdown_t)     (void);

#endif /* __SIMPLEVLC_H */
