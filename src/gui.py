from dataclasses import dataclass, asdict
import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from threading import Thread
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo
import time
from typing import List, Dict, Tuple
import sys
import utils

from pymavlink.dialects.v10 import common


from asac import ASAC
from content.content import Content
from content.general import ContentGeneral
from content.motors import ContentMotors
from content.pid import ContentPid
from content.rx import ContentRx
from content.vtx import ContentVTX
from content.pid import ContentPid
from utils import run_thread


PROJECT_ROOT = Path(__file__).absolute().parent.parent
RESOURCES = PROJECT_ROOT.joinpath('resources')


def get_image(name: str) -> tk.PhotoImage:
    return tk.PhotoImage(file=RESOURCES.joinpath(name))


# def info_popup(msg: str, bg='green', timeout_ms: int = 3000) -> None:

DEFAULT_WINDOW_WIDTH = 1400
DEFAULT_WINDOW_HEIGHT = 900

FONT = 'Helvetica'


# Settings struct
@dataclass
class SettingsGeneral:
    craft_name: str
    #esc_protocol: ESC_Protocol
    #rx_protocol: RX_Protocol
    #vtx: VTX


@dataclass
class SettingsPID:
    roll_p: float = 0.0
    roll_i: float = 0.0
    roll_d: float = 0.0
    pitch_p: float = 0.0
    pitch_i: float = 0.0
    pitch_d: float = 0.0
    yaw_p: float = 0.0
    yaw_i: float = 0.0
    yaw_d: float = 0.0



# Global variables
pid = SettingsPID()


# -- Styles -- #
BASE_BACKGROUND = 'white'
frame_style = {'bg': BASE_BACKGROUND}




class LogDebug(ttk.LabelFrame):

    def __init__(self, parent) -> None:
        super().__init__(parent, text='Debug Console')
        self.text = tk.Text(self, height=10)
        btn_clear = ttk.Button(self, text='Clear', command=lambda: self.text.delete("1.0","end"))

        btn_clear.pack(anchor=tk.W)
        self.text.pack(side=tk.BOTTOM, expand=True, fill=tk.X)

    def log(self, msg: str) -> None:
        self.text.insert(tk.END, msg)
        self.text.see(tk.END)


