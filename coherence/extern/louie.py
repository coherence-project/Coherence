"""
Wrapper module for the louie implementation
"""

import warnings
from coherence.dispatcher import Dispatcher

class Any(object): pass
class All(object): pass
class Anonymous(object): pass

# fake the API 
class Dummy(object): pass
signal = Dummy()
sender = Dummy()

#senders
sender.Anonymous = Anonymous
sender.Any = Any

#signals
signal.All = All

# a slightly less raise-y-ish implementation as louie was not so picky, too
class GlobalDispatcher(Dispatcher):

    def connect(self, signal, callback, *args, **kw):
        if not signal in self.receivers:
            # ugly hack
            self.receivers[signal] = []
        return Dispatcher.connect(self, signal, callback, *args, **kw)

    def _get_receivers(self, signal):
        try:
            return self.receivers[signal]
        except KeyError:
            return []

_global_dispatcher = GlobalDispatcher()
_global_receivers_pool = {}

def connect(receiver, signal=All, sender=Any, weak=True):
    callback = receiver
    if signal in (Any, All):
        raise NotImplemented("This is not allowed. Signal HAS to be something")
    if sender not in (Any, All):
        warnings.warn("Seriously! Use the coherence.dispatcher. It IS object based")
    receiver = _global_dispatcher.connect(signal, callback)
    _global_receivers_pool[(callback, signal)] = receiver
    return receiver

def disconnect(receiver, signal=All, sender=Any, weak=True):
    callback = receiver
    if signal in (Any, All):
        raise NotImplemented("This is not allowed. Signal HAS to be something")
    if sender not in (Any, All):
        warnings.warn("Seriously! Use the coherence.dispatcher. It IS object based")
    receiver = _global_receivers_pool.pop((callback, signal))
    return _global_dispatcher.disconnect(receiver)

def send(signal=All, sender=Anonymous, *arguments, **named):
    if signal in (Any, All):
        raise NotImplemented("This is not allowed. Signal HAS to be something")
    if sender not in (Anonymous, None):
        warnings.warn("Seriously! Use the coherence.dispatcher. It IS object based")
    # the first value of the callback shall always be the signal:
    results, errors = _global_dispatcher.emit(signal, *arguments, **named)
    if errors:
        warnings.warn('Erros while processing %s: %r' % (signal, errors))

def send_minimal(signal=All, sender=Anonymous, *arguments, **named):
    return send(signal, sender, *arguments, **named)

def send_exact(signal=All, sender=Anonymous, *arguments, **named):
    return send(signal, sender, *arguments, **named)

def send_robust(signal=All, sender=Anonymous, *arguments, **named):
    return send(signal, sender, *arguments, **named)


