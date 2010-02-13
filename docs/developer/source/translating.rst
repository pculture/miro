=============
Miro and i18n
=============

.. _howto-translation:

Editing Translations
====================

Translations are constantly being updated as users work on them. You
can browse them at
https://translations.launchpad.net/democracy/trunk/+pots/democracyplayer/

You can modify or review a translation by clicking on the language
name and using the Rosetta web interface.


Adding a new translation
========================

To add a new translation, it is recommended you sign up for a
launchpad account. You can do this at:
https://translations.launchpad.net/democracy/trunk/+pots/democracyplayer/+login

Next, go back to
https://translations.launchpad.net/democracy/trunk/+pots/democracyplayer
and find the box marked preferred languages.

Choose your preferred languages. They should now show up as languages
available for translation with Democracy.

Click on the language name to get started.


Testing translations on Linux
=============================

To test out your translation, make sure you get the latest source code
from git::

   git clone http://git.participatoryculture.org/miro/

Next, make sure you place your ``.po`` file in ``tv/resources/locale``.

You can request a ``.po`` file by clicking on the download link while
viewing your translation in launchpad.

Do::

   LANGUAGE=xx ./run.sh

to launch Miro in your language, where ``xx`` is the language code. For
example::

   LANGUAGE=fr ./run.sh

works for French.

For more info on building Miro in Linux, see GTKX11BuildDocs:
https://develop.participatoryculture.org/projects/democracy/wiki/GTKX11BuildDocs


Localized strings
=================

This document covers guidelines for dealing with strings that are to
be translated.


Using gettext
-------------

At the top of modules that have strings to be translated, have the
following import::

   from miro.gtcache import gettext as _

Our gettext wraps the Python module ``gettext.gettext`` with caching.

You can use it like this::

   title = _("Title")


.. Note::

   One thing to be aware of is that if you're using ``_`` for gettext,
   then you can't use it as a wildcard variable for unpacking
   tuples/lists. For example, this is bad::

      from miro.gtcache import gettext as _
      ...
      a, b, _ = sometuple

   The second use of ``_`` will override the first. Ick.


Using ngettext
--------------

FIXME - add information here.

When using ngettext, you must use the same Python variables in both
the singular and plural forms. Otherwise Launchpad doesn't let
translators do the right thing. See bug #11066
(http://bugzilla.pculture.org/show_bug.cgi?id=11066).

GOOD::

    title = ngettext("Remove feed", "Remove feeds", len(feeds))

BAD::

    title = ngettext(
            "Remove %(name)s",
            "Remove %(count)d feeds"
            len(feeds),
            {"name": feeds[0].name, "count": len(feeds)})


String expansion and translations
---------------------------------

Use Python formatting syntax. In cases where there is more than one
variable, this allows translators to reorder the variables.

Also, pass the expansion dict into the gettext/ngettext call. If
there's a variable expansion error, then ``gtcache.gettext`` will fall
back to the English string. This prevents bad translations from
preventing users from using Miro.

GOOD::

    title = _("Delete file %(filename)s?", {"filename": self.filename})

    title = _("Delete %(count)s file %(filename)s?", 
              {"count": count, "filename": self.filename})

BAD because it expands the variables before calling gettext::

    title = _("Delete file %(filename)s?" % {"filename": self.filename})
                                         ^                             ^

BAD because it uses ``%s`` instead of something like ``%(filename)s`` 
and it doesn't pass in the expansion dict into gettext::

    title = _("Delete file %s?") % self.filename
                           ^^

Long strings and translations
-----------------------------

Long strings (description of things, ...) should be formatted like
this::

    description = _(
        "This is a really long string that is formatted using explicit "
        "whitespace and explicit string delimiters.  It avoids whitespace "
        "problems that can't be seen (extra spaces, carriage returns, ... "
        "without causing parsing problems.\n"
        "\n"
        "You can do multiple paragraphs as well."
    )

If you need to expand variables in the long string, use the Python
string formatting syntax and a dict like this::

    description = _(
        "This is a long string that you find in %(shortappname)s that "
        "is translated.  Using Python string formatting syntax like this "
        "makes it easier for translators to understand what values are "
        "substituted in.  This paragraph has %(count)d two values.",
        {"count": 2, "shortappname": "Miro"}
    )


Sentence fragments
------------------

BAD::

    label1 = _("Remember")
    textentry1 = TextEntry()
    label2 = _("videos in this feed.")

which shows up as something like this:

    Remember [_______] videos in this feed.

This is bad because the sentence "Remember ______ videos in this
feed." is broken up. Translators may not see the two parts near each
other and therefore won't be able to put this sentence together
correctly.

GOOD because it doesn't compose things preventing re-ordering::

    label1 = _("Remember this many videos in this feed:")
    textentry1 = TextEntry()

which shows up as something like this:

    Remember this many videos in this feed: [________]


One-word string problems
------------------------

Many strings to be translated are only one word.  In some cases, the
word may be used in different contexts and should get translated
differently.  The problem is that gettext globs the uses together into
one translatable string.

There's more details about this problem at
http://www.gnu.org/s/libc/manual/html_node/GUI-program-problems.html .

The way we deal with it is to use the ``|`` symbol to provide clarity
as to which context this particular single word is being used in, then
peel it off at usage by calling ``gtcache.declarify``.

For example::

    from miro.gtcache import gettext as _
    from miro.gtcache import declarify

    all1_text = _('All')
    all2_text = declarify(_('View|All'))
    
In this example, "View|All" doesn't get globbed with "All" because
they're different strings.  Translators can translate them differently
and they should up correctly in the ui.
