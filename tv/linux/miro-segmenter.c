/*
 * Copyright (c) 2009 Chase Douglas
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License version 2
 * as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 */

/*
 * Modified by Geoffrey Lee for Miro
 *
 * Original source may be obtained from:
 * http://svn.assembla.com/svn/legend/segmenter/segmenter.c
 */

#include <sys/types.h>
#include <sys/socket.h>

#include <arpa/inet.h>

#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>    /* XXX Windows? */

#include "libavformat/avformat.h"

static AVStream *add_output_stream(AVFormatContext *output_format_context, AVStream *input_stream) {
    AVCodecContext *input_codec_context;
    AVCodecContext *output_codec_context;
    AVStream *output_stream;

    output_stream = av_new_stream(output_format_context, 0);
    if (!output_stream) {
        fprintf(stderr, "Could not allocate stream\n");
        exit(1);
    }

    input_codec_context = input_stream->codec;
    output_codec_context = output_stream->codec;

    output_codec_context->codec_id = input_codec_context->codec_id;
    output_codec_context->codec_type = input_codec_context->codec_type;
    output_codec_context->codec_tag = input_codec_context->codec_tag;
    output_codec_context->bit_rate = input_codec_context->bit_rate;
    output_codec_context->extradata = input_codec_context->extradata;
    output_codec_context->extradata_size = input_codec_context->extradata_size;

    if(av_q2d(input_codec_context->time_base) * input_codec_context->ticks_per_frame > av_q2d(input_stream->time_base) && av_q2d(input_stream->time_base) < 1.0/1000) {
        output_codec_context->time_base = input_codec_context->time_base;
        output_codec_context->time_base.num *= input_codec_context->ticks_per_frame;
    }
    else {
        output_codec_context->time_base = input_stream->time_base;
    }

    switch (input_codec_context->codec_type) {
#if LIBAVFORMAT_VERSION_MAJOR > 52
        case AVMEDIA_TYPE_AUDIO:
#else
        case CODEC_TYPE_AUDIO:
#endif
            output_codec_context->channel_layout = input_codec_context->channel_layout;
            output_codec_context->sample_rate = input_codec_context->sample_rate;
            output_codec_context->channels = input_codec_context->channels;
            output_codec_context->frame_size = input_codec_context->frame_size;
            if ((input_codec_context->block_align == 1 && input_codec_context->codec_id == CODEC_ID_MP3) || input_codec_context->codec_id == CODEC_ID_AC3) {
                output_codec_context->block_align = 0;
            }
            else {
                output_codec_context->block_align = input_codec_context->block_align;
            }
            break;
#if LIBAVFORMAT_VERSION_MAJOR > 52
        case AVMEDIA_TYPE_VIDEO:
#else
        case CODEC_TYPE_VIDEO:
#endif
            output_codec_context->pix_fmt = input_codec_context->pix_fmt;
            output_codec_context->width = input_codec_context->width;
            output_codec_context->height = input_codec_context->height;
            output_codec_context->has_b_frames = input_codec_context->has_b_frames;

            if (output_format_context->oformat->flags & AVFMT_GLOBALHEADER) {
                output_codec_context->flags |= CODEC_FLAG_GLOBAL_HEADER;
            }
            break;
    default:
        break;
    }

    return output_stream;
}

