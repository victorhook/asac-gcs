from pymavlink.dialects.v10.common import MAVLink, MAVLink_message, MAVError
from pymavlink.dialects.v10 import common
from pymavlink import mavutil
from serial import Serial
from serial.serialutil import SerialException
import sys
from typing import Callable, List, Dict, Tuple
from threading import Event, Thread
from io import StringIO
from queue import Queue, Empty
import time
from enum import IntEnum
import utils
from typing import Dict


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
        self.logger = utils.get_logger()

        if on_connect is None:
            on_connect = lambda: self.logger.info('Connected')
        if on_disconnect is None:
            on_disconnect = lambda: self.logger.info('Disonnected')
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

        self._stop_flag = Event()
        self._stop_flag.set()
        self._serial = Serial(baudrate=115200, timeout=0.5, write_timeout=5)
        self._fake_file = self._serial#StringIO()
        self._mav = MAVLink(self._fake_file)
        self._rx = Queue()
        self._msg_handlers: Dict[MAVLink_message, callable] = {}
        self._param_receive_timeout_ms = 2000
        self._first_tx_since_connected = True
        self._reboot_flag = Event()
        self._state = ASAC_State.NOT_CONNECTED

        self._REBOOT_RECONNECT_TIMEOUT_S = 3

        self._serial_write = self._serial.write

        def write_wrapper(*args, **kwargs):
            if self._first_tx_since_connected:
                self._serial.flush()
                self._first_tx_since_connected = True
            self._serial_write(*args, **kwargs)

        self._serial.write = write_wrapper

        self._param_values = Queue() # Queue[common.MAVLink_param_value_message]

        # Add some default message handlers
        self.add_message_handler(common.MAVLink_param_value_message,
                                 self._param_values.put)

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

        # Quick-fix for now, should not have these hard-coded sleeps in future...
        delay = 5
        self.logger.info(f'Sending reboot request, waiting for {delay} seconds...')
        time.sleep(delay)
        self.logger.info('Closing serial connection')
        self.stop()
        self.logger.info('Opening serial connection')
        time.sleep(1)
        self.start()

        # Once we reboot, we start a timer, waiting for the system reboots
        # so that we can try to re-connect instantly after.
        #self._reboot_flag.clear()
        #self._wait_for_reboot()
        #Thread(target=self._wait_for_reboot, daemon=True).start()

    def set_parameters(self, parameters: Dict[str, Tuple[float, int]],
                       on_complete: Callable) -> None:
        for param in parameters:
            param_value, param_type = parameters[param]
            self.set_parameter(param, param_value, param_type)

        self._serial.flushOutput()

        if on_complete:
            # TODO: Real implementation, now we'll just wait some time...
            # Assuming all Setters are OK
            time.sleep(1)
            on_complete()

    def wait_until_rebooted(self) -> bool:
        '''
        Freezes calling thread until ASAC is rebooted, or until a timeout
        occurs due to fail reconnection.
        Returns True if we are successfully reconnected and otherwise False.
        '''
        self._reboot_flag.wait()
        return self.is_connected()

    def _wait_for_reboot(self) -> None:
        # Need to wait some time before closing serial port, to ensure that
        # reboot packed was successfully sent. Not a fan of hardcoding the
        # timeout value, but works for now.
        time.sleep(.5)
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

        self._reboot_flag.set()

    def add_message_handler(self, msg_type: MAVLink_message, callback: callable) -> None:
        '''
        Need to specify mavlink message class instead of ID, since some mavlink
        messages has ID as attribute (eg MAVLink_battery_status_message),
        so if we identified the messages with ID this fails.
        '''
        if msg_type not in self._msg_handlers:
            self._msg_handlers[msg_type] = []

        self._msg_handlers[msg_type].append(callback)

    def del_message_handler(self, msg_id: int, callback: callable) -> None:
        handlers = self._msg_handlers.get(msg_id, [])
        handlers.remove(callback)

    def reset_parameters(self) -> None:
        PARAM_RESET_CONFIG_DEFAULT = 2

        self._mav.command_int_send(self.MAVLINK_SYSTEM_ID,
                            common.MAV_COMP_ID_ALL,
                            0,
                            common.MAV_CMD_PREFLIGHT_STORAGE,
                            0,
                            0,
                            PARAM_RESET_CONFIG_DEFAULT,
                            0,
                            0,
                            0,
                            0,
                            0,
                            0,
                            True)

    def write_params_to_flash(self, on_complete: Callable) -> None:
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
        #def cb(msg):
        #    # Remove temporary message handler
        #    self.del_message_handler(common.MAVLINK_MSG_ID_PARAM_VALUE, cb)
        #    if on_ack is not None:
        #        on_ack(msg)

        #self.add_message_handler(common.MAVLINK_MSG_ID_PARAM_VALUE, cb)
        self._mav.param_set_send(self.MAVLINK_SYSTEM_ID,
                                 common.MAV_COMP_ID_ALL,
                                 name,
                                 value,
                                 type,
                                 True)

    def set_parameter_blocking(self, name: str, value: float, type: int) -> None:
        self.set_parameter()
        response = self._get_parameters.get()
        print(response)

    def _get_parameters(self,
                       on_complete: Callable[..., dict] = None,
                       max_attempts: int = 5,
                       delay_between_attempts_ms: int = 1000) -> None:

        attempt = 1
        params = []

        while attempt < max_attempts and self._param_values.empty():
            self.logger.info('> Sending PARAM Request')
            # Send a PARAM Request list message
            self._mav.param_request_list_send(self.MAVLINK_SYSTEM_ID,
                                          common.MAV_COMP_ID_ALL,
                                          True)
            # Wait for some time for us to get response
            time.sleep(self._param_receive_timeout_ms / 1000)

            if self._param_values.empty():
                # If we got no response, we'll wait some time before sending
                # another request
                time.sleep(delay_between_attempts_ms / 1000)
                attempt += 1

        params = {}
        while not self._param_values.empty():
            param = self._param_values.get()
            params[param.param_id] = param

        self.logger.info(f'Recevied params {len(params)} parameters:')
        for name, p in params.items():
            self.logger.info(f'    {name}: {p.param_value}')

        if on_complete is not None:
            on_complete(params)

    def get_parameters(self,
                       on_complete: Callable[..., dict] = None,
                       max_attempts: int = 5,
                       delay_between_attempts_ms: int = 1000) -> None:

        Thread(target=self._get_parameters,
               args=(on_complete,
                     max_attempts,
                     delay_between_attempts_ms),
               daemon=True).start()

    def set_motor_throttle_test(self, motor: int, throttle: int) -> None:
        '''
        Sets the throttle of the given motor to the given throttle.

        Parameters:
            motor: Number of motor, eg 1, 2, ...
            throttle: Throttle value of motor, 0-100.
        '''
        self._mav.command_int_send(
            self.MAVLINK_SYSTEM_ID,
            common.MAV_COMP_ID_ALL,
            0,
            common.MAV_CMD_DO_MOTOR_TEST,
            0, 0,
            motor, # 1
            common.MOTOR_TEST_THROTTLE_PERCENT, # 2
            throttle, # 3
            0, 0, 0, 0
        )

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
                msg_type = type(msg)
                handlers = self._msg_handlers.get(msg_type)

                if not handlers:
                    print(f'No handler found for message: {msg}')
                    pass
                else:
                    for handler in handlers:
                        handler(msg)
            except Empty:
                pass
            except TimeoutError:
                pass

    def _receive_thread(self) -> None:
        self.logger.info('RX Thread started')
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
                self.logger.warning('Device disconnected or multiple access on port?')
                self.stop()
            except TypeError as e:
                # This occurs of we're disconnected
                pass
        self.logger.info('RX Thread ended')


if __name__ == '__main__':
    PORT = sys.argv[1]
    asac = ASAC(PORT)
    asac.start()
    while True:
        pass