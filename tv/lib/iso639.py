# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s},
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""Holds the international standard for short codes for language names.
"""

TWO_LETTERS_CODE = "alpha2"
THREE_LETTERS_CODE = "alpha3"
LENGTH_MAP = {2: TWO_LETTERS_CODE, 3: THREE_LETTERS_CODE}

def find(value, key=None):
    """For a given language code value, returns the language name.

    >>> find('en')
    {'alpha2': 'en', 'alpha3': 'eng', 'name': u'English'}
    >>> find('foo', THREE_LETTERS_CODE)
    None

    :param value: language code value.  example: 'en'

    :param key: either None, ``TWO_LETTER_CODE`` or
        ``THREE_LETTERS_CODE``

    :returns: the language dict
    """
    if value is None:
        return None
    parts = None
    if "_" in value:
        parts = value.split("_")
        value = parts[0]
    if key is None:
        try:
            key = LENGTH_MAP[len(value)]
        except (TypeError, KeyError):
            return None
    for lang in LANGUAGES_MAP:
        if key in lang and lang[key] == value:
            langdict = dict(lang)
            if parts:
                langdict["name"] = u"%s (%s)" % (langdict["name"], parts[1])
            return langdict
    return None

LANGUAGES_MAP = [
    {"alpha2": "",   "alpha3": "und", "name": u"Unspecified"},
    {"alpha2": "af", "alpha3": "afr", "name": u"Afrikaans"},
    {"alpha2": "sq", "alpha3": "alb", "name": u"Albanian"},
    {"alpha2": "sq", "alpha3": "sqi", "name": u"Albanian"},
    {"alpha2": "am", "alpha3": "amh", "name": u"Amharic"},
    {"alpha2": "ar", "alpha3": "ara", "name": u"Arabic"},
    {"alpha2": "hy", "alpha3": "arm", "name": u"Armenian"},
    {"alpha2": "hy", "alpha3": "hye", "name": u"Armenian"},
    {"alpha2": "as", "alpha3": "asm", "name": u"Assamese"},
    {"alpha2": "ay", "alpha3": "aym", "name": u"Aymara"},
    {"alpha2": "az", "alpha3": "aze", "name": u"Azerbaijani"},
    {"alpha2": "eu", "alpha3": "baq", "name": u"Basque"},
    {"alpha2": "eu", "alpha3": "eus", "name": u"Basque"},
    {"alpha2": "be", "alpha3": "bel", "name": u"Belarusian"},
    {"alpha2": "bn", "alpha3": "ben", "name": u"Bengali"},
    {"alpha2": "bs", "alpha3": "bos", "name": u"Bosnian"},
    {"alpha2": "br", "alpha3": "bre", "name": u"Breton"},
    {"alpha2": "bg", "alpha3": "bul", "name": u"Bulgarian"},
    {"alpha2": "my", "alpha3": "bur", "name": u"Burmese"},
    {"alpha2": "my", "alpha3": "mya", "name": u"Burmese"},
    {"alpha2": "ca", "alpha3": "cat", "name": u"Catalan"},
    {"alpha2": "zh", "alpha3": "chi", "name": u"TradChinese"},
    {"alpha2": "zh", "alpha3": "zho", "name": u"TradChinese"},
    {"alpha2": "cz", "alpha3": "cze", "name": u"Czech"},
    {"alpha2": "cs", "alpha3": "ces", "name": u"Czech"},
    {"alpha2": "da", "alpha3": "dan", "name": u"Danish"},
    {"alpha2": "nl", "alpha3": "dut", "name": u"Dutch"},
    {"alpha2": "nl", "alpha3": "nld", "name": u"Dutch"},
    {"alpha2": "dz", "alpha3": "dzo", "name": u"Dzongkha"},
    {"alpha2": "en", "alpha3": "eng", "name": u"English"},
    {"alpha2": "eo", "alpha3": "epo", "name": u"Esperanto"},
    {"alpha2": "et", "alpha3": "est", "name": u"Estonian"},
    {"alpha2": "fo", "alpha3": "fao", "name": u"Faroese"},
    {"alpha2": "", "alpha3": "fil", "name": u"Filipino"},
    {"alpha2": "fi", "alpha3": "fin", "name": u"Finnish"},
    {"alpha2": "fr", "alpha3": "fre", "name": u"French"},
    {"alpha2": "fr", "alpha3": "fra", "name": u"French"},
    {"alpha2": "fy", "alpha3": "fry", "name": u"Western Frisian"},
    {"alpha2": "ka", "alpha3": "geo", "name": u"Georgian"},
    {"alpha2": "ka", "alpha3": "kat", "name": u"Georgian"},
    {"alpha2": "de", "alpha3": "ger", "name": u"German"},
    {"alpha2": "de", "alpha3": "deu", "name": u"German"},
    {"alpha2": "", "alpha3": "nds", "name": u"LowGerman"},
    {"alpha2": "gl", "alpha3": "glg", "name": u"Galician"},
    {"alpha2": "gd", "alpha3": "gla", "name": u"ScottishGaelic"},
    {"alpha2": "ga", "alpha3": "gle", "name": u"IrishGaelic"},
    {"alpha2": "gv", "alpha3": "glv", "name": u"ManxGaelic"},
    {"alpha2": "",   "alpha3": "grc", "name": u"GreekAncient"},
    {"alpha2": "el", "alpha3": "gre", "name": u"Greek"},
    {"alpha2": "el", "alpha3": "ell", "name": u"Greek"},
    {"alpha2": "gn", "alpha3": "grn", "name": u"Guarani"},
    {"alpha2": "gu", "alpha3": "guj", "name": u"Gujarati"},
    {"alpha2": "he", "alpha3": "heb", "name": u"Hebrew"},
    {"alpha2": "hi", "alpha3": "hin", "name": u"Hindi"},
    {"alpha2": "hu", "alpha3": "hun", "name": u"Hungarian"},
    {"alpha2": "is", "alpha3": "ice", "name": u"Icelandic"},
    {"alpha2": "is", "alpha3": "isl", "name": u"Icelandic"},
    {"alpha2": "id", "alpha3": "ind", "name": u"Indonesian"},
    {"alpha2": "it", "alpha3": "ita", "name": u"Italian"},
    {"alpha2": "jv", "alpha3": "jav", "name": u"JavaneseRom"},
    {"alpha2": "ja", "alpha3": "jpn", "name": u"Japanese"},
    {"alpha2": "kl", "alpha3": "kal", "name": u"Greenlandic"},
    {"alpha2": "kn", "alpha3": "kan", "name": u"Kannada"},
    {"alpha2": "ks", "alpha3": "kas", "name": u"Kashmiri"},
    {"alpha2": "kk", "alpha3": "kaz", "name": u"Kazakh"},
    {"alpha2": "km", "alpha3": "khm", "name": u"Khmer"},
    {"alpha2": "rw", "alpha3": "kin", "name": u"Kinyarwanda"},
    {"alpha2": "ky", "alpha3": "kir", "name": u"Kirghiz"},
    {"alpha2": "ko", "alpha3": "kor", "name": u"Korean"},
    {"alpha2": "ku", "alpha3": "kur", "name": u"Kurdish"},
    {"alpha2": "", "alpha3": "ckb", "name": u"Central Kurdish"},
    {"alpha2": "", "alpha3": "csb", "name": u"Kashubian"},
    {"alpha2": "lo", "alpha3": "lao", "name": u"Lao"},
    {"alpha2": "la", "alpha3": "lat", "name": u"Latin"},
    {"alpha2": "lv", "alpha3": "lav", "name": u"Latvian"},
    {"alpha2": "lt", "alpha3": "lit", "name": u"Lithuanian"},
    {"alpha2": "lb", "alpha3": "ltz", "name": u"Luxembourgish"},
    {"alpha2": "mk", "alpha3": "mac", "name": u"Macedonian"},
    {"alpha2": "mk", "alpha3": "mkd", "name": u"Macedonian"},
    {"alpha2": "ml", "alpha3": "mal", "name": u"Malayalam"},
    {"alpha2": "mr", "alpha3": "mar", "name": u"Marathi"},
    {"alpha2": "ms", "alpha3": "may", "name": u"MalayRoman"},
    {"alpha2": "ms", "alpha3": "msa", "name": u"MalayRoman"},
    {"alpha2": "mg", "alpha3": "mlg", "name": u"Malagasy"},
    {"alpha2": "mt", "alpha3": "mlt", "name": u"Maltese"},
    {"alpha2": "mo", "alpha3": "mol", "name": u"Moldavian"},
    {"alpha2": "mn", "alpha3": "mon", "name": u"Mongolian"},
    {"alpha2": "ne", "alpha3": "nep", "name": u"Nepali"},
    {"alpha2": "nb", "alpha3": "nob", "name": u"Norwegian"},
    {"alpha2": "no", "alpha3": "nor", "name": u"Norwegian"},
    {"alpha2": "nn", "alpha3": "nno", "name": u"Nynorsk"},
    {"alpha2": "ny", "alpha3": "nya", "name": u"Nyanja"},
    {"alpha2": "oc", "alpha3": "oci", "name": u"Occitan"},
    {"alpha2": "or", "alpha3": "ori", "name": u"Oriya"},
    {"alpha2": "om", "alpha3": "orm", "name": u"Oromo"},
    {"alpha2": "pa", "alpha3": "pan", "name": u"Punjabi"},
    {"alpha2": "fa", "alpha3": "per", "name": u"Persian"},
    {"alpha2": "fa", "alpha3": "fas", "name": u"Persian"},
    {"alpha2": "pl", "alpha3": "pol", "name": u"Polish"},
    {"alpha2": "pt", "alpha3": "por", "name": u"Portuguese"},
    {"alpha2": "qu", "alpha3": "que", "name": u"Quechua"},
    {"alpha2": "ro", "alpha3": "rum", "name": u"Romanian"},
    {"alpha2": "ro", "alpha3": "ron", "name": u"Romanian"},
    {"alpha2": "rn", "alpha3": "run", "name": u"Rundi"},
    {"alpha2": "ru", "alpha3": "rus", "name": u"Russian"},
    {"alpha2": "sa", "alpha3": "san", "name": u"Sanskrit"},
    {"alpha2": "sr", "alpha3": "scc", "name": u"Serbian"},
    {"alpha2": "sr", "alpha3": "srp", "name": u"Serbian"},
    {"alpha2": "hr", "alpha3": "scr", "name": u"Croatian"},
    {"alpha2": "hr", "alpha3": "hrv", "name": u"Croatian"},
    {"alpha2": "si", "alpha3": "sin", "name": u"Sinhalese"},
    {"alpha2": "",   "alpha3": "sit", "name": u"Tibetan"},
    {"alpha2": "sk", "alpha3": "slo", "name": u"Slovak"},
    {"alpha2": "sk", "alpha3": "slk", "name": u"Slovak"},
    {"alpha2": "sl", "alpha3": "slv", "name": u"Slovenian"},
    {"alpha2": "se", "alpha3": "sme", "name": u"Sami"},
    {"alpha2": "",   "alpha3": "smi", "name": u"Sami"},
    {"alpha2": "sd", "alpha3": "snd", "name": u"Sindhi"},
    {"alpha2": "so", "alpha3": "som", "name": u"Somali"},
    {"alpha2": "es", "alpha3": "spa", "name": u"Spanish"},
    {"alpha2": "su", "alpha3": "sun", "name": u"SundaneseRom"},
    {"alpha2": "sw", "alpha3": "swa", "name": u"Swahili"},
    {"alpha2": "sv", "alpha3": "swe", "name": u"Swedish"},
    {"alpha2": "ta", "alpha3": "tam", "name": u"Tamil"},
    {"alpha2": "tt", "alpha3": "tat", "name": u"Tatar"},
    {"alpha2": "te", "alpha3": "tel", "name": u"Telugu"},
    {"alpha2": "tg", "alpha3": "tgk", "name": u"Tajiki"},
    {"alpha2": "tl", "alpha3": "tgl", "name": u"Tagalog"},
    {"alpha2": "th", "alpha3": "tha", "name": u"Thai"},
    {"alpha2": "bo", "alpha3": "tib", "name": u"Tibetan"},
    {"alpha2": "bo", "alpha3": "bod", "name": u"Tibetan"},
    {"alpha2": "ti", "alpha3": "tir", "name": u"Tigrinya"},
    {"alpha2": "",   "alpha3": "tog", "name": u"Tongan"},
    {"alpha2": "tr", "alpha3": "tur", "name": u"Turkish"},
    {"alpha2": "tk", "alpha3": "tuk", "name": u"Turkmen"},
    {"alpha2": "ug", "alpha3": "uig", "name": u"Uighur"},
    {"alpha2": "uk", "alpha3": "ukr", "name": u"Ukrainian"},
    {"alpha2": "ur", "alpha3": "urd", "name": u"Urdu"},
    {"alpha2": "uz", "alpha3": "uzb", "name": u"Uzbek"},
    {"alpha2": "vi", "alpha3": "vie", "name": u"Vietnamese"},
    {"alpha2": "cy", "alpha3": "wel", "name": u"Welsh"},
    {"alpha2": "cy", "alpha3": "cym", "name": u"Welsh"},
    {"alpha2": "yi", "alpha3": "yid", "name": u"Yiddish"},
    {"alpha2": "zu", "alpha3": "zul", "name": u"Zulu"}
]

if __name__ == "__main__":
    # This goes through all the languages we support in
    # resources/locale/ and runs them through find and prints the ones
    # that aren't in LANGUAGES_MAP.
    import os
    langs = [mem[:-3] for mem in os.listdir("../resources/locale/")
             if mem.endswith(".mo")]

    unknown = []
    for mem in langs:
        ret = find(mem)
        if ret == None:
            unknown.append(mem)
        print "%s -> %s" % (mem, ret)
