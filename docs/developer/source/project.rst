=======
Project
=======

This manual is the architectural and code documentation for Miro.  It's
intended for developers of Miro and anyone else who might be using
Miro code for their projects.

It is not a user guide.


Communication
=============

IRC

    We have two channels on ``freenode.net``:

    * ``#miro`` - for user-oriented discussion, support, etc
    * ``#miro-hackers`` - for developer oriented discussion, packaging,
      debugging, testing, translation issues, etc

Mailing list

    http://participatoryculture.org/mailman/listinfo/develop

Development web-site

    https://develop.participatoryculture.org/

Planet

    http://planet.getmiro.com/


Source code
===========

Trunk is unstable and is where we're doing development for the next
release.

The branches are stable and where we do development for minor point
releases.

Trunk (unstable!)::

    svn co https://svn.participatoryculture.org/svn/dtv/trunk/

Miro 2.5 branch (stable)::

    svn co https://svn.participatoryculture.org/svn/dtv/branches/Miro-2.5

Miro 2.0 branch (stable, but old)::

    svn co https://svn.participatoryculture.org/svn/dtv/branches/Miro-2.0

Miro 1.2 branch (stable, but very old)::

    svn co https://svn.participatoryculture.org/svn/dtv/branches/Miro-1.2


Documentation
=============

This manual is written using `restructured text`_.  It is "compiled"
into HTML and PDF by `Sphinx`_.  This manual is versioned alongside
Miro in the ``docs/`` directory of trunk.  See the ``README`` file for
information on how to build the manual.

.. _restructured text: http://docutils.sourceforge.net/rst.html
.. _Sphinx: http://sphinx.pocoo.org/

Additional developer-focused documentation is in the Trac wiki at
https://develop.participatoryculture.org/ .  In the wiki, you'll find
build documentation for the three Miro platforms, architecture
documentation, testing and QA documentation, information on
translating and packaging Miro, code style, and a bunch of pages that
discuss decisions made during Miro development over the eons.  Some of
this documentation will be absorbed into this manual.

There's additional material in the developer blogs and the `Miro
Planet`_.  This material tends to be on a day-by-day basis.

.. _Miro Planet: http://planet.getmiro.com/

User documentation is primarily on the Get Miro site:

:Features:   http://getmiro.com/download/features/
:Using Miro: http://getmiro.com/using-miro/
:FAQ:        http://getmiro.com/using-miro/faq/

