
from twisted.trial import unittest
from twisted.internet import defer
from coherence.dispatcher import Dispatcher, UnknownSignal, Receiver, \
        SignalingProperty, ChangedSignalingProperty, CustomSignalingProperty

class TestDispatcher(Dispatcher):
    __signals__ = {'test': 'Test signal'}

class SimpleTarget(object):

    def __init__(self):
        self.called = 0
        self.called_a = 0
        self.called_b = 0
        self.called_c = 0
        self.called_d = 0

    def callback(self):
        self.called += 1

    def updater(self, arg1, arg2, value, arg4, key_a='p', variable=None):
        setattr(self, variable, value)
        setattr(self, "%s_%s" % (variable, arg2), key_a)

    def plus(self, plus, variable=False):
        setattr(self, variable, getattr(self, variable) + plus)

    def fail_before(self, plus, variable=False):
        raise TypeError(':(')
        self.update(plus, variable=variable)

class TestDispatching(unittest.TestCase):

    def setUp(self):
        self.called_counter = 0
        self.dispatcher = TestDispatcher()
        self.target = SimpleTarget()

    def test_simple_emit(self):

        receiver = self.dispatcher.connect('test', self.target.callback)
        self.dispatcher.emit('test')
        self.assertEquals(self.target.called, 1)

        self.dispatcher.emit('test')
        self.assertEquals(self.target.called, 2)

        self.dispatcher.disconnect(receiver)
        self.dispatcher.emit('test')
        self.assertEquals(self.target.called, 2)

    def test_simple_deferred_emit(self):

        receiver = self.dispatcher.connect('test', self.target.callback)
        self.dispatcher.deferred_emit('test')
        self.assertEquals(self.target.called, 1)

        self.dispatcher.deferred_emit('test')
        self.assertEquals(self.target.called, 2)

        self.dispatcher.disconnect(receiver)
        self.dispatcher.deferred_emit('test')
        self.assertEquals(self.target.called, 2)

    def test_simple_save_emit(self):

        def call(res):
            return self.dispatcher.save_emit('test')

        def test(res, val):
            self.assertEquals(self.target.called, val)


        receiver = self.dispatcher.connect('test', self.target.callback)

        dfr = defer.succeed(None)
        dfr.addCallback(call)
        dfr.addCallback(test, 1)
        dfr.addCallback(call)
        dfr.addCallback(test, 2)
        dfr.addCallback(lambda x: self.dispatcher.disconnect(receiver))
        dfr.addCallback(call)
        dfr.addCallback(test, 2)
        return dfr

    def test_connect_typo(self):
        self.assertRaises(UnknownSignal, self.dispatcher.connect, 'Test', None)

    def test_disconnect_none_receiver(self):
        """
        trying to disconnect with None shouldn't fail, it is a valid use case
        """
        self.dispatcher.disconnect(None)

    def test_disconnect_false_receiver(self):
        """
        this receiver isn't coming from this dispatcher
        """
        # this is REALLY constructed. you may *not* instantiate a Receiver yourself anyway
        rec = Receiver('test', None, None, None)
        self.dispatcher.disconnect(rec)

    def test_disconnect_wrong_signal_receiver(self):
        rec = Receiver('Test', None, None, None)
        self.assertRaises(UnknownSignal, self.dispatcher.disconnect, rec)

    def test_disconnect_not_receiver(self):
        self.assertRaises(TypeError, self.dispatcher.disconnect, 'test')

    def test_emit_false_signal(self):
        self.assertRaises(UnknownSignal, self.dispatcher.emit, False)

    def test_emit_without_receivers(self):
        self.dispatcher.emit('test')
        self.assertEquals(self.target.called, 0)

    def test_emit_with_multiple_receiver(self):
        rc1 = self.dispatcher.connect('test', self.target.updater,
                1, 2, variable='va1')
        rc2 = self.dispatcher.connect('test', self.target.updater,
                'value', 2, variable='variable')
        rc3 = self.dispatcher.connect('test', self.target.updater,
                'other', 2, variable='one')

        self.dispatcher.emit('test', self, 'other', key_a='q')
        # check rc1
        self.assertEquals(self.target.va1, 1)
        self.assertEquals(self.target.va1_other, 'q')
        #check rc2
        self.assertEquals(self.target.variable, 'value')
        self.assertEquals(self.target.variable_other, 'q')
        # check rc3
        self.assertEquals(self.target.one, 'other')
        self.assertEquals(self.target.one_other, 'q')

        # now removing the one in the middel
        self.dispatcher.disconnect(rc2)

        # and try again with other data
        self.dispatcher.emit('test', self, 'other', key_a='thistime')
        # check rc1
        self.assertEquals(self.target.va1, 1)
        self.assertEquals(self.target.va1_other, 'thistime')
        #check rc2
        self.assertEquals(self.target.variable, 'value')
        self.assertEquals(self.target.variable_other, 'q')
        # check rc3
        self.assertEquals(self.target.one, 'other')
        self.assertEquals(self.target.one_other, 'thistime')

        # no keyword
        self.dispatcher.emit('test', self, 'a')
        # worked for rc1 and rc3 with the default value
        self.assertEquals(self.target.va1_a, 'p')
        self.assertEquals(self.target.one_a, 'p')
        # but not on rc2
        self.assertFalse(hasattr(self.target, 'variable_a'))

        self.dispatcher.disconnect(rc1)
        self.dispatcher.disconnect(rc3)

    def test_emit_multiple_with_failing_in_between(self):


        rc1 = self.dispatcher.connect('test', self.target.plus,
                1, variable='called_a')
        rc2 = self.dispatcher.connect('test', self.target.plus,
                2, variable='called_b')
        rc3 = self.dispatcher.connect('test', self.target.fail_before,
                3, variable='called_c')
        rc4 = self.dispatcher.connect('test', self.target.plus,
                4, variable='called_d')

        self.dispatcher.emit('test')
        self.assertEquals(self.target.called_a, 1)
        self.assertEquals(self.target.called_b, 2)
        self.assertEquals(self.target.called_c, 0)
        self.assertEquals(self.target.called_d, 4)

        self.dispatcher.emit('test')
        self.assertEquals(self.target.called_a, 2)
        self.assertEquals(self.target.called_b, 4)
        self.assertEquals(self.target.called_c, 0)
        self.assertEquals(self.target.called_d, 8)

        self.dispatcher.disconnect(rc1)
        self.dispatcher.disconnect(rc2)
        self.dispatcher.disconnect(rc3)
        self.dispatcher.disconnect(rc4)

