# -*- coding: utf-8 -*-

"""Munge a .po file so we English-bound can see what strings aren't marked 
for translation yet.

Run this with a .po file as an argument.  It will set the translated strings 
to be the same as the English, but with vowels in the wrong case:

    ./poxx.py locale/xx/LC_MESSAGES/django.po    

Then set LANGUAGE_CODE='xx' in settings.py, and you'll see wacky case for
translated strings, and normal case for strings that still need translating.

This code is in the public domain.

"""

import string
import re, sys
try:
    import polib    # from http://bitbucket.org/izi/polib
except ImportError:
    print "You need to install polib.  Do:"
    print ""
    print "   pip install polib"
    sys.exit()
import HTMLParser


def wc(c):
    return c == "'" or c in string.letters

def nwc(c):
    return not wc(c)

TRANSFORM = (
    # INW?, NIW?, match, WC?, NW?, replacement
    (False, False, "an", False, False, "un"),
    (False, False, "An", False, False, "Un"),
    (False, False, "au", False, False, "oo"),
    (False, False, "Au", False, False, "Oo"),
    (False, False, "a", True, False, "e"),
    (False, False, "A", True, False, "E"),
    (False, False, "en", False, True, "ee"),
    (True, False, "ew", False, False, "oo"),
    (True, False, "e", False, True, "e-a"),
    (False, True, "e", False, False, "i"),
    (False, True, "E", False, False, "I"),
    (True, False, "f", False, False, "ff"),
    (True, False, "ir", False, False, "ur"),
    (True, False, "i", False, False, "ee"),  # FIXME
    (True, False, "ow", False, False, "oo"),
    (False, True, "o", False, False, "oo"),
    (False, True, "O", False, False, "Oo"),
    (True, False, "o", False, False, "u"),
    (False, False, "the", False, False, "zee"),
    (False, False, "The", False, False, "Zee"),
    (False, False, "th", False, True, "t"),
    (True, False, "tion", False, False, "shun"),
    (True, False, "u", False, False, "oo"),
    (True, False, "U", False, False, "Oo"),
    (False, False, "v", False, False, "f"),
    (False, False, "V", False, False, "F"),
    (False, False, "w", False, False, "v"),
    (False, False, "W", False, False, "V")
)


def chef_transform(s):
    # old_s = s
    out = []

    in_word = False  # in a word?
    i_seen = 0       # seen an i?

    # this is awful--better to do a real lexer
    while s:
        if s.startswith((".", "!", "?")):
            in_word = False
            i_seen = 0
            out.append(s[0])
            s = s[1:]
            continue

        for mem in TRANSFORM:
            if in_word and not mem[0]:
                continue
            if not in_word and mem[1]:
                continue
            if not s.startswith(mem[2]):
                continue
            try:
                if mem[3] and not wc(s[len(mem[2])]):
                    continue
            except IndexError:
                continue

            try:
                if mem[4] and not nwc(s[len(mem[2])]):
                    continue
            except IndexError:
                continue

            out.append(mem[5])
            s = s[len(mem[2]):]
            in_word = True
            break

        else:
            out.append(s[0])
            s = s[1:]

    # print old_s, "->", out
    return u"".join(out)

class HtmlAwareMessageMunger(HTMLParser.HTMLParser):
    def __init__(self):
        HTMLParser.HTMLParser.__init__(self)
        self.s = ""

    def result(self):
        return self.s

    def xform(self, s):
        return chef_transform(s)

    def handle_starttag(self, tag, attrs, closed=False):
        self.s += "<" + tag
        for name, val in attrs:
            self.s += " "
            self.s += name
            self.s += '="'
            if name in ['alt', 'title']:
                self.s += self.xform(val)
            else:
                self.s += val
            self.s += '"'
        if closed:
            self.s += " /"
        self.s += ">"

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs, closed=True)

    def handle_endtag(self, tag):
        self.s += "</" + tag + ">"

    def handle_data(self, data):
        # We don't want to munge placeholders, so split on them, keeping them
        # in the list, then xform every other token.
        toks = re.split(r"(%\(\w+\)[ds])", data)
        for i, tok in enumerate(toks):
            if i % 2:
                self.s += tok
            else:
                self.s += self.xform(tok)

    def handle_charref(self, name):
        self.s += "&#" + name + ";"

    def handle_entityref(self, name):
        self.s += "&" + name + ";"

def translate_string(s):
    hamm = HtmlAwareMessageMunger()
    hamm.feed(s)
    out = hamm.result()

    if out.endswith(" >"):
        return out[:-2] + " bork! >"
    elif out.endswith("\n"):
        return out[:-2] + " bork bork bork!\n"
    return out + " bork!"


def munge_one_file(fname):
    po = polib.pofile(fname)
    po.metadata["Language"] = "Swedish Chef"
    po.metadata["Plural-Forms"] = "nplurals=2; plural= n != 1"
    po.metadata["Content-Type"] = "text/plain; charset=UTF-8"
    count = 0
    for entry in po:
        if entry.msgid_plural:
            entry.msgstr_plural["0"] = translate_string(entry.msgid_plural)
            entry.msgstr_plural["1"] = translate_string(entry.msgid)
        else:
            entry.msgstr = translate_string(entry.msgid)

        if 'fuzzy' in entry.flags:
            entry.flags.remove('fuzzy') # clear the fuzzy flag
        count += 1
    print "Munged %d messages in %s" % (count, fname)
    po.save()

if __name__ == "__main__":
    for fname in sys.argv[1:]:
        munge_one_file(fname)
