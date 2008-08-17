from miro.test.framework import MiroTestCase

from miro import xhtmltools

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
