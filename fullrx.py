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

import gevent
from gevent.event import Event
from gevent.queue import Queue
from pyrsistent import PRecord, field
from rx import Observable
from rx.subjects import Subject

# start_response callable type
_SR = Callable[[str, Tuple[str, str]], Callable[[str], None]]


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
    body: str


class RxToWsgi:
    """
    Valid WSGI app class that sends requests though rx observables.

    Create it with a function that maps an Observable of Requests to an
    Observable of (Request, Response) tuples.
    """

    def __init__(self, rx_app: Callable[[Observable], Observable]) -> None:
        """Initialize the RxToWsgi object."""
        self._request_queue = Queue()
        self._request_observable = _observe_queue(self._request_queue)
        self._responses_ready: Dict[Request, Event] = {}
        self._responses: Dict[Request, Response] = {}
        self._response_observable = rx_app(self._request_observable)
        self._response_observable.subscribe(self._coordinate_response,
                                            on_error=self._coordinate_error)

    def _coordinate_error(self, error: Exception) -> None:
        print("RxToWsgi got error {}".format(error))

    def _coordinate_response(self,
                             request_response: Tuple[Request, Response],
                             ) -> None:
        request, response = request_response
        self._responses[request] = response
        self._responses_ready.pop(request).set()

    def __call__(self,
                 environ: Dict[str, Any],
                 start_response: _SR,
                 ) -> Iterable[str]:
        """Implement the WSGI application."""
        request = Request(environ=environ)
        ready = Event()
        self._responses_ready[request] = ready
        self._request_queue.put(request)

        ready.wait()

        response = self._responses.pop(request)
        start_response(_status_string(response.status), response.headers)
        return [response.body]


def _observe_queue(queue: Queue) -> Observable:
    subject = Subject()
    gevent.spawn(_link_observable_to_queue, subject, queue)
    return subject


def _link_observable_to_queue(subject: Subject, queue: Queue) -> None:
    while 1:
        subject.on_next(queue.get())


def _status_string(status_number: int) -> str:
    strs = BaseHTTPRequestHandler.responses[http.HTTPStatus(status_number)]
    return '{} {}'.format(status_number, strs[0])
