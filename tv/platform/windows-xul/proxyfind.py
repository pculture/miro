"""proxyfind.py.  Get proxy info from windows."""

from ctypes import Structure, byref, windll
from ctypes.wintypes import LPWSTR, BOOL
import logging
import re

class WINHTTP_CURRENT_USER_IE_PROXY_CONFIG(Structure):
    _fields_ = [
        ('fAutoDetect', BOOL),
        ('lpszAutoConfigUrl', LPWSTR),
        ('lpszProxy', LPWSTR),
        ('lpszProxyBypass', LPWSTR),
    ]

class ProxyInfo:
    def __init__(self):
        self.active = False
        self.host = self.port = None
        self.ignore_hosts = []

def get_proxy_info():
    proxy_info = ProxyInfo()
    ie_proxy_info = WINHTTP_CURRENT_USER_IE_PROXY_CONFIG()
    rv = windll.winhttp.WinHttpGetIEProxyConfigForCurrentUser(
            byref(ie_proxy_info))

    if not rv or ie_proxy_info.lpszProxy is None:
        return proxy_info
    proxy_info.host, proxy_info.port = \
            parse_host_and_port(ie_proxy_info.lpszProxy)
    if ie_proxy_info.lpszProxyBypass is not None:
        proxy_info.ignore_hosts = re.split("[;\s]*", 
                ie_proxy_info.lpszProxyBypass)
    return proxy_info

def parse_host_and_port(windows_proxy_string):
    for proxy in re.split("[;\s]*", windows_proxy_string):
        original_string = proxy
        if proxy.startswith("http="):
            proxy = proxy[len('http='):]
        elif '=' in proxy or proxy == '':
            continue
        if '://' in proxy:
            if proxy.startswith("http://"):
                proxy = proxy[len("http://"):]
            else:
                logging.warn("unsupported proxy scheme: %s" % original_string)
                continue
        if ':' in proxy:
            proxy, port = proxy.split(":")
            try:
                port = int(port)
            except ValueError:
                logging.warn("bad proxy port: %s" % original_string)
                continue
        else:
            port = 80
        return proxy, port
    logging.warn("couldn't find proxy: %s" % windows_proxy_string)
    return None, None
