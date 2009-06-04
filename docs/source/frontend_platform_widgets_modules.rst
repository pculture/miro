=========================================
platform-specific widget frontend modules
=========================================

Platform code is in a handful of locations depending on the platform.
All OSX platform code is in:

* ``platform/osx/plat/frontend/widgets/``

GTK-X11 and Windows platform code is in:

* ``platform/gtk-x11/plat/frontends/widgets/``
* ``platform/windows-xul/plat/frontends/widgets/``

with shared GTK widget code in:

* ``portable/frontends/widgets/gtk/``

Because of this, we created a ``widgetset`` module which is the
namespace for all platform-specific widgets and functions.

On OSX, the ``platform/osx/plat/frontends/widgets/widgetset.py``
file imports the names of all the OSX-specific widgets and functions
which are in modules in the same directory.

On GTK-X11, the
``platform/gtk-x11/plat/frontends/widgets/widgetset.py`` file imports
the names from widgets and functions in that directory as well as the
widgets and functions in
``portable/frontends/widgets/gtk/widgetset.py``.  The Windows code
does the same.

That allows us to import platform-specific widgets and functions this
way::

    from miro.plat.frontends.widgets.widgetset import Rect

If you create a new widget, here's how you figure out where to put the
code, what module it needs to be imported into so it's in the correct
namespace, and how to import and use it:

1. if it's not platform-specific:

   :code goes in: ``portable/frontends/widgets/``
   :used:         ``import miro.frontends.widgets.mymodule``

2. if it is OSX platform-specific code:

   :code goes in: ``platform/osx/plat/frontends/widgets/``
   :imported in:  ``platform/osx/plat/frontends/widgets/widgetset.py``
   :used:         ``from miro.plat.frontends.widgets.widgetset import mymodule``

3. if it is GTK code that's shared between the Windows and GTK-X11 platforms:

   :code goes in: ``portable/frontends/widgets/gtk/``
   :imported in:  ``portable/frontends/widgets/gtk/widgetset.py``
   :used:         ``from miro.plat.frontends.widgets.widgetset import mymodule``

4. if it is GTK-X11 code that is NOT shared with Windows:

   :code goes in: ``platfrom/gtk-x11/plat/frontends/widgets/``
   :imported in:  ``platform/gtk-x11/plat/frontends/widgets/widgetset.py``
   :used:         ``from miro.plat.frontends.widgets.widgetset import mymodule``

5. if it is Windows code that is NOT shared with GTK-X11:

   :code goes in: ``platform/windows-xul/plat/frontends/widgets/``
   :imported in:  ``platform/windows-xul/plat/frontends/widgets/widgetset.py``
   :used:         ``from miro.plat.frontends.widgets.widgetset import mymodule``

