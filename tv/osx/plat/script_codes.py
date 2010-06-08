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
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

def map_to_two_letters_code(code):
    for pair in OSX_SCRIPT_CODES_LIST:
        if pair[0] == code and pair[1] is not None:
            return pair[1]
    return None

OSX_SCRIPT_CODES_LIST = [
    (0,   "en"),  # English
    (1,   "fr"),  # French
    (2,   "de"),  # German
    (3,   "it"),  # Italian
    (4,   "nl"),  # Dutch
    (5,   "sv"),  # Swedish
    (6,   "es"),  # Spanish
    (7,   "da"),  # Danish
    (8,   "pt"),  # Portuguese
    (9,   "no"),  # Norwegian
    (10,  "he"),  # Hebrew
    (11,  "ja"),  # Japanese
    (12,  "ar"),  # Arabic
    (13,  "fi"),  # Finnish
    (14,  "el"),  # Greek
    (15,  "is"),  # Icelandic
    (16,  "mt"),  # Maltese
    (17,  "tr"),  # Turkish
    (18,  "hr"),  # Croatian
    (19,  "zh"),  # TradChinese
    (20,  "ur"),  # Urdu
    (21,  "hi"),  # Hindi
    (22,  "th"),  # Thai
    (23,  "ko"),  # Korean
    (24,  "lt"),  # Lithuanian
    (25,  "pl"),  # Polish
    (26,  "hu"),  # Hungarian
    (27,  "et"),  # Estonian
    (28,  "lv"),  # Latvian
    (29,  "se"),  # Sami
    (30,  "fo"),  # Faroese
    (31,  None),  # Farsi
    (31,  "fa"),  # Persian
    (32,  "ru"),  # Russian
    (33,  None),  # SimpChinese
    (34,  None),  # Flemish
    (35,  "ga"),  # IrishGaelic
    (36,  "sq"),  # Albanian
    (37,  "ro"),  # Romanian
    (38,  "cz"),  # Czech
    (39,  "sk"),  # Slovak
    (40,  "sl"),  # Slovenian
    (41,  "yi"),  # Yiddish
    (42,  "sr"),  # Serbian
    (43,  "mk"),  # Macedonian
    (44,  "bg"),  # Bulgarian
    (45,  "uk"),  # Ukrainian
    (46,  None),  # Belorussian
    (47,  "uz"),  # Uzbek
    (48,  "kk"),  # Kazakh
    (49,  "az"),  # Azerbaijani
    (50,  None),  # AzerbaijanAr
    (51,  "hy"),  # Armenian
    (52,  "ka"),  # Georgian
    (53,  "mo"),  # Moldavian
    (54,  "ky"),  # Kirghiz
    (55,  "tg"),  # Tajiki
    (56,  "tk"),  # Turkmen
    (57,  "mn"),  # Mongolian
    (58,  None),  # MongolianCyr
    (59,  None),  # Pashto
    (60,  "ku"),  # Kurdish
    (61,  "ks"),  # Kashmiri
    (62,  "sd"),  # Sindhi
    (63,  "bo"),  # Tibetan
    (64,  "ne"),  # Nepali
    (65,  "sa"),  # Sanskrit
    (66,  "mr"),  # Marathi
    (67,  "bn"),  # Bengali
    (68,  "as"),  # Assamese
    (69,  "gu"),  # Gujarati
    (70,  "pa"),  # Punjabi
    (71,  "or"),  # Oriya
    (72,  "ml"),  # Malayalam
    (73,  "kn"),  # Kannada
    (74,  "ta"),  # Tamil
    (75,  "te"),  # Telugu
    (76,  "si"),  # Sinhalese
    (77,  "my"),  # Burmese
    (78,  "km"),  # Khmer
    (79,  "lo"),  # Lao
    (80,  "vi"),  # Vietnamese
    (81,  "id"),  # Indonesian
    (82,  "tl"),  # Tagalog
    (83,  "ms"),  # MalayRoman
    (84,  "ml"),  # MalayArabic
    (85,  "am"),  # Amharic
    (86,  "ti"),  # Tigrinya
    (87,  "om"),  # Oromo
    (88,  "so"),  # Somali
    (89,  "sw"),  # Swahili
    (90,  "rw"),  # Kinyarwanda
    (90,  None),  # Ruanda
    (91,  "rn"),  # Rundi
    (92,  "ny"),  # Nyanja
    (92,  None),  # Chewa
    (93,  "mg"),  # Malagasy
    (94,  "eo"),  # Esperanto
    (128, "cy"),  # Welsh
    (129, "eu"),  # Basque
    (130, "ca"),  # Catalan
    (131, "la"),  # Latin
    (132, "qu"),  # Quechua
    (133, "gn"),  # Guarani
    (134, "ay"),  # Aymara
    (135, "tt"),  # Tatar
    (136, "ug"),  # Uighur
    (137, "dz"),  # Dzongkha
    (138, "jv"),  # JavaneseRom
    (139, "su"),  # SundaneseRom
    (140, "gl"),  # Galician
    (141, "af"),  # Afrikaans
    (142, "br"),  # Breton
    (143, None),  # Inuktitut
    (144, "gd"),  # ScottishGaelic
    (145, "gv"),  # ManxGaelic
    (146, "ga"),  # IrishGaelicScript
    (147, "tog"), # Tongan
    (148, "grc"), # GreekAncient
    (149, "kl"),  # Greenlandic
    (150, None),  # AzerbaijanRoman
    (151, "nn")   # Nynorsk
]
