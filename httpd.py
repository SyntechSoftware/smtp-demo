import asyncore
import logging
import socket
from io import BytesIO
from http.server import BaseHTTPRequestHandler
from http import HTTPStatus
import urllib.parse as urlparse
from urllib.parse import parse_qs


logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
log = logging.getLogger(__name__)


class HttpServer(asyncore.dispatcher):
    """Receives connections and establishes handlers for each client.
    """

    def __init__(self, address, handler):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind(address)
        self.handler = handler
        self.address = self.socket.getsockname()
        log.debug('binding to %s', self.address)
        self.listen(5)
        return

    def handle_accept(self):
        # Called when a client connects to our socket
        client_info = self.accept()
        log.debug('handle_accept() -> %s', client_info[1])
        ProcessHandler(sock=client_info[0], address=client_info[1], handler=self.handler)
        return

    def handle_close(self):
        log.debug('handle_close()')
        self.close()
        return


class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text, client_address):
        self.rfile = BytesIO(request_text)
        self.wfile = BytesIO()
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.client_address = client_address
        self.parse_request()
        mname = 'do_' + self.command
        if not hasattr(self, mname):
            self.send_error(
                HTTPStatus.NOT_IMPLEMENTED,
                "Unsupported method (%r)" % self.command)
            return
        method = getattr(self, mname)
        parsed = urlparse.urlparse(self.path)
        self.path = parsed.path
        self.query_string = parse_qs(parsed.query)
        try:
            method()
        except Exception as e:
            self.send_error(500, "Internal server error")
            log.error(e)
        self.end_headers()
        self.wfile.flush()  # actually send the response if not already done.

    def send_error(self, code, message=None, expliane=None):
        self.send_response(code, message)
        self.wfile.flush()


class ProcessHandler(asyncore.dispatcher):
    """Handles echoing messages from a single client.
    """

    def __init__(self, sock, handler=None, address=None, chunk_size=9182):
        self.chunk_size = chunk_size
        self.handler = handler
        asyncore.dispatcher.__init__(self, sock=sock)
        self.client_address = address
        self.data_to_write = []
        return

    def writable(self):
        """We want to write if we have received data."""
        response = bool(self.data_to_write)
        log.debug('writable() -> %s', response)
        return response

    def handle_write(self):
        """Write as much as possible of the most recent message we have received."""
        data = self.data_to_write.pop()
        sent = self.send(data[:self.chunk_size])
        if sent < len(data):
            remaining = data[sent:]
            self.data_to_write.append(remaining)
        log.debug('handle_write() -> (%d) "%s"', sent, data[:sent])
        if not self.writable():
            self.handle_close()

    def handle_read(self):
        """Read an incoming message from the client and put it into our outgoing queue."""
        data = self.recv(self.chunk_size)
        log.debug('handle_read() -> (%d) "%s"', len(data), data)
        if self.handler and data:
            request = self.handler(data, self.client_address)
            self.data_to_write.insert(0, request.wfile.getvalue())
        else:
            self.data_to_write.insert(0, '')

    def handle_close(self):
        log.debug('handle_close()')
        self.close()
