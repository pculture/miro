"""clipboard.py.  Used to access the clipboard from python."""

from ctypes import windll, c_char_p
CF_TEXT = 1

OpenClipboard = windll.user32.OpenClipboard
GetClipboardData = windll.user32.GetClipboardData
CloseClipboard = windll.user32.CloseClipboard
GlobalLock = windll.kernel32.GlobalLock
GlobalUnlock = windll.kernel32.GlobalUnlock

def getText():
     text = None
     if OpenClipboard(None):
         try:
             hClipMem = GetClipboardData(CF_TEXT)
             if hClipMem:
                 GlobalLock.restype = c_char_p
                 text = GlobalLock(hClipMem)
                 GlobalUnlock(hClipMem)
             else:
                 print "GCD failed"
         finally:
             CloseClipboard()
     else:
         print "OPEN CLIP FAILED"
     return text
