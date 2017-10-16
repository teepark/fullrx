#!/usr/bin/env python3
"""Simple app that displays the environ dict in response body."""

import os
import sys
from typing import List, Mapping

from gevent import pywsgi
from rx import Observable

from fullrx import FullRx, Request, Response, RxToWsgi


def rx_app(request: Request) -> Observable:
    """App in singular Rx form."""
    return Observable.just(_pure_app(request))


def full_rx_app(requests: Observable) -> Observable:
    """App in streaming Rx form."""
    return requests.map(_pure_app)


def _pure_app(request: Request) -> Response:
    """Pure request -> response function."""
    body = b'\n'.join(f'{k}: {v}'.encode('utf-8') for k, v in request.headers)
    return Response(request,
                    200,
                    [('Content-Length', str(len(body))),
                     ('Content-Type', 'text/plain')],
                    Observable.just(body))


full_app = FullRx(full_rx_app)
app = RxToWsgi(rx_app)


def main(environ: Mapping[str, str], argv: List[str]) -> int:
    """Run the app server."""
    (pywsgi.WSGIServer(('127.0.0.1', 8001), full_app)
     .serve_forever())

    return 100


if __name__ == "__main__":
    sys.exit(main(os.environ, sys.argv))
