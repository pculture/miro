InfoList is a fast, low-level table model, that can be used with the
widgets.TableView class for sorted lists of ItemInfo objects (and is theory
any other info-like object).

InfoList has a few features to make item lists quick and easy
  - can quickly lookup a row by it's id attribute.  Not having to track iters
    in python is both convenient and fast.
  - can lookup a row by it's position (this is O(N) some times, but is fast
    enough in practice)
  - keeps the list in sorted order
  - stores arbitrary attributes for each item

InfoList glues together code in many different (C-like) languages.

Here's a the other components:

  - infolist.pyx -- python module (pyrex)
  - infolist-nodelist.c -- InfoList data structions (C)
  - infolist-idmap.cpp -- simple hash table (C++)
  - infolist-gtk.c, infolist-cocoa.m -- each platform adds another file to
    implement platform-specific parts.  The hooks are definined in
    infolist-platform.h (C/Objective-C)
