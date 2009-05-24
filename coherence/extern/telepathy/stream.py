import socket
import gobject


class TrivialStream:
    def __init__(self, socket_address=None):
        self.socket_address = socket_address

    def read_socket(self, s):
        try:
            data = s.recv(1024)
            if len(data) > 0:
                print "received:", data
        except socket.error, e:
            pass
        return True

    def write_socket(self, s, msg):
        print "send:", msg
        try:
            s = s.send(msg)
        except socket.error, e:
            pass
        return True

class TrivialStreamServer(TrivialStream):
    def __init__(self):
        TrivialStream.__init__(self)
        self._socket = None

    def run(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setblocking(1)
        self._socket.settimeout(0.1)
        self._socket.bind(("127.0.0.1", 0))

        self.socket_address = self._socket.getsockname()
        print "Trivial Server launched on socket", self.socket_address
        self._socket.listen(1)

        gobject.timeout_add(1000, self.accept_client, self._socket)

    def accept_client(self, s):
        try:
            s2, addr = s.accept()
            s2.setblocking(1)
            s2.setblocking(0.1)
            self.handle_client(s2)
            return True
        except socket.timeout:
            return True

    def handle_client(self, s):
        pass

class TrivialStreamClient(TrivialStream):

    def connect(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect(self.socket_address)
        print "Trivial client connected to", self.socket_address
