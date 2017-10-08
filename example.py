#!/usr/bin/env python3
"""Simple app that displays the environ dict in response body."""

import os
import sys
from typing import List, Mapping

from gevent import pywsgi
from fullrx import Response, RxToWsgi
from rx import Observable


def _app(request: Observable) -> Response:
    response = Response()
    response.status = 200
    response.body = b'\n'.join('{} {!r}'.format(*pair).encode('utf8')
                               for pair in request.environ.items())
    response.headers = [('Content-Type', 'text/plain'),
                        ('Content-Encoding', 'utf-8'),
                        ('Content-Length', str(len(response.body)))]
    return response


def rx_app(requests:  Observable) -> Observable:
    """Set up the app in rx form."""
    requests.subscribe(on_error=_on_error)
    return requests.map(lambda req: (req, _app(req)))


def _on_error(error: Exception) -> None:
    print("App got error {}".format(error))


def main(environ: Mapping[str, str], argv: List[str]) -> int:
    """Run the app."""
    wsgi_app = RxToWsgi(rx_app)

    server = pywsgi.WSGIServer(("127.0.0.1", 8000), wsgi_app)
    server.serve_forever()

    return 100


if __name__ == "__main__":
    sys.exit(main(os.environ, sys.argv))