class Battery(tk.Canvas):

    BG = '#AA0000'
    FILL = '#00BB00'

    VOLTAGE_TABLE = [
        (3.2, 4.2),
        (6.4, 8.4),
        (9.6, 12.6),
        (12.8, 16.8)
    ]

    def __init__(self, parent) -> None:
        self.w = 100
        self.h = 35
        super().__init__(parent, width=self.w, height=self.h, background=self.BG)
        self._fill = self.create_rectangle(0, 0, 0, self.h, fill=self.FILL)
        self._text = self.create_text(self.w//2, self.h//2+5, text='0V', font=(FONT, 14, 'bold'))
        self.set(0)

    def set(self, voltage: float) -> None:
        min_, max_ = self._get_min_max(voltage)
        print(min_, max_)
        perc = (voltage - min_) / (max_ - min_)
        self.coords(self._fill, 0, 0, perc*self.w, self.h)
        self.itemconfigure(self._text, text=f'{voltage:.2f} V')

    def _get_min_max(self, voltage: float) -> Tuple[float, float]:
        for min_, max_ in self.VOLTAGE_TABLE:
            if voltage < max_:
                return min_, max_
        # If voltage is higher than max we'll return last one
        return self.VOLTAGE_TABLE[-1]

class Gui(tk.Tk):

    _SETTINGS_PATH = PROJECT_ROOT.joinpath('gui_settings.json')

    @dataclass
    class GuiSettings:
        active_content: str
        window_width: int
        window_height: int

    def __init__(self) -> None:
        super().__init__()
        self.logger = utils.get_logger()

        self.protocol("WM_DELETE_WINDOW", self._on_exit)

        self.settings: self.GuiSettings

        # Load previous settings
        self.settings = self._load_settings()

        # Some general UI
        self.BG = BASE_BACKGROUND
        self.geometry(f'{self.settings.window_width}x{self.settings.window_width}')
        self.title('ASAC GCS')

        # Backend and control
        self._asac = ASAC(on_connect=self._on_connect,
                          on_disconnect=self._on_disconnect)
        # Add handlers for MAVlink messages
        self._asac.add_message_handler(common.MAVLink_statustext_message, self._mavlink_statustext)
        self._asac.add_message_handler(common.MAVLink_heartbeat_message, self._mavlink_heartbeat)
        #self._asac.add_message_handler(common.MAVLINK_MSG_ID_SCALED_IMU, self._mavlink_scaled_imu)
        self._asac.add_message_handler(common.MAVLink_attitude_message, self._mavlink_attitude)
        self._asac.add_message_handler(common.MAVLink_battery_status_message, self._mavlink_battery_status)

        # -- Frames --- #
        frame_pack_kw = {'padx': 5, 'pady': 5}

        self.frame = ttk.Frame(self)
        self.frame_ctrl = ttk.Frame(self.frame)
        self.frame_main = ttk.Frame(self.frame)
        self.frame_sidebar = ttk.Frame(self.frame_main)
        self.frame_content = ttk.Frame(self.frame_main)
        self.log_debug = LogDebug(self.frame)

        # -- Control frame -- #
        ctrl_pack_kw = {'padx': '10', 'pady': '0'}
        self.img_btn_connected = get_image('btn_connected.png')
        self.img_btn_disconnected = get_image('btn_disconnected.png')
        self.img_title = get_image('title.png')
        title = ttk.Label(self.frame_ctrl, image=self.img_title)

        serial_port = ttk.Label(self.frame_ctrl, text='Serial port')
        self.combo_serial_port_var = tk.StringVar()
        self.combo_serial_port = ttk.Combobox(self.frame_ctrl, width=40,
                                              state='readonly',
                                              textvariable=self.combo_serial_port_var)
        self.btn_connect = ttk.Button(self.frame_ctrl, text='Connect',
                                     command=self._connect)
        self.btn_reboot = ttk.Button(self.frame_ctrl, text='Reboot',
                                     command=self._reboot)
        self.battery = Battery(self.frame_ctrl)
        self.label_image_connected = ttk.Label(self.frame_ctrl)

        title.pack(side=tk.LEFT, **ctrl_pack_kw)
        self.label_image_connected.pack(side=tk.RIGHT, **ctrl_pack_kw)
        self.battery.pack(side=tk.RIGHT, **ctrl_pack_kw)
        self.btn_reboot.pack(side=tk.RIGHT, **ctrl_pack_kw)
        self.btn_connect.pack(side=tk.RIGHT, **ctrl_pack_kw)
        self.combo_serial_port.pack(side=tk.RIGHT, **ctrl_pack_kw)
        serial_port.pack(side=tk.RIGHT, **ctrl_pack_kw)

        # -- Main content -- #
        self.content_general = ContentGeneral(self.frame_content, self._asac, self.general_save)
        self.content_pid = ContentPid(self.frame_content, self.pid_save, self._asac)
        self.content_motors = ContentMotors(self.frame_content, self._asac, self.info_popup)
        self.content_rx = ContentRx(self.frame_content, self._asac)
        self.content_vtx = ContentVTX(self.frame_content)
        self.contents = {
            'general': self.content_general,
            'pid': self.content_pid,
            'motors': self.content_motors,
            'rx': self.content_rx,
            'vtx': self.content_vtx,
        }

        # -- Side bar -- #
        sidebar_btn_pack = {'ipadx': 10, 'ipady': 10, 'fill': tk.X}
        for content in self.contents:
            # The weird-looking lambda here is just using a default value
            # for the argument.
            btn = ttk.Button(self.frame_sidebar, text=content.upper(),
                            command=lambda content=content: self.set_content(content))
            btn.pack(**sidebar_btn_pack)

        # Add stdout & stderr to debug console
        self.sys_stdout = sys.stdout.write
        self.sys_stderr = sys.stderr.write

        def stdout(msg):
            self.log_debug.log(msg)
            self.sys_stdout(msg)
        def stderr(msg):
            self.log_debug.log(msg)
            self.sys_stderr(msg)

        sys.stdout.write = stdout
        sys.stderr.write = stderr

        # Pack all frames
        self.frame_ctrl.pack(fill=tk.X, **frame_pack_kw, anchor=tk.N)
        # Add horizontal line between control bar and main
        tk.Canvas(self.frame, background='gray', height=1).pack(fill=tk.X)
        self.frame_main.pack(fill=tk.BOTH, expand=True, **frame_pack_kw)

        self.frame_sidebar.pack(side=tk.LEFT, fill=tk.Y, **frame_pack_kw)
        self.frame_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, **frame_pack_kw)
        self.log_debug.pack(side=tk.BOTTOM, fill=tk.X, **frame_pack_kw)

        #self.frame.pack(fill=tk.BOTH, expand=True)
        self.frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Info poup
        self._info_showing = False
        self._info = tk.Label(self)

        self._available_serial_ports: List[ListPortInfo] = []
        Thread(target=self._available_serial_port_thread, daemon=True).start()

        # Update UI state once before we start
        self._update_state()

    def _on_connect(self) -> None:
        run_thread(self._asac.get_parameters, self._update_parameters)
        self.info_popup(f'Connected to {self._asac.port}', bg='green')
        self._update_state()

    def _on_disconnect(self) -> None:
        self._update_state()

    def _connect(self) -> None:
        port = self.combo_serial_port_var.get()
        if port:
            port, desc = port.split('(')
            port = port.strip()
            run_thread(self._asac.start, port)
            #self.info_popup(f'Failed to connect to port {port}', bg='red')
        else:
            self.info_popup(f'No serial port available', bg='red')

    def _disconnect(self) -> None:
        run_thread(self._asac.stop)

    def _update_parameters(self, params: Dict[str, common.MAVLink_param_value_message]) -> None:
        self.content_pid.set_pid_values(params)

    def _reboot(self) -> None:
        run_thread(self._asac.reboot)

    def general_save(self) -> None:
        self.info_popup('Saved!', timeout_ms=1000)

    def pid_save(self) -> None:
        self.info_popup('Saved!', timeout_ms=1000)

    def info_popup(self, msg: str, bg='green', timeout_ms: int = 3000) -> None:
        '''
        Shows an info popup at the bottom of the screen, with the given message,
        background color and timeout duration.
        '''
        if self._info_showing:
            return

        self._info_showing = True

        self._info.config(text=msg, bg=bg, height=2, width=len(msg)+2)
        self.update()
        self._info.place(
            x=self.winfo_width() // 2,
            y=self.winfo_height()-40
        )

        def wait_until_complete(timeout_ms: int) -> None:
            time.sleep(timeout_ms/1000)
            self._info.place_forget()
            self._info_showing = False

        Thread(target=wait_until_complete,
               args=(timeout_ms, ),
               daemon=True).start()

    def is_connected(self) -> bool:
        return self._asac.is_connected()

    def set_content(self, new_content_name: str) -> None:
        if new_content_name != self.settings.active_content:
            self.settings.active_content = new_content_name

        self._update_state()

    def _load_settings(self) -> 'GuiSettings':
        try:
            with open(self._SETTINGS_PATH) as f:
                data = json.load(f)
                return self.GuiSettings(**data)
        except Exception as e:
            self.logger.error(f'Exception when loading settings from {self._SETTINGS_PATH}:')
            self.logger.error(e)

            # Create default settings
            self.settings = self.GuiSettings(
                active_content='general',
                window_width=DEFAULT_WINDOW_WIDTH,
                window_height=DEFAULT_WINDOW_HEIGHT
            )
            self._store_settings()
            return self.settings

    def _store_settings(self) -> None:
        ''' Writes settings to disk, as json. '''
        with open(self._SETTINGS_PATH, 'w') as f:
            json.dump(
                asdict(self.settings),
                f,
                indent=4
            )

    def _on_exit(self) -> None:
        self.logger.info('Exiting GUI, storing settings to disk first')

        # Save window dimensions
        self.settings.window_width = self.winfo_width()
        self.settings.window_height = self.winfo_height()

        self._store_settings()
        self.destroy()

    def _update_state(self) -> None:
        if self.is_connected():
            self.label_image_connected.config(image=self.img_btn_connected)
            self.btn_connect['text'] = 'Disconnect'
            self.btn_connect['command'] = self._disconnect
            self.btn_reboot['state'] = 'enabled'
        else:
            self.label_image_connected.config(image=self.img_btn_disconnected)
            self.btn_connect['text'] = 'Connect'
            self.btn_connect['command'] = self._connect
            self.btn_reboot['state'] = tk.DISABLED

        for content in self.contents.values():
            content: Content
            content.pack_forget()

        self.combo_serial_port['values'] = [f'{port.device} ({port.description})' for port in self._available_serial_ports]
        if self.combo_serial_port['values']:
            self.combo_serial_port.current(0)
        else:
            self.combo_serial_port_var.set('')

        self.contents[self.settings.active_content].pack(fill=tk.BOTH, expand=True)

    def _available_serial_port_thread(self) -> None:
        while not self.is_connected():
            available_ports = []
            ports = list_ports.comports()
            for port in ports:
                available_ports.append(port)

            if available_ports != self._available_serial_ports:
                self._available_serial_ports = available_ports
                self._update_state()

            time.sleep(1)

    # -- MAVLINK message handlers -- #
    def _mavlink_heartbeat(self, msg: common.MAVLink_heartbeat_message) -> None:
        #print('HEARTBEAT')
        pass

    def _mavlink_statustext(self, msg: common.MAVLink_heartbeat_message) -> None:
        print(msg)

    def _mavlink_attitude(self, msg: common.MAVLink_attitude_message) -> None:
        self.contents['general'].set_attitude_info(msg)

    def _mavlink_battery_status(self, msg: common.MAVLink_battery_status_message) -> None:
        vbat_mv = msg.voltages[0]
        self.battery.set(vbat_mv / 1000)


if __name__ == '__main__':
    gui = Gui()
    style = ttk.Style()
    style.theme_use('clam')
    style.configure(
        '.',
        background='white',
        foreground='black',
        #background='#090A4E',
        #foreground='#ffffff',
        font='helvetica 16',
    )
    gui.mainloop()