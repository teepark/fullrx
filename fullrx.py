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
    Type,
    TypeVar,
)

from pyrsistent import PRecord, field, pvector_field
from rx import Observable
from rx.subjects import Subject

_StartResponse = Callable[[str, List[Tuple[str, str]]], None]
_R = TypeVar('_R', bound=PRecord)


class Request(PRecord):
    """Immutable representation of an HTTP request."""

    protocol: str = field(type=str, mandatory=True)
    method: str = field(type=str, mandatory=True)
    path: str = field(type=str, mandatory=True)
    query_string: str = field(type=str, mandatory=True)
    client_ip: str = field(type=str, mandatory=True)
    client_port: int = field(type=int, mandatory=True)
    headers: Iterable[Tuple[str, str]] = pvector_field(tuple)
    body: Any = field(mandatory=True)

    @classmethod
    def from_environ(cls: Type[_R], environ: Dict[str, Any]) -> _R:
        """Build a Request object out of a WSGI environ dict."""
        return cls(
            protocol=environ['SERVER_PROTOCOL'],
            method=environ['REQUEST_METHOD'],
            path=environ['PATH_INFO'],
            query_string=environ['QUERY_STRING'],
            client_ip=environ['REMOTE_ADDR'],
            client_port=int(environ['REMOTE_PORT']),
            headers=[(k[5:].replace('_', '-').title(), v)
                     for k, v in environ.items()
                     if k.startswith("HTTP_")],
            body=environ['wsgi.input'],
        )


class Response:
    """Class representing HTTP responses."""

    def __init__(self,
                 request: Request,
                 status: int = None,
                 headers: List[Tuple[str, str]] = None,
                 body: Observable = None,
                 ) -> None:
        """Initialize a Response object."""
        self.request = request
        self.status = status
        self.headers = headers
        self.body = body

    def _start(self, start_response: _StartResponse) -> None:
        s = BaseHTTPRequestHandler.responses[http.HTTPStatus(self.status)][0]
        start_response(f'{self.status} {s}', self.headers)

    def _body(self) -> Iterable[bytes]:
        return self.body.to_blocking().to_iterable()


class RxToWsgi:
    """RxToWSGI."""

    def __init__(self,
                 rx_app: Callable[[Request], Observable],
                 ) -> None:
        """Initialize."""
        self.rx_app = rx_app

    def __call__(self,
                 environ: Dict[str, Any],
                 start_response: _StartResponse,
                 ) -> Iterable[bytes]:
        """Run the WSGI app."""
        response = next(self.rx_app(Request.from_environ(environ))
                        .to_blocking()
                        .to_iterable())

        response._start(start_response)
        return response._body()


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
                 start_response: _StartResponse,
                 ) -> Iterable[bytes]:
        """Run the WSGI app."""
        request = Request.from_environ(environ)

        responses = (self._response_stream
                     .filter(lambda response: response.request is request)
                     .first()
                     .to_blocking()
                     .to_iterable())

        self._request_stream.on_next(request)
        response = next(responses)

        response._start(start_response)
        return response._body()
