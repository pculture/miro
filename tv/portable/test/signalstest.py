from miro import signals

from miro.test.framework import MiroTestCase

class TestSignaller(signals.SignalEmitter):
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'signal1', 'signal2')

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
        self.signaller.connect('signal1', self.callback)
        self.signaller.disconnect('signal1', self.callback)
        self.signaller.emit('signal1')
        self.assertEquals(self.callbacks, [])

    def test_missing_callback(self):
        self.assertRaises(KeyError, self.signaller.connect,
                'signal3', self.callback)
        self.assertEquals(self.callbacks, [])

    def test_connect_args(self):
        self.signaller.connect('signal1', self.callback, 'bar')
        self.signaller.emit('signal1', 'foo')
        self.checkSingleCallback(self.signaller, 'foo', 'bar')

    def test_nothing_connected(self):
        self.signaller.connect('signal1', self.callback)
        self.signaller.emit('signal2', 'foo')
        self.assertEquals(self.callbacks, [])
