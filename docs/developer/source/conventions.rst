=============
 Conventions
=============

Source code
===========

Follow PEP-8 [1]_ except in these cases:

1. unit tests because the Python unittest module doesn't
2. interfacing with Cocoa in the OSX platform code

.. [1] http://www.python.org/dev/peps/pep-0008/


Source control (git)
====================

Source code is stored in a git repository.  Web access is at
http://git.participatoryculture.org/miro .


cloning
-------

If you have git write access::

   % git clone ssh://<username>@pcf1.pculture.org/var/git/miro

If you don't::

   % git clone http://git.participatoryculture.org/miro


fetching
--------

::

   % git fetch
   % git rebase origin


pushing with git access
-----------------------

::

   % git push origin master


pushing without git access
--------------------------

If the changes you're making are associated with a bug already, then
do::

   % rm -Rf patches
   % git format-patch -o patches origin


Then attach the files in ``patches`` directory to the bug report.

If you don't have an associated bug report already, make one with a clear
description of what the problem is and what you did to solve it.

If no one gets back to you within a few days, send a note to the
develop mailing list or find one of us on IRC in ``#miro-hackers`` on
freenode.net.
