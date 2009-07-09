========================
database related modules
========================

Modules in the ``miro`` package namespace located in ``portable/`` in
the source tarball that contain storage or database related code.

Miro's database is stored using sqlite in a file named ``sqlitedb``.

Prior to Miro 2.5, the database consisted of two tables:
``dtv_variables`` and ``dtv_objects``.  The ``dtv_objects`` table had
an id field and an object field that was a binary blob holding binary
Python pickle objects.

As of Miro 2.5, the database is now a relational database with no
Python pickles in it.

.. Note::

   We encourage outside tools to access and query this data.

   The tables should be pretty self-explanatory.  If you are confused
   about the data in the tables, look at the ``schema.py`` module
   which holds schema information.

   As of Miro 2.5, this is the only way to access metadata stored
   in Miro.


``storedatabase`` - crux of the database storage code
=====================================================

.. automodule:: miro.storedatabase
   :members:

``schema`` - Holds Schema objects
=================================

.. automodule:: miro.schema
   :members:

``item`` - Item
===============

.. automodule:: miro.item
   :members:

``feed`` - Feed
===============

.. automodule:: miro.feed
   :members:

``folder`` - Folders
====================

.. automodule:: miro.folder
   :members:

``frontendstate`` - Frontend state
==================================

.. automodule:: miro.frontendstate
   :members:

``guide`` - Guide and sites
===========================

.. automodule:: miro.guide
   :members:

``playlist`` - Playlists
========================

.. automodule:: miro.playlist
   :members:

``tabs`` - tabs, tab order and friends
======================================

.. automodule:: miro.tabs
   :members:

``theme`` - ThemeHistory
========================

.. automodule:: miro.theme
   :members:
