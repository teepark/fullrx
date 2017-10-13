"""rx to wsgi mapper to support full web apps as rx observable mappers."""

import http
from http.server import BaseHTTPRequestHandler
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Tuple,
)

from pyrsistent import PRecord, field
from rx import Observable
from rx.subjects import Subject

# start_response callable type
# (not really true but we're not using the write callable)
_SR = Callable[[str, List[Tuple[str, str]]], None]


class Request(PRecord):
    """Immutable representation of an HTTP request."""

    # TODO: pull the WSGI environ apart into meaningful fields
    environ: Dict[str, Any] = field(type=dict)

    def __hash__(self):
        """Hashing implementation to overcome the dict field."""
        return hash(tuple(self.environ.items()))


class Response:
    """Class representing HTTP responses."""

    status: int
    headers: List[Tuple[str, str]]
    body: Observable  # single response


class RxToWsgi:
    """RxToWSGI."""

    def __init__(self,
                 rx_app: Callable[[Request], Observable],
                 ) -> None:
        """Initialize."""
        self.rx_app = rx_app

    def __call__(self,
                 environ: Dict[str, Any],
                 start_response: _SR,
                 ) -> Iterable[bytes]:
        """Run the WSGI app."""
        response = next(self.rx_app(Request(environ=environ))
                        .to_blocking()
                        .to_iterable())

        start_response(_status_string(response.status), response.headers)
        return response.body.to_blocking().to_iterable()


class FullRx:
    """FullRx."""

    def __init__(self,
                 rx_app: Callable[[Observable], Observable],
                 ) -> None:
        """Initialize the WSGI app."""
        self.rx_app = rx_app

        self._request_stream = Subject()
        self._request_stream.publish()

        self._response_stream = self.rx_app(self._request_stream)
        self._response_stream.subscribe(on_error=print)
        self._response_stream.publish()

    def __call__(self,
                 environ: Dict[str, Any],
                 start_response: _SR,
                 ) -> Iterable[bytes]:
        """Run the WSGI app."""
        request = Request(environ=environ)

        responses = (self._response_stream
                     .filter(lambda pair: pair[0] is request)
                     .first()
                     .map(lambda pair: pair[1])
                     .to_blocking()
                     .to_iterable())

        self._request_stream.on_next(request)
        response = next(responses)

        start_response(_status_string(response.status), response.headers)
        return response.body.to_blocking().to_iterable()


def _status_string(status_number: int) -> str:
    strs = BaseHTTPRequestHandler.responses[http.HTTPStatus(status_number)]
    return '{} {}'.format(status_number, strs[0])
