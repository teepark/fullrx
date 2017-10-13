#!/usr/bin/env python3
"""Simple app that displays the environ dict in response body."""

import os
import sys
from typing import List, Mapping

from gevent import pywsgi
from rx import Observable

from fullrx import FullRx, Request, Response, RxToWsgi


def rx_app(request: Request) -> Observable:
    """App."""
    return Observable.just(_pure_app(request))


def full_rx_app(requests: Observable) -> Observable:
    """Full Rx app."""
    return requests.map(lambda req: (req, _pure_app(req)))


def _pure_app(request: Request) -> Response:
    response = Response()
    response.status = 200
    body = b'\n'.join(f'{k}: {v!r}'.encode('utf-8')
                      for k, v in request.environ.items())
    response.headers = [('Content-Length', str(len(body))),
                        ('Content-Type', 'text/plain')]
    response.body = Observable.just(body)
    return response


full_app = FullRx(full_rx_app)
app = RxToWsgi(rx_app)


def main(environ: Mapping[str, str], argv: List[str]) -> int:
    """Run the app server."""
    (pywsgi.WSGIServer(('127.0.0.1', 8001), full_app)
     .serve_forever())

    return 100


if __name__ == "__main__":
    sys.exit(main(os.environ, sys.argv))
