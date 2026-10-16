"""Minimal Prometheus text-format metrics (no external dependency)."""
import threading

_l = threading.Lock()
_counters, _gauges, _hist = {}, {}, {}
BUCKETS = [.01, .05, .1, .25, .5, 1, 2.5, 5, 10, 30, 60]


def _k(name, labels):
    return (name, tuple(sorted(labels.items())))


def inc(name, **labels):
    with _l:
        k = _k(name, labels)
        _counters[k] = _counters.get(k, 0) + 1


def add(name, value, **labels):
    with _l:
        k = _k(name, labels)
        _counters[k] = _counters.get(k, 0) + value


def gauge(name, value, **labels):
    with _l:
        _gauges[_k(name, labels)] = value


def observe(name, value, **labels):
    with _l:
        h = _hist.setdefault(_k(name, labels), [[0] * len(BUCKETS), 0, 0.0])
        for i, b in enumerate(BUCKETS):
            if value <= b:
                h[0][i] += 1
        h[1] += 1
        h[2] += value


def _fmt(labels, extra=None):
    items = list(labels) + (list(extra.items()) if extra else [])
    return '{' + ','.join(f'{k}="{v}"' for k, v in items) + '}' if items else ''


def render():
    out = []
    with _l:
        for (n, lb), v in _counters.items():
            out.append(f'{n}_total{_fmt(lb)} {v}')
        for (n, lb), v in _gauges.items():
            out.append(f'{n}{_fmt(lb)} {v}')
        for (n, lb), (bk, cnt, s) in _hist.items():
            for b, c in zip(BUCKETS, bk):
                out.append(f'{n}_bucket{_fmt(lb, {"le": b})} {c}')
            out.append(f'{n}_bucket{_fmt(lb, {"le": "+Inf"})} {cnt}')
            out.append(f'{n}_sum{_fmt(lb)} {s}')
            out.append(f'{n}_count{_fmt(lb)} {cnt}')
    return '\n'.join(out) + '\n'
