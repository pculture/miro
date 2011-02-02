import unittest
from miro.httpauthtools import decode_auth_header, HTTPAuthPassword

class DecodeAuthHeaderTest(unittest.TestCase):
    def test_valid_basic(self):
        for header, decoded in (
            ('Basic realm="secure"', ("basic", "secure", None)),
            ('Basic realm="r w s"', ("basic", "r w s", None)),
            ):
            self.assertEquals(decode_auth_header(header), decoded)

    def test_valid_digest(self):
        ret = decode_auth_header(
            'Digest realm="atlanta.com",domain="sip:boxesbybob.com", '
            'qop="auth", nonce="f84f1cec41e6cbe5aea9c8e88d359", '
            'opaque="", stale=FALSE, algorithm=MD5')
        self.assertEquals(ret, ("digest", "atlanta.com", "sip:boxesbybob.com"))

        ret = decode_auth_header(
            'Digest realm="testrealm@host.com", qop="auth,auth-int", '
            'nonce="dcd98b7102dd2f0e8b11d0f600bfb0c093", '
            'opaque="5ccc069c403ebaf9f0171e9517f40e41"')
        self.assertEquals(ret, ("digest", "testrealm@host.com", None))

    def test_invalid(self):
        # missing everything
        self.assertRaises(ValueError, decode_auth_header, "")

        # missing realm
        self.assertRaises(ValueError, decode_auth_header, "Basic")
        self.assertRaises(ValueError, decode_auth_header, "Digest")

        # bogus scheme
        self.assertRaises(AssertionError, decode_auth_header,
                          'Foo realm="foo.com"')
