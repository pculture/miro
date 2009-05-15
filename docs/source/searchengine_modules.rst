====================
searchengine modules
====================

Miro allows users to do searches against sites that return RSS data
for search queries.

Search engine data is stored in ``.xml`` files in ``resources/searchengines/``.
Here's an example search engine::

    <searchengine>
        <id>5min</id>
        <displayname>5min</displayname>
        <url>http://www.5min.com/Rss/Search/%s</url>
        <sort>11</sort>
    </searchengine>

``id``

    A unique id string that identifies this specific search engine.

``displayname``

    The name that appears in Miro in the search engine drop down.

``url``

    The url to use to do the search.  There are several things that
    can be expanded in the search url:

    * ``%s`` expands to the search terms
    * ``%a`` expands to 1 or 0 regarding whether or not to filter adult content
    * ``%l`` expands to the number of search results to return

``sort``

    This is the integer denoting the position this search engine takes in
    the list of search engines.

To create a new search engine, do the following:

1. create an xml file for the search engine that gets placed in
   ``resources/searchengines/``.

2. create a 16 pixel by 16 pixel 8-bit/color non-interlaced PNG image for
   the search icon.  The name of this file must be ``search_icon_<id>.png``
   where ``<id>`` is the id of the search engine.  For example, 
   ``search_icon_5min.png``.  This icon gets placed in ``resources/images/``.

3. When you're happy with your search engine data, create a bug in
   `bugzilla <http://bugzilla.pculture.org/>`_ for someone to add the
   new search engine and attach the ``.xml`` and ``.png`` files to it.


``miro.searchengines`` - search engines module
==============================================

.. automodule:: miro.searchengines
   :members:
