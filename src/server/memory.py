# -*- coding: utf8 -*-

from __future__ import unicode_literals

from threading import Lock
from functools import wraps


class Memory(object):
    """
    A singleton containing all the memory items shared by
    all threads of the server.
    """
    def __init__(self):
        super(Memory, self).__init__()
        self._memory = {}

    def setVal(self, mid, value):
        self._memory[mid] = value

    def getVal(self, mid):
        if mid in self._memory:
            return self._memory[mid]

# this module is a singleton
_instance = None

_lock = Lock()

def getInstance():
    global _instance
    global _lock
    if _instance is None:
        with _lock:
            # re-test the _instance value, avoiding the case where another
            # thread did the initialization between the previous test and the
            # lock
            if _instance is None:
                _instance = Memory()
    return _instance

def getVal(mid):
    getInstance().getVal(mid)

def setVal(mid, val):
    getInstance().setVal(mid, val)


def singletonize(method):
    @wraps(method)
    def wrapper(*args, **kwargs):
        return method(getInstance(), *args, **kwargs)
    return wrapper

getVal = singletonize(Memory.getVal)
setVal = singletonize(Memory.setVal)
