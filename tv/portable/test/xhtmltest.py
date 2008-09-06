from miro.test.framework import MiroTestCase

from miro import xhtmltools

class Test_fix_xml_header(MiroTestCase):
    def test(self):
        doc1 = """
<xml>
</xml>
""".strip()

        doc2 = """
<?xml version="1.0" encoding="utf-8"?>
<xml>
</xml>
""".strip()

        doc3 = """
<?xml version="1.0"?>
<xml>
</xml>
""".strip()

        self.assertEquals(xhtmltools.fix_xml_header(doc1, "utf-8"),
                          """
<?xml version="1.0" encoding="utf-8"?><xml>
</xml>
""".strip())

        self.assertEquals(xhtmltools.fix_xml_header(doc2, "utf-8"), doc2)
        self.assertEquals(xhtmltools.fix_xml_header(doc3, "utf-8"),
                          """
<?xml version="1.0" encoding="utf-8"?>
<xml>
</xml>
""".strip())



class Test_fix_html_header(MiroTestCase):
    def test(self):
        doc1 = """
<html>
</html>
""".strip()

        doc2 = """
<html>
<head>
<meta http=equiv="Content-Type" content="text/html; charset=utf-8">
</head>
</html>
""".strip()

        doc3 = """
<html>
<head>
</head>
</html>
""".strip()

        # doc1 is missing head tags, so we don't touch it.
        self.assertEquals(xhtmltools.fix_html_header(doc1, "utf-8"), doc1)

        # doc2 looks fine, so we don't touch it.
        self.assertEquals(xhtmltools.fix_html_header(doc2, "utf-8"), doc2)

        self.assertEquals(xhtmltools.fix_html_header(doc3, "utf-8"), 
                          """
<html>
<head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">
</head>
</html>
""".strip())

class Test_url_encode_dict(MiroTestCase):
    def test(self):
        urlencodedict = xhtmltools.url_encode_dict

        # test the empty case
        self.assertEquals(urlencodedict({}), "")

        # test regular items
        self.assertEquals(urlencodedict({"a": "b"}), "a=b")
        self.assertEquals(urlencodedict({"a": "b", "c": "d"}), 
                          "a=b&c=d")
        self.assertEquals(urlencodedict({"a": "b", "c": "d", "e": "f"}), 
                          "a=b&c=d&e=f")

        # test non string items--these log a warning, but otherwise
        # produce nothing
        self.assertEquals(urlencodedict({"a": 1}), "")

        # test weird stuff
        self.assertEquals(urlencodedict({"a": "<foo>&blah;\'\""}), 
                          "a=%3Cfoo%3E%26blah%3B%27%22")
