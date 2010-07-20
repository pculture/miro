================================
 API for renderers on GNU/Linux
================================

General
=======

All renderers on GNU/Linux have to support the same API.  The user can
switch renderers on the command line as well as in the preferences
panel.

On the command line::

    miro --set=renderer=gstreamer

This will load the renderer located in the ``tv/linux/plat/renderers``
directory in source or in the ``miro/plat/renderers`` directory when
installed named ``gstreamerrenderer``.

If we did::

    miro --set=renderer=foo

then Miro would load the renderer located in
``tv/linux/plat/renderers/foorenderer.py`` in source or in the
``miro/plat/renderers/foorenderer.py`` when installed.

Renderer code is written in Python and follows the API.


Trouble-shooting
================

If the renderer kicks up problems in the form of exceptions, they'll
show up in the Miro logs.  The logs are located in ``~/.miro``.
Definitely worth looking here first for issues.


Implementing a renderer
=======================

1. implement the API
2. when your renderer hits an end-of-stream event, make sure it calls
   ``app.playback_manager.on_movie_finished()``
3. the xid comes from 


API
===

.. function:: get_item_type(item_info, success_callback, error_callback)

   Miro calls this to figure out what type of media item the item_info
   refers to.

   The ``success_callback`` has this signature::

       success_callback(item_type)

   where item_type is either "video", "audio", or "unplayable".   

   The ``error_callback`` has this signature::

       error_callback()

   :param item_info: a :class:`miro.messages.ItemInfo` object
   :param success_callback: function called if the type was
       successfully determined
   :param error_callback: function called if there was an error


.. function:: movie_data_program_info(movie_path, thumbnail_path)

   Miro calls this to get the information for the program that
   extracts information about the media item.

   This information is returned as a tuple.  The first item in the
   tuple is the list of arguments to be passed to subprocess to run
   the program.  The second item is the environment in which to run
   the program in.

   For the gstreamer renderer, this is a separate script called
   gst_extractor.py.

   The gstreamer renderer returns::

       ((sys.executable, extractor_path, movie_path, thumbnail_path),
         None)

   The first part is the list of arguments to run the program.

   This requires no special environment, so the second part is None.    
   
   :param movie_path: absolute path to the media file
   :param thumbnail_path: absolute path to where the thumbnail that is
       generated should be saved; for audio files, this is ignored

   :returns: (program_args, environment)

.. class:: AudioRenderer

   .. method:: select_file(iteminfo, callback, errback, sub_filename)

      Sets the renderer up to play the media item specified by
      ``iteminfo``.

      This method can be asynchronous.  It responds by calling either
      the ``callback`` or ``errback`` functions.

      If something goes awry (file can't be opened, etc.), then the
      ``errback`` function is called.

      If everything goes fine, then the ``callback`` function is called.

      ``sub_filename`` is the full path of the subtitle file that should
      be opened with this media item.

      :param iteminfo: the :class:`miro.messages.ItemInfo` object
      :param callback: the function to call if the item is opened
          successfully; it takes no arguments
      :param errback: the function to call if the item is opened
          unsuccessfully; it takes no arguments

   .. method:: get_current_time()

      Returns the current time position in the file in seconds.

   .. method:: set_current_time(seconds)

      Sets the time position in the file to the time specified by
      ``seconds``.

   .. method:: get_duration()

      Returns the total number of seconds in this media file.

   .. method:: set_volume(level)

      Sets the volume to some level between 0.0 and 3.0.

   .. method:: play()

      Play the selected file.

   .. method:: pause()

      Pause the selected file.

   .. method:: stop()

      Stop playing the selected file.

   .. method:: get_rate()

      I don't really know what this does.

   .. method:: set_rate(rate)

      Sets the playback rate.


.. class:: VideoRenderer

   Everything in AudioRenderer plus some additional methods.

   .. method:: set_widget(widget)

      Called to set the widget for video rendering.  

      ``widget.persistent_window.xid`` holds the xid to display video
      to.

      ``widget.persistent_window`` is a gtk.DrawingArea derivative.

      :param widget: The window for showing video.

   .. method:: go_fullscreen()

      Tells the renderer that Miro is requesting to go fullscreen.

   .. method:: exit_fullscreen()

      Tells the renderer that the Miro is exiting fullscreen.

   .. method:: get_subtitles()

      Returns a dict of index -> (language, filename) for available
      subtitles.

      If there are no subtitles available, return ``{}``.

   .. method:: get_subtitle_tracks()

      Returns a list of 2-tuple of (index, language) for available
      tracks.

      If there are no tracks, return ``[]``.

   .. method:: get_enabled_subtitle_track()

      Returns the currently enabled track.

   .. method:: enable_subtitle_track(track_index)

      Enables the track at ``track_index``.  This should be a valid
      track in the list returned by :meth:`VideoRenderer.get_subtitle_tracks`.

   .. method:: disable_subtitles()

      Disables subtitles.

   .. method:: select_subtitle_file(iteminfo, sub_path, 
               handle_successful_select)

      Selects an external subtitle file to display when showing the
      video item specified by iteminfo.

      If all goes well, call handle_successful_select.

   .. method:: setup_subtitle_encoding_menu(menubar)

      Adds the menu items to the encoding menu for subtitles.  This
      allows users to specify the string encoding that's used by the
      subtitle file/track they have selected.
