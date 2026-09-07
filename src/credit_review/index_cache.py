"""Small process cache survives UI module reloads; keys contain exact indexed text."""
from collections import OrderedDict
from threading import Lock

_lock = Lock()
_values = OrderedDict()


def cached_index(key, build):
    with _lock:
        if key not in _values:
            _values[key] = build()
        _values.move_to_end(key)
        while len(_values) > 4:
            _values.popitem(last=False)
        return _values[key]