# Receiver tests

class TestReceiver(unittest.TestCase):

    def setUp(self):
        self.called = 0

    def _callback(self, *args, **kw):
        self.called += 1
        self.args = args
        self.kw = kw

    def test_simple_calling(self):
        rec = Receiver('test', self._callback, (), {})
        self.assertEquals(rec.signal, 'test')
        rec()
        self.assertEquals(self.called, 1)
        self.assertEquals(self.args, ())
        self.assertEquals(self.kw, {})

        rec()
        self.assertEquals(self.called, 2)
        self.assertEquals(self.args, ())
        self.assertEquals(self.kw, {})

        rec()
        self.assertEquals(self.called, 3)
        self.assertEquals(self.args, ())
        self.assertEquals(self.kw, {})

    def test_calling_with_args(self):
        rec = Receiver('test', self._callback, (1, 2, 3), {'test': 'a'})
        self.assertEquals(rec.signal, 'test')
        rec(0)
        self.assertEquals(self.called, 1)
        self.assertEquals(self.args, (0, 1, 2, 3))
        self.assertEquals(self.kw, {'test': 'a'})

        rec(-1)
        self.assertEquals(self.called, 2)
        self.assertEquals(self.args, (-1, 1, 2, 3))
        self.assertEquals(self.kw, {'test': 'a'})

        rec(-2)
        self.assertEquals(self.called, 3)
        self.assertEquals(self.args, (-2, 1, 2, 3))
        self.assertEquals(self.kw, {'test': 'a'})

    def test_calling_with_kw(self):
        rec = Receiver('test', self._callback, (1, 2, 3), {'test': 'a'})
        self.assertEquals(rec.signal, 'test')
        rec(p='q')
        self.assertEquals(self.called, 1)
        self.assertEquals(self.args, (1, 2, 3))
        self.assertEquals(self.kw, {'test': 'a', 'p': 'q'})

        rec(other='wise')
        self.assertEquals(self.called, 2)
        self.assertEquals(self.args, (1, 2, 3))
        self.assertEquals(self.kw, {'test': 'a', 'other': 'wise'})

        rec(and_one='more')
        self.assertEquals(self.called, 3)
        self.assertEquals(self.args, (1, 2, 3))
        self.assertEquals(self.kw, {'test': 'a', 'and_one': 'more'})

    def test_calling_with_clashing_kw(self):
        rec = Receiver('test', self._callback, (1, 2, 3), {'test': 'a', 'p': 'a'})
        self.assertEquals(rec.signal, 'test')
        rec(p='q')
        self.assertEquals(self.called, 1)
        self.assertEquals(self.args, (1, 2, 3))
        self.assertEquals(self.kw, {'test': 'a', 'p': 'q'})

        rec(other='wise')
        self.assertEquals(self.called, 2)
        self.assertEquals(self.args, (1, 2, 3))
        self.assertEquals(self.kw, {'test': 'a', 'other': 'wise', 'p': 'a'})

    def test_calling_with_clashing_kw_and_args(self):
        rec = Receiver('test', self._callback, (1, 2, 3), {'test': 'a', 'p': 'a'})
        self.assertEquals(rec.signal, 'test')
        # without
        rec()
        self.assertEquals(self.called, 1)
        self.assertEquals(self.args, (1, 2, 3))
        self.assertEquals(self.kw, {'test': 'a', 'p': 'a'})

        rec(1, 2, 7, test='True', o='p')
        self.assertEquals(self.called, 2)
        self.assertEquals(self.args, (1, 2, 7, 1, 2, 3))
        self.assertEquals(self.kw, {'test': 'True', 'o': 'p', 'p': 'a'})


    def test_repr(self):
        rec = Receiver('test', 'callback', (0, 1, 2), {})
        self.assertIn('%s' % id(rec), '%r' % rec)
        self.assertIn('test', '%r' % rec)
        self.assertIn('callback', '%r' % rec)
        self.assertIn('0, 1, 2', '%r' % rec)

# Signal Descriptor test

class SimpleSignaler(object):
    simple = SignalingProperty('simple')

    def __init__(self):
        self.emitted = []

    def emit(self, signal, *values, **kw):
        self.emitted.append((signal, values, kw))

class DummySignaler(SimpleSignaler):

    simple_with_default = SignalingProperty('simple2', default=0)

    double_a = SignalingProperty('same-signal')
    double_b = SignalingProperty('same-signal')

    double_c = SignalingProperty('dif-var', var_name='_a')
    double_d = SignalingProperty('dif-var', var_name='_b')

    changer = ChangedSignalingProperty('state')
    changer_with_default = ChangedSignalingProperty('state2', default='off')

    def __init__(self):
        self.emitted = []
        self._x = 0
        self.x_get = 0
        self.x_set = 0

    def xget(self):
        self.x_get += 1
        return self._x

    def xset(self, value):
        self.x_set += 1
        self._x = value

    def xsq(self, value):
        self.x_set += 1
        self._x = value * value

    x = CustomSignalingProperty('x-changed', xget, xset)
    x_square = CustomSignalingProperty('x-square', xget, xsq)

class TestSignalingDescriptors(unittest.TestCase):

    def setUp(self):
        self.signaler = DummySignaler()

    def test_simple(self):
        self.signaler.simple = 'A'
        self._check(values=[('simple', ('A',), {})])

        # empty
        self.signaler.emitted = []
        self.signaler.simple = 'A'
        # stays empty
        self._check()

    def test_simple_with_default(self):
        self.signaler.simple_with_default = 'B'
        self._check(values=[('simple2', ('B',), {})])

        # empty
        self.signaler.emitted = []
        self.signaler.simple_with_default = 'B'
        # stays empty
        self._check()

    def test_changer(self):
        self.signaler.changer = 'Yes'
        self._check(values=[('state', ('Yes', None), {})])

        # empty
        self.signaler.emitted = []
        self.signaler.changer = 'Yes'
        # stays empty
        self._check()

    def test_changer_with_default(self):
        self.signaler.changer_with_default = 'another'
        self._check(values=[('state2', ('another', 'off'), {})])

        # empty
        self.signaler.emitted = []
        self.signaler.changer_with_default = 'another'
        # stays empty
        self._check()

    def test_double_same_var(self):
        self.signaler.double_a = 'A1'
        self.signaler.double_b = 'B2'
        self._check(values=[('same-signal', ('A1',), {}),
                ('same-signal', ('B2',), {})])

        # empty
        self.signaler.emitted = []
        # sending B2 over double a even thought it was changed by b
        self.signaler.double_a = 'B2'
        self.signaler.double_b = 'B2'
        # stays empty
        self._check()

        # but changing them different works
        self.signaler.double_a = 'B1'
        self.signaler.double_b = 'A2'
        self._check(values=[('same-signal', ('B1',), {}),
                ('same-signal', ('A2',), {})])

    def test_double_differnt_var(self):
        self.signaler.double_c = 'A1'
        self.signaler.double_d = 'B2'
        self._check(values=[('dif-var', ('A1',), {}),
                ('dif-var', ('B2',), {})])

        # empty
        self.signaler.emitted = []
        self.signaler.double_c = 'A1'
        self.signaler.double_d = 'B2'
        # stays empty
        self._check()

        # but they still allow changes
        self.signaler.double_c = 'B1'
        self.signaler.double_d = 'A2'
        self._check(values=[('dif-var', ('B1',), {}),
                ('dif-var', ('A2',), {})])

    def test_custom(self):
        self.signaler.x = 'Pocahontas'
        self._check(values=[('x-changed', ('Pocahontas',), {})],
            x='Pocahontas', x_get=2, x_set=1)
        self.assertEquals(self.signaler.x, 'Pocahontas')

        # settings again to the same value is boring me
        self.signaler.emitted = []
        self.signaler.x_get = 0
        self.signaler.x_set = 0

        self.signaler.x = 'Pocahontas'
        self.assertEquals(self.signaler.emitted, [])
        self.assertEquals(self.signaler.x, 'Pocahontas')

    def test_custom_square(self):
        self.signaler.x_square = 10
        self._check(values=[('x-square', (100,), {})],
            x=100, x_get=2, x_set=1)
        self.assertEquals(self.signaler.x, 100)

    def test_custom_square_nearly_the_same(self):
        self.signaler._x = 10
        self.signaler.x_square = 10
        self._check(values=[('x-square', (100,), {})],
            x=100, x_get=2, x_set=1)
        self.assertEquals(self.signaler.x, 100)

    def _check(self, values=[], x=0, x_set=0, x_get=0):
        self.assertEquals(self.signaler._x, x)
        self.assertEquals(self.signaler.x_set, x_set)
        self.assertEquals(self.signaler.x_get, x_get)
        self.assertEquals(self.signaler.emitted, values)

class TestStayInObjectSignaling(unittest.TestCase):

    def setUp(self):
        self.foo = SimpleSignaler()
        self.bar = SimpleSignaler()

    def test_double_different_values(self):
        self.foo.simple = 'A'
        self.bar.simple = 'B'
        self.assertEquals(self.foo.simple, 'A')
        self.assertEquals(self.bar.simple, 'B')
        self.assertEquals(len(self.foo.emitted), 1)
        self.assertEquals(len(self.bar.emitted), 1)

        self.assertEquals(self.foo.emitted[0][1][0], 'A')
        self.assertEquals(self.bar.emitted[0][1][0], 'B')
