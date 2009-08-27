
from twisted.internet import defer

class Receiver(object):
    def __init__(self, signal, callback, args, kwargs):
        self.signal = signal
        self.callback = callback
        self.arguments = args
        self.keywords = kwargs

    def __call__(self, *args, **kwargs):
        args = args + self.arguments

        kw = self.keywords.copy()
        if kwargs:
            kw.update(kwargs)
        return self.callback(*args, **kw)

    def __repr__(self):
        return "<Receiver %s for %s: %s (%s, %s)>" % (id(self),
                self.signal,
                self.callback,
                ', '.join(
                        ['%r' % x for x in self.arguments]
                        ),
                ', '.join(
                        ['%s=%s' % (x, y) for x, y in self.keywords.iteritems()]
                        )
                )

class UnknownSignal(Exception): pass

class Dispatcher(object):

    __signals__ = {}

    def __init__(self):
        self.receivers = {}
        for signal in self.__signals__.iterkeys():
            self.receivers[signal] = []

    def connect(self, signal, callback, *args, **kw):
        receiver = Receiver(signal, callback, args, kw)
        try:
            self.receivers[signal].append(receiver)
        except KeyError:
            raise UnknownSignal(signal)
        return receiver

    def disconnect(self, receiver):
        if not receiver:
            return

        try:
            self.receivers[receiver.signal].remove(receiver)
        except KeyError:
            raise UnknownSignal(receiver.signal)
        except AttributeError:
            raise TypeError("'%r' is not a Receiver-like object" % receiver)
        except ValueError:
            # receiver not in the list, goal achieved
            pass

    def emit(self, signal, *args, **kwargs):
        results = []
        errors = []
        for receiver in self._get_receivers(signal):
            try:
                results.append((receiver, receiver(*args, **kwargs)))
            except Exception, e:
                errors.append((receiver, e))

        return results, errors

    def deferred_emit(self, signal, *args, **kwargs):
        receivers = []
        dfrs = []
        # TODO: the loop is blocking, use callLaters and/or coiterate here
        for receiver in self._get_receivers(signal):
            receivers.append(receiver)
            dfrs.append(defer.maybeDeferred(receiver, *args, **kwargs))

        if not dfrs:
            return defer.succeed([])

        result_dfr = defer.DeferredList(dfrs)
        result_dfr.addCallback(self._merge_results_and_receivers, receivers)
        return result_dfr

    def save_emit(self, signal, *args, **kwargs):
        deferred = defer.Deferred()
        # run the deferred_emit in as a callback
        deferred.addCallback(self.deferred_emit, *args, **kwargs)
        # and callback the deferred with the signal as the 'result' in the
        # next mainloop iteration
        from twisted.internet import reactor
        reactor.callLater(0, deferred.callback, signal)
        return deferred

    def _merge_results_and_receivers(self, result, receivers):
        # make a list of (rec1, res1), (rec2, res2), (rec3, res3) ...
        return [(receiver, result[counter])
                for counter, receiver in enumerate(receivers)]

    def _get_receivers(self, signal):
        try:
            return self.receivers[signal]
        except KeyError:
            raise UnknownSignal(signal)


class SignalingProperty(object):
    """
    Does emit self.signal when the value has changed but only if HAS changed
    (means old_value != new_value).
    """

    def __init__(self, signal, var_name=None, default=None):
        self.signal = signal

        if var_name is None:
            var_name = "__%s__val" % signal

        self.var_name = var_name

        self.default = default

    def __get__(self, obj, objtype=None):
        return getattr(obj, self.var_name, self.default)

    def __set__(self, obj, value):
        if self.__get__(obj) == value:
            return
        setattr(obj, self.var_name, value)
        obj.emit(self.signal, value)

class ChangedSignalingProperty(SignalingProperty):
    """
    Does send the signal with two values when changed:
        1. the new value
        2. the value it has been before
    """
    def __set__(self, obj, value):
        before = self.__get__(obj)
        if before == value:
            return
        setattr(obj, self.var_name, value)
        obj.emit(self.signal, value, before)

class CustomSignalingProperty(object):
    """
    Signal changes to this property. allows to specify fget and fset as the
    build in property-decorator.
    """

    def __init__(self, signal, fget, fset, fdel=None, doc=None):
        """
        fdel is there for API compability only. As there is no good way to
        signal a deletion it is not implemented at all.
        """
        self.signal = signal
        self.fget = fget
        self.fset = fset
        self.__doc__ = doc

    def __get__(self, obj, objtype):
        return self.fget(obj)

    def __set__(self, obj, value):
        """
        Call fset with value. Call fget before and after to figure out if
        something actually changed. Only if something changed the signal is
        emitted.

        The signal will be emitted with the new value given by fget.

        *Note*: This means that fset might gets called with the same value twice
        while the signal is not emitted a second time. You might want to check
        for that in your fset.
        """

        old_value = self.fget(obj)
        self.fset(obj, value)
        new_value = self.fget(obj)

        if old_value == new_value:
            return

        obj.emit(self.signal, new_value)
