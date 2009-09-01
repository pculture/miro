=====================
 Developer how to...
=====================

... write a new frontend widget
===============================

See the sections on :ref:`platform-specific widget frontend modules 
<howto-platformwidgets>` and :ref:`portable widget frontend modules
<howto-portablewidgets>`.


... get ``Feed`` objects for all feeds
======================================

From the backend, it's easy:

*Miro 2.5 and up*::

   from miro import feed

   for f in feed.Feed.make_view():
       ...


From the frontend, it's a little harder since the frontend can't access
the database directly.  There are ``ChannelInfo`` objects in the 
``TabListManagers`` and we can iterate through those to get a list of
feeds:

*Miro 2.5 and up*::

   import app

   all_feeds = app.tab_list_manager.feed_list.get_feeds()
   all_feeds += app.tab_list_manager.audio_feed_list.get_feeds()
   all_feeds = [ci for ci in all_feeds if not ci.is_folder]
