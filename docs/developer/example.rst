=========
 Example
=========

Watch history
=============

File/directory structure::

    |- watchhistory.miroext
    |- watchhistory/
       |- __init__.py         has the load/unload functions
       |- main.py             has the rest of the code referred to in __init__.py


``watchhistory.miroext``:

.. literalinclude:: ../../tv/extensions/watchhistory.miroext
   :language: ini
   :linenos:

``watchhistory/__init__.py``:

.. literalinclude:: ../../tv/extensions/watchhistory/__init__.py
   :language: python
   :linenos:

``watchhistory/main.py``:

.. literalinclude:: ../../tv/extensions/watchhistory/main.py
   :language: python
   :linenos:
