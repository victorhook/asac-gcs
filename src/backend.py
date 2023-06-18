from serial import Serial
from threading import Thread, Event
from queue import Queue
from abc import abstractmethod


class Transport:

    def __init__(self) -> None:
        self.timeout_ms: int = 1000
        self._is_connected: bool = False

    def connect(self) -> bool:
        if self._is_connected:
            return False

        if self.do_connect():
            self._is_connected = True

        self.do_set_timeout(self.timeout_ms)

        return self.is_connected()

    def disconnect(self) -> None:
        if not self._is_connected:
            return

        self.do_disconnect()
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._is_connected

    def read(self, nbr_of_bytes: int) -> bytes:
        if not self.is_connected():
            return

        return self.do_read(nbr_of_bytes)

    def write(self, data: bytes) -> int:
        if not self.is_connected():
            return

        return self.do_write(data)

    def set_timeout(self, timeout_ms: int) -> None:
        self.timeout_ms = timeout_ms
        self.do_set_timeout(timeout_ms)

    @abstractmethod
    def do_set_timeout(self, timeout_ms: int) -> None:
        pass

    @abstractmethod
    def do_connect(self) -> bool:
        pass

    @abstractmethod
    def do_disconnect(self) -> None:
        pass

    @abstractmethod
    def do_read(self, nbr_of_bytes: int) -> bytes:
        pass

    @abstractmethod
    def do_write(self, data: bytes) -> int:
        pass


class TransportSerial(Transport):

    def __init__(self, port) -> None:
        super().__init__()
        self._serial = Serial(baudrate=115200)
        self._serial.port = port

    @abstractmethod
    def do_set_timeout(self, timeout_ms: int) -> None:
        self._serial.timeout = timeout_ms / 1000
        self._serial.write_timeout = timeout_ms / 1000

    @abstractmethod
    def do_connect(self) -> bool:
        self._serial.open()

    @abstractmethod
    def do_disconnect(self) -> None:
        self._serial.close()

    @abstractmethod
    def do_read(self, nbr_of_bytes: int) -> bytes:
        return self._serial.read(nbr_of_bytes)

    @abstractmethod
    def do_write(self, data: bytes) -> int:
        return self._serial.write(data)


class Backend:

    def __init__(self) -> None:
        self._rx = Queue()
        self._tx = Queue()
        self._transport: Transport = None
        self._stop_flag = Event()

    def start(self, transport: Transport) -> None:
        self._stop_flag.clear()
        self._transport = transport
        Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        self._transport.connect()
        self._transport.set_timeout(.1)

        while not self._stop_flag.is_set():
            # Read RX
            try:
                one_byte = self._transport.read(1)
                if one_byte:
                    self._rx.put(one_byte)
            except TimeoutError:
                pass

            # Write any data in TX buffer
            while not self._tx.empty():
                self._transport.write(self._tx.get())

    def is_connected(self) -> bool:
        return self._transport.is_connected()
