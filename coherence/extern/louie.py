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

global _global_dispatcher
_global_dispatcher = GlobalDispatcher()
_global_receivers_pool = {}

def _display_deprecation_warning():
    warnings.warn("extern.louie will soon be deprecated in favor of coherence.dispatcher.")

def connect(receiver, signal=All, sender=Any, weak=True):
    callback = receiver
    if signal in (Any, All):
        raise NotImplemented("This is not allowed. Signal HAS to be something")
    if sender not in (Any, All):
        _display_deprecation_warning()
    receiver = _global_dispatcher.connect(signal, callback)
    _global_receivers_pool[(callback, signal)] = receiver
    return receiver

def disconnect(receiver, signal=All, sender=Any, weak=True):
    callback = receiver
    if signal in (Any, All):
        raise NotImplemented("This is not allowed. Signal HAS to be something")
    if sender not in (Any, All):
        _display_deprecation_warning()
    receiver = _global_receivers_pool.pop((callback, signal))
    return _global_dispatcher.disconnect(receiver)

def send(signal=All, sender=Anonymous, *arguments, **named):
    if signal in (Any, All):
        raise NotImplemented("This is not allowed. Signal HAS to be something")
    if sender not in (Anonymous, None):
        _display_deprecation_warning()
    # the first value of the callback shall always be the signal:
    return _global_dispatcher.save_emit(signal, *arguments, **named)

def send_minimal(signal=All, sender=Anonymous, *arguments, **named):
    return send(signal, sender, *arguments, **named)

def send_exact(signal=All, sender=Anonymous, *arguments, **named):
    return send(signal, sender, *arguments, **named)

def send_robust(signal=All, sender=Anonymous, *arguments, **named):
    return send(signal, sender, *arguments, **named)


