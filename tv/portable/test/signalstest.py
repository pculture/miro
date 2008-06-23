from miro import signals

from miro.test.framework import MiroTestCase

class TestSignaller(signals.SignalEmitter):
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'signal1', 'signal2', 
                'signal-three')
        self.signal_three_callbacks = []

    def do_signal_three(self, *args):
        self.signal_three_callbacks.append(args)

class SignalsTest(MiroTestCase):
    def setUp(self):
        self.callbacks = []
        self.signaller = TestSignaller()
        MiroTestCase.setUp(self)
        
    def callback(self, *args):
        self.callbacks.append(args)

    def checkSingleCallback(self, *values):
        self.assertEquals(len(self.callbacks), 1)
        self.assertEquals(self.callbacks[0], values)

    def test_callback(self):
        self.signaller.connect('signal1', self.callback)
        self.signaller.emit('signal1', 'foo')
        self.checkSingleCallback(self.signaller, 'foo')

    def test_disconnect(self):
        id = self.signaller.connect('signal1', self.callback)
        self.signaller.disconnect(id)
        self.signaller.emit('signal1')
        self.assertEquals(self.callbacks, [])

    def test_missing_callback(self):
        self.assertRaises(KeyError, self.signaller.connect,
                'signal5', self.callback)
        self.assertEquals(self.callbacks, [])

    def test_connect_args(self):
        self.signaller.connect('signal1', self.callback, 'bar')
        self.signaller.emit('signal1', 'foo')
        self.checkSingleCallback(self.signaller, 'foo', 'bar')

    def test_nothing_connected(self):
        self.signaller.connect('signal1', self.callback)
        self.signaller.emit('signal2', 'foo')
        self.assertEquals(self.callbacks, [])

    def test_do_method(self):
        self.signaller.connect('signal-three', self.callback)
        self.signaller.emit('signal-three', 'foo')
        self.checkSingleCallback(self.signaller, 'foo')
        self.assertEquals(self.signaller.signal_three_callbacks, [('foo',)])

    def test_weak_callback(self):
        callback_obj = WeakCallbackTester(self)
        self.signaller.connect_weak('signal1', callback_obj.callback, 0)
        self.signaller.emit('signal1')
        self.checkSingleCallback(0)
        del callback_obj
        self.signaller.emit('signal1')
        self.checkSingleCallback(0)
        self.assertEquals(len(self.signaller.get_callbacks('signal1')), 0)

    def test_weak_callback_disconnect(self):
        callback_obj = WeakCallbackTester(self)
        id = self.signaller.connect_weak('signal1', callback_obj.callback, 0)
        self.signaller.disconnect(id)
        self.signaller.emit('signal1')
        self.assertEquals(self.callbacks, [])

class WeakCallbackTester(object):
    def __init__(self, unittest):
        self.unittest = unittest

    def callback(self, obj, *values):
        self.unittest.callbacks.append(values)
