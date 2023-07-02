from pymavlink.dialects.v10.common import MAVLink, MAVLink_message, MAVError
from pymavlink.dialects.v10 import common
from pymavlink import mavutil
from serial import Serial
import sys
from typing import Callable, List
from threading import Event, Thread
from io import StringIO
from queue import Queue, Empty
import time


class ASAC:

    MAVLINK_SYSTEM_ID = 0

    def __init__(self,
                 port: str = None,
                 on_connect: callable = None,
                 on_disconnet: callable = None) -> None:
        self.port = port
        self.on_connect = on_connect
        self.on_disconnet = on_disconnet

        self._stop_flag = Event()
        self._stop_flag.set()
        self._serial = Serial(baudrate=115200, timeout=0.5, write_timeout=5)
        self._fake_file = self._serial#StringIO()
        self._mav = MAVLink(self._fake_file)
        self._rx = Queue()
        self._msg_handlers = {}
        self._param_receive_timeout_ms = 1000

        # Add some default message handlers


    def add_message_handler(self, msg_id: int, callback: callable) -> None:
        if msg_id not in self._msg_handlers:
            self._msg_handlers[msg_id] = []

        self._msg_handlers[msg_id].append(callback)

    def get_parameters(self, on_complete: Callable[..., dict]) -> None:
        self._mav.param_request_list_send(self.MAVLINK_SYSTEM_ID,
                                          common.MAV_COMP_ID_ALL,
                                          True)
        params = self._wait_for_parameters()
        params = {p.param_id: p for p in params}
        on_complete(params)
        return params
        #Thread(target=self._wait_for_parameters, daemon=True).start()

    def _wait_for_parameters(self) -> None:
        timeout_s = self._param_receive_timeout_ms / 1000
        params = []

        self.add_message_handler(common.MAVLINK_MSG_ID_PARAM_VALUE,
                                 lambda msg: params.append(msg))

        time.sleep(timeout_s)

        print('PARAMS RECEIVED: ', params)
        return params

    def start(self, port: str = None) -> bool:
        if not self._stop_flag.is_set():
            return False

        if port is not None:
            self.port = port

        self._serial.port = self.port
        self._serial.open()
        self._stop_flag.clear()
        Thread(target=self._receive_thread, daemon=True).start()
        Thread(target=self._msg_handler_thread, daemon=True).start()

        if self.on_connect is not None:
            self.on_connect()

        return True

    def is_connected(self) -> None:
        return self._serial.is_open

    def stop(self) -> None:
        if self._stop_flag.is_set():
            return False

        self._stop_flag.set()
        self._serial.close()

        if self.on_disconnet is not None:
            self.on_disconnet()

        return True

    def _msg_handler_thread(self) -> None:
        while not self._stop_flag.is_set():
            try:
                msg: MAVLink_message = self._rx.get(timeout=1)
                handlers = self._msg_handlers.get(msg.id)
                #print(msg)

                if not handlers:
                    #print(f'No handler found for message: {msg}')
                    pass
                else:
                    for handler in handlers:
                        handler(msg)
            except Empty:
                pass
            except TimeoutError:
                pass

    def _receive_thread(self) -> None:
        print('RX Thread started')
        while not self._stop_flag.is_set():
            try:
                byte = self._serial.read(1)
                if byte:
                    try:
                        res = self._mav.parse_char(byte)
                        if res:
                            self._rx.put(res)
                    except MAVError:
                        pass
            except TypeError as e:
                print('TYPEERRR', e)
                # This occurs of we're disconnected
                pass
        print('RX Thread ended')

if __name__ == '__main__':
    PORT = sys.argv[1]
    asac = ASAC(PORT)
    asac.start()

    #while 1:
    #    import time
    #    time.sleep(11)