import objc
from AppKit import *

def set(n):
    NSThread.setThreadPriority_(n)

def setNormalPriority():
    set(.5)

def setBackgroundPriority():
    set(.25)

def setHighPriority():
    set(.75)

def setMaximumPriority():
    set(1.0)
