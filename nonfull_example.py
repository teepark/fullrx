#!/usr/bin/env python3
"""Investigate whether we can only partially use rx in a WSGI app."""

import os
from random import randint
import sys
from typing import Any, Callable, Dict, Iterable, List, Mapping, Tuple

from gevent.event import Event
from gevent.pywsgi import WSGIServer
from rx import Observable
from rx.concurrency import GEventScheduler

number_fountain: Observable = (Observable.generate(randint(0, 100),
                                                   lambda _: True,
                                                   lambda _: randint(0, 100),
                                                   lambda x: x,
                                                   GEventScheduler())
                               .publish())
number_fountain.connect()


def wsgi_app(environ: Dict[str, Any],
             start_response: Callable[[str, List[Tuple[str, str]]], None],
             ) -> Iterable[bytes]:
    """WSGI app making use of an rx data source."""
    square = None
    ev = Event()

    def _sub(n):
        nonlocal square
        square = n
        ev.set()

    sub = (number_fountain
           .map(lambda x: x ** 2)
           .first()
           .subscribe(_sub))

    ev.wait()
    sub.dispose()

    start_response('200 OK', [])
    return ['{}'.format(square).encode('utf-8')]


def main(environ: Mapping[str, str], argv: List[str]) -> int:
    """Run the server."""
    WSGIServer(('127.0.0.1', 8000), wsgi_app).serve_forever()
    return 100


if __name__ == "__main__":
    sys.exit(main(os.environ, sys.argv))
