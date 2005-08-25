from win32con import *
from ctypes import *
from ctypes.wintypes import *
kernel32 = windll.kernel32
GetCurrentThread = kernel32.GetCurrentThread
SetThreadPriority = kernel32.SetThreadPriority

def setNormalPriority():
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_NORMAL)

def setBackgroundPriority():
    # or possibly THREAD_PRIORITY_LOWEST, which is a bit higher
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_IDLE)

def setHighPriority():
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_ABOVE_NORMAL)

def setMaximumPriority():
    # tempting to go to THREAD_PRIORITY_TIME_CRITICAL here, but that
    # could easily cause problems for other applications.
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_HIGHEST)
