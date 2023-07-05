from pymavlink.dialects.v10.common import MAVLink, MAVLink_message, MAVError
from pymavlink.dialects.v10 import common
from pymavlink import mavutil
from serial import Serial
from serial.serialutil import SerialException
import sys
from typing import Callable, List
from threading import Event, Thread
from io import StringIO
from queue import Queue, Empty
import time
from enum import IntEnum


__all__ = ['ASAC']


REBOOT_AUTOPILOT = 1


class ASAC_State(IntEnum):
    NOT_CONNECTED = 0
    SERIAL_CONNECTED_WAITING_FOR_HEARTBEAT = 1
    CONNECTED = 2

class ASAC:

    MAVLINK_SYSTEM_ID = 0

    def __init__(self,
                 port: str = None,
                 on_connect: callable = None,
                 on_disconnect: callable = None) -> None:
        self.port = port
        if on_connect is None:
            on_connect = lambda: print('Connected')
        if on_disconnect is None:
            on_disconnect = lambda: print('Disonnected')
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

        self._stop_flag = Event()
        self._stop_flag.set()
        self._serial = Serial(baudrate=115200, timeout=0.5, write_timeout=5)
        self._fake_file = self._serial#StringIO()
        self._mav = MAVLink(self._fake_file)
        self._rx = Queue()
        self._msg_handlers = {}
        self._param_receive_timeout_ms = 1000
        self._first_tx_since_connected = True
        self._state = ASAC_State.NOT_CONNECTED

        self._REBOOT_RECONNECT_TIMEOUT_S = 3

        self._serial_write = self._serial.write

        def write_wrapper(*args, **kwargs):
            if self._first_tx_since_connected:
                self._serial.flush()
                self._first_tx_since_connected = True
            self._serial_write(*args, **kwargs)

        self._serial.write = write_wrapper

        # Add some default message handlers

    def reboot(self) -> None:
        self._mav.command_int_send(self.MAVLINK_SYSTEM_ID,
                                   common.MAV_COMP_ID_ALL,
                                   0,
                                   common.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
                                   0,
                                   0,
                                   REBOOT_AUTOPILOT,
                                   0,
                                   0,
                                   0,
                                   0,
                                   0,
                                   0,
                                   True)
        self._serial.flushOutput()

        # Once we reboot, we start a timer, waiting for the system reboots
        # so that we can try to re-connect instantly after.
        Thread(target=self._wait_for_reboot, daemon=True).start()

    def _wait_for_reboot(self) -> None:
        # Need to wait some time before closing serial port, to ensure that
        # reboot packed was successfully sent. Not a fan of hardcoding the
        # timeout value, but works for now.
        time.sleep(.1)
        self.stop()

        t0 = time.time()
        reconnected = False
        while (not reconnected and \
               (time.time() - t0) < self._REBOOT_RECONNECT_TIMEOUT_S):
            try:
                reconnected = self.start()
            except SerialException:
                pass
            time.sleep(.1)

    def add_message_handler(self, msg_id: int, callback: callable) -> None:
        if msg_id not in self._msg_handlers:
            self._msg_handlers[msg_id] = []

        self._msg_handlers[msg_id].append(callback)

    def del_message_handler(self, msg_id: int, callback: callable) -> None:
        handlers = self._msg_handlers.get(msg_id, [])
        handlers.remove(callback)

    def write_params_to_flash(self) -> None:
        PARAM_WRITE_PERSISTENT = 1
        self._mav.command_int_send(self.MAVLINK_SYSTEM_ID,
                            common.MAV_COMP_ID_ALL,
                            0,
                            common.MAV_CMD_PREFLIGHT_STORAGE,
                            0,
                            0,
                            PARAM_WRITE_PERSISTENT,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            True)

    def set_parameter(self, name: str, value: float, type: int,
                      on_ack: Callable[[common.MAVLink_message], None] = None) -> None:
        def cb(msg):
            # Remove temporary message handler
            self.del_message_handler(common.MAVLINK_MSG_ID_PARAM_VALUE, cb)
            if on_ack is not None:
                on_ack(msg)

        self.add_message_handler(common.MAVLINK_MSG_ID_PARAM_VALUE, cb)
        self._mav.param_set_send(self.MAVLINK_SYSTEM_ID,
                                 common.MAV_COMP_ID_ALL,
                                 name,
                                 value,
                                 type,
                                 True)

    def get_parameters(self, on_complete: Callable[..., dict] = None,
                       max_attempts: int = 5,
                       delay_between_attempts_ms: int = 500) -> None:
        # TODO: Cleanup and use threading for waiting so we don't block
        # calling thread
        attempt = 1
        params = []
        while attempt < max_attempts and not params:
            self._mav.param_request_list_send(self.MAVLINK_SYSTEM_ID,
                                          common.MAV_COMP_ID_ALL,
                                          True)
            params = self._wait_for_parameters()
            time.sleep(delay_between_attempts_ms / 1000)
            attempt += 1

        if params:
            params = {p.param_id: p for p in params}

        if on_complete is not None:
            on_complete(params)

        return params
        Thread(target=self._wait_for_parameters, daemon=True).start()

    def _wait_for_parameters(self) -> None:
        timeout_s = self._param_receive_timeout_ms / 1000
        params = []

        def param_callback(msg: common.MAVLink_message) -> None:
            params.append(msg)

        self.add_message_handler(common.MAVLINK_MSG_ID_PARAM_VALUE,
                                 param_callback)
        time.sleep(timeout_s)
        self.del_message_handler(common.MAVLINK_MSG_ID_PARAM_VALUE,
                                 param_callback)


        print(f'{len(params)} Params received: ')
        for param in params:
            print(f'    - {param.param_id}: {param.param_value}')

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

        self._serial.flush()

        return True

    def is_connected(self) -> None:
        return self._serial.is_open

    def stop(self) -> None:
        if self._stop_flag.is_set():
            return False

        self._stop_flag.set()
        self._serial.close()

        if self.on_disconnect is not None:
            self.on_disconnect()

        return True

    def _msg_handler_thread(self) -> None:
        while not self._stop_flag.is_set():
            try:
                msg: MAVLink_message = self._rx.get(timeout=1)
                print(msg)
                handlers = self._msg_handlers.get(msg.id)

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
            except SerialException:
                # Device probably disconnected itself
                print('Device disconnected or multiple access on port?')
                self.stop()
            except TypeError as e:
                print('TYPEERRR', e)
                # This occurs of we're disconnected
                pass
        print('RX Thread ended')


if __name__ == '__main__':
    PORT = sys.argv[1]
    asac = ASAC(PORT)
    asac.start()
