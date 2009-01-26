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

#define XINE_ENABLE_EXPERIMENTAL_FEATURES 1
#include <xine.h>
#include <xine/video_out.h>
#include <gdk-pixbuf/gdk-pixbuf.h>
#include <glib.h>

typedef struct {
  xine_t* xine;
  xine_stream_t* stream;
  xine_video_port_t* videoPort;
  xine_audio_port_t* audioPort;
} _Xine;

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

static void _make_new_data_mine(_Xine* xine) {
    xine->videoPort = xine_open_video_driver(xine->xine, "none", XINE_VISUAL_TYPE_NONE, NULL);
    xine->audioPort = xine_open_audio_driver(xine->xine, "none", NULL);
    xine->stream = xine_stream_new(xine->xine, xine->audioPort, xine->videoPort);
}

static void xineDataMineClose(_Xine *xine)
{
  xine_close(xine->stream);
  xine_dispose(xine->stream);
  xine_close_audio_driver(xine->xine, xine->audioPort);
  xine_close_video_driver(xine->xine, xine->videoPort);
  /*    _make_new_data_mine(xine);*/
}

static int xineDataMineFilename(_Xine* xine, const char* filename)
{
  int rv;
  rv = xine_open(xine->stream, filename);
  return rv;
}

/* duration is in ms */
static int xineFileDuration(_Xine* xine)
{
    int rv;
    int duration;
    int dummy, dummy2;
    rv = xine_get_pos_length(xine->stream, &dummy, &dummy2, &duration);
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

static int xineFileScreenshot(_Xine *xine, int position, const char *screenshot)
{
    int rv;
    xine_video_frame_t frame;
    int i, j;
    int CbOffset;
    int CrOffset;
    unsigned char *out_data;
    GdkPixbuf *pixbuf;
    xine_video_port_t *video_out;

    if (!xine_get_stream_info (xine->stream, XINE_STREAM_INFO_HAS_VIDEO))
      return 0;
    rv = xine_play(xine->stream, 0, position);
    if (rv == 0)
      return 0;
    video_out = xine->videoPort;
    if (video_out->get_property (video_out, VO_PROP_NUM_STREAMS) == 0) {
        return 1;
    }
    rv = xine_get_next_video_frame (video_out, &frame);
    if (rv == 0)
      return 0;
    if (frame.colorspace != XINE_IMGFMT_YV12 &&
	frame.colorspace != XINE_IMGFMT_YUY2) {
      xine_free_video_frame (video_out, &frame);
      return 0;
    }
    build_tables();
    out_data = g_malloc (frame.width * frame.height * 3);
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
    g_free (out_data);
    xine_free_video_frame (xine->videoPort, &frame);
    return 1;
}

int main(int argc, char *argv[])
{
  char *filename;
  char *screenshot_filename;
  int rv;
  int duration = -1;
  _Xine *xine;
  if (argc != 3) {
    return 0;
  }
  g_type_init();
  filename = argv[1];
  screenshot_filename = argv[2];

  xine = (_Xine*)g_malloc(sizeof(_Xine));
  xine->xine = xine_new();
  xine_init(xine->xine);
  _make_new_data_mine(xine);

  rv = xineDataMineFilename(xine, filename);
  if (rv != 0) {
    duration = xineFileDuration(xine);
    if (duration == -1)
      rv = 0;
    else
      rv = xineFileScreenshot(xine, duration / 2, screenshot_filename);
  }
  printf ("Miro-Movie-Data-Length: %d\n", duration);
  printf ("Miro-Movie-Data-Thumbnail: %s\n", rv ? "Success" : "Failure");
  return 0;
}