int main(int argc, char **argv)
{
    const char *input;
    double segment_duration;
    char *segment_duration_check;
    double prev_segment_time = 0;
    AVInputFormat *ifmt;
    AVOutputFormat *ofmt;
    AVFormatContext *ic = NULL;
    AVFormatContext *oc;
    AVStream *video_st;
    AVStream *audio_st;
    AVCodec *codec;
    char *output_filename;
    int video_index;
    int audio_index;
    unsigned int first_segment = 1;
    unsigned int last_segment = 0;
    int decode_done;
    int ret;
    int i;

    if (argc != 3) {
        fprintf(stderr, "Usage: %s <segment duration in seconds> <port>\n", argv[0]);
        exit(1);
    }

    av_register_all();
    av_log_set_level(AV_LOG_DEBUG);

#define LOCALHOST_STRING "tcp://127.0.0.1:"
    output_filename = malloc(strlen(argv[2]) + strlen(LOCALHOST_STRING) + 1);
    if (!output_filename) {
        fprintf(stderr, "Can't allocate memory for output filename\n");
        exit(1);
    }
    strcpy(output_filename, LOCALHOST_STRING);
    strcat(output_filename, argv[2]);
    fprintf(stderr, "OUTPUT FILENAME %s\n", output_filename);

    input = "pipe:";

    segment_duration = strtod(argv[1], &segment_duration_check);
    if (segment_duration_check == argv[1] || segment_duration == HUGE_VAL || segment_duration == -HUGE_VAL) {
        fprintf(stderr, "Segment duration time (%s) invalid\n", argv[2]);
        exit(1);
    }

    ifmt = av_find_input_format("mpegts");
    if (!ifmt) {
        fprintf(stderr, "Could not find MPEG-TS demuxer\n");
        exit(1);
    }

    ret = av_open_input_file(&ic, input, ifmt, 0, NULL);
    if (ret != 0) {
        fprintf(stderr, "Could not open input file, make sure it is an mpegts file: %d\n", ret);
        exit(1);
    }

    if (av_find_stream_info(ic) < 0) {
        fprintf(stderr, "Could not read stream information\n");
        exit(1);
    }

#if LIBAVFORMAT_VERSION_MAJOR > 52
    ofmt = av_guess_format("mpegts", NULL, NULL);
#else
    ofmt = guess_format("mpegts", NULL, NULL);
#endif
    if (!ofmt) {
        fprintf(stderr, "Could not find MPEG-TS muxer\n");
        exit(1);
    }

    oc = avformat_alloc_context();
    if (!oc) {
        fprintf(stderr, "Could not allocated output context");
        exit(1);
    }
    oc->oformat = ofmt;

    video_index = -1;
    audio_index = -1;

    video_st = audio_st = NULL;

    for (i = 0; i < ic->nb_streams && (video_index < 0 || audio_index < 0); i++) {
        switch (ic->streams[i]->codec->codec_type) {
#if LIBAVFORMAT_VERSION_MAJOR > 52
            case AVMEDIA_TYPE_VIDEO:
#else
            case CODEC_TYPE_VIDEO:
#endif
                video_index = i;
                ic->streams[i]->discard = AVDISCARD_NONE;
                video_st = add_output_stream(oc, ic->streams[i]);
                break;
#if LIBAVFORMAT_VERSION_MAJOR > 52
            case AVMEDIA_TYPE_AUDIO:
#else
            case CODEC_TYPE_AUDIO:
#endif
                audio_index = i;
                ic->streams[i]->discard = AVDISCARD_NONE;
                audio_st = add_output_stream(oc, ic->streams[i]);
                break;
            default:
                ic->streams[i]->discard = AVDISCARD_ALL;
                break;
        }
    }

    if (av_set_parameters(oc, NULL) < 0) {
        fprintf(stderr, "Invalid output format parameters\n");
        exit(1);
    }

    dump_format(oc, 0, input, 1);

    if (video_st) {
        codec = avcodec_find_decoder(video_st->codec->codec_id);
        if (!codec) {
            fprintf(stderr, "Could not find video decoder, key frames will not be honored\n");
        }
    
        if (avcodec_open(video_st->codec, codec) < 0) {
            fprintf(stderr, "Could not open video decoder, key frames will not be honored\n");
        }
    }

    if (url_fopen(&oc->pb, output_filename, URL_WRONLY) < 0) {
        fprintf(stderr, "Could not open '%s'\n", output_filename);
        exit(1);
    }

    if (av_write_header(oc)) {
        fprintf(stderr, "Could not write mpegts header to first output file\n");

        exit(1);
    }

    do {
        double segment_time;
        AVPacket packet;

        decode_done = av_read_frame(ic, &packet);
        if (decode_done < 0) {
            break;
        }

        if (av_dup_packet(&packet) < 0) {
            fprintf(stderr, "Could not duplicate packet");
            av_free_packet(&packet);
            break;
        }

#if LIBAVFORMAT_VERSION_MAJOR > 52
        if (packet.stream_index == video_index && (packet.flags & AV_PKT_FLAG_KEY)) {
#else
        if (packet.stream_index == video_index && (packet.flags & PKT_FLAG_KEY)) {
#endif
            segment_time = (double)video_st->pts.val * video_st->time_base.num / video_st->time_base.den;
        }
        else if (video_index < 0) {
            segment_time = (double)audio_st->pts.val * audio_st->time_base.num / audio_st->time_base.den;
        }
        else {
            segment_time = prev_segment_time;
        }

        if (segment_time - prev_segment_time >= segment_duration) {
            put_flush_packet(oc->pb);
            url_fclose(oc->pb);

            if (url_fopen(&oc->pb, output_filename, URL_WRONLY) < 0) {
                fprintf(stderr, "Could not open '%s'\n", output_filename);
                break;
            }

            prev_segment_time = segment_time;
        }

        ret = av_interleaved_write_frame(oc, &packet);
        if (ret < 0) {
            fprintf(stderr, "Warning: Could not write frame of stream\n");
        }
        else if (ret > 0) {
            fprintf(stderr, "End of stream requested\n");
            av_free_packet(&packet);
            break;
        }
        av_free_packet(&packet);
    } while (!decode_done);

    av_write_trailer(oc);

    if (video_st)
        avcodec_close(video_st->codec);

    for(i = 0; i < oc->nb_streams; i++) {
        av_freep(&oc->streams[i]->codec);
        av_freep(&oc->streams[i]);
    }

    url_fclose(oc->pb);
    av_free(oc);

    /* End-of-transcode marker. */
    {
        struct sockaddr_in sockaddr;
	int rc, s;

        memset(&sockaddr, 0, sizeof(sockaddr));
        sockaddr.sin_family = AF_INET;
        sockaddr.sin_port = htons(atoi(argv[2]));
        sockaddr.sin_addr.s_addr = inet_addr("127.0.0.1");
        /* Don't worry about errors - there isn't much we can do anyway. */
        s = socket(AF_INET, SOCK_STREAM, 0);
        rc = connect(s, (struct sockaddr *)&sockaddr, sizeof(sockaddr));
        close(s);
    }

    return 0;
}

// vim:sw=4:tw=4:ts=4:ai:expandtab
