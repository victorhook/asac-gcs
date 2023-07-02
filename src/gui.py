from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from threading import Thread
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo
import time
from typing import List, Dict

from pymavlink.dialects.v10 import common

from asac import ASAC


PROJECT_ROOT = Path(__file__).absolute().parent.parent
RESOURCES = PROJECT_ROOT.joinpath('resources')


def get_image(name: str) -> tk.PhotoImage:
    return tk.PhotoImage(file=RESOURCES.joinpath(name))


# Settings struct
@dataclass
class SettingsGeneral:
    craft_name: str

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
label_style = {'bg': BASE_BACKGROUND}
entry_style = {'bg': BASE_BACKGROUND}
btn_style = {'bg': 'white', 'fg': 'black'}


class ParamFloat:

    def __init__(self, parent, row: int, name: str, value: float,
                 readonly: bool = False, decimals: int = 4) -> None:
        self._decimals = decimals
        if readonly:
            state = 'readonly'
        else:
            state = 'normal'
        pack = {'padx': 5, 'pady': 5, 'sticky': tk.W}
        tk.Label(parent, text=name, **label_style).grid(row=row, column=0, **pack)
        self._entry = tk.Entry(parent, state=state, **entry_style)
        self._entry.grid(row=row, column=1, **pack)
        self.set(value)

    def get(self) -> float:
        return float(self._entry.get())

    def set(self, value: float) -> None:
        state = self._entry['state']
        self._entry['state'] = 'normal'
        self._entry.delete(0, tk.END)
        self._entry.insert(tk.END, round(value, self._decimals))
        self._entry['state'] = state

class Content(tk.Frame):

    def __init__(self, parent, title: str) -> None:
        super().__init__(parent, **frame_style)
        title = tk.Label(self, text=title, **label_style)
        title.config(font=('Courier', 20))
        title.pack()
        self.content = tk.Frame(self, **frame_style)
        self.content.pack()
        self.name = title

class AttitudeInfo(tk.LabelFrame):

    def __init__(self, parent) -> None:
        super().__init__(parent, text='Attitude', **frame_style)
        pad = {}
        self.time_boot_ms = ParamFloat(self, 0, 'MS since boot', 0, True)
        self.roll = ParamFloat(self, 1, 'Roll', 0, True)
        self.pitch = ParamFloat(self, 2, 'Pitch', 0, True)
        self.yaw = ParamFloat(self, 3, 'Yaw', 0, True)
        self.rollspeed = ParamFloat(self, 4, 'Roll Speed', 0, True)
        self.pitchspeed = ParamFloat(self, 5, 'Pitch Speed', 0, True)
        self.yawspeed = ParamFloat(self, 6, 'Yaw Speed', 0, True)

class ContentGeneral(Content):
    def __init__(self, parent, save_callback: callable) -> None:
        super().__init__(parent, 'General')
        pack = {'padx': 10, 'pady': 10}

        self.config_frame = tk.Frame(self.content, **frame_style)
        self.attitude_info = AttitudeInfo(self.content)

        tk.Label(self.config_frame, text='Craft name', **label_style).grid(row=0, column=0, **pack)
        tk.Label(self.config_frame, text='Rotation X', **label_style).grid(row=1, column=0, **pack)
        tk.Label(self.config_frame, text='Rotation Y', **label_style).grid(row=2, column=0, **pack)
        tk.Label(self.config_frame, text='Rotation Z', **label_style).grid(row=3, column=0, **pack)
        tk.Label(self.config_frame, text='ESC Protocol', **label_style).grid(row=4, column=0, **pack)

        self.input_craft_name = tk.Entry(self.config_frame, **entry_style)
        self.input_rotation_x = tk.Entry(self.config_frame, **entry_style)
        self.input_rotation_y = tk.Entry(self.config_frame, **entry_style)
        self.input_rotation_z = tk.Entry(self.config_frame, **entry_style)
        self.input_esc_protocol = ttk.Combobox(self.config_frame)

        self.input_craft_name.grid(row=0, column=1, **pack)
        self.input_rotation_x.grid(row=1, column=1, **pack)
        self.input_rotation_y.grid(row=2, column=1, **pack)
        self.input_rotation_z.grid(row=3, column=1, **pack)
        self.input_esc_protocol.grid(row=4, column=1, **pack)

        btn_save = tk.Button(self.config_frame, text='Save', **btn_style, command=save_callback)
        btn_save.grid(row=5, columnspan=2)

        frame_pad = {'padx': 10, 'pady': 10}
        self.attitude_info.pack(side=tk.LEFT, **frame_pad)
        self.config_frame.pack(side=tk.LEFT, **frame_pad)

    def set_attitude_info(self, msg: common.MAVLink_attitude_message) -> None:
        self.attitude_info.time_boot_ms.set(msg.time_boot_ms)
        self.attitude_info.roll.set(msg.roll)
        self.attitude_info.pitch.set(msg.pitch)
        self.attitude_info.yaw.set(msg.yaw)
        self.attitude_info.rollspeed.set(msg.rollspeed)
        self.attitude_info.pitchspeed.set(msg.pitchspeed)
        self.attitude_info.yawspeed.set(msg.yawspeed)


class ContentPid(Content):
    def __init__(self, parent, save_callback: callable) -> None:
        super().__init__(parent, 'PID')
        pack = {'padx': 10, 'pady': 10, 'ipadx': 5, 'ipady': 5}
        self.frame_roll = tk.LabelFrame(self.content, **frame_style, text='ROLL')
        self.frame_pitch = tk.LabelFrame(self.content, **frame_style, text='PITCH')
        self.frame_yaw = tk.LabelFrame(self.content, **frame_style, text='YAW')

        self.roll_p = ParamFloat(self.frame_roll, 0, 'P', 0)
        self.roll_i = ParamFloat(self.frame_roll, 1, 'I', 0)
        self.roll_d = ParamFloat(self.frame_roll, 2, 'D', 0)
        self.pitch_p = ParamFloat(self.frame_pitch, 0, 'P', 0)
        self.pitch_i = ParamFloat(self.frame_pitch, 1, 'I', 0)
        self.pitch_d = ParamFloat(self.frame_pitch, 2, 'D', 0)
        self.yaw_p = ParamFloat(self.frame_yaw, 0, 'P', 0)
        self.yaw_i = ParamFloat(self.frame_yaw, 1, 'I', 0)
        self.yaw_d = ParamFloat(self.frame_yaw, 2, 'D', 0)

        self.frame_roll.pack(side=tk.LEFT, **pack)
        self.frame_pitch.pack(side=tk.LEFT, **pack)
        self.frame_yaw.pack(side=tk.LEFT, **pack)

        btn_save = tk.Button(self, text='Save', **btn_style, command=save_callback)
        btn_save.pack()

    def set_pid_values(self, pid_values: Dict[str, float]) -> None:
        self.roll_p.set(pid_values.get('roll_p', 0))
        self.roll_i.set(pid_values.get('roll_i', 0))
        self.roll_d.set(pid_values.get('roll_d', 0))
        self.pitch_p.set(pid_values.get('pitch_p', 0))
        self.pitch_i.set(pid_values.get('pitch_i', 0))
        self.pitch_d.set(pid_values.get('pitch_d', 0))
        self.yaw_p.set(pid_values.get('yaw_p', 0))
        self.yaw_i.set(pid_values.get('yaw_i', 0))
        self.yaw_d.set(pid_values.get('yaw_d', 0))

class ContentMotors(Content):
    def __init__(self, parent) -> None:
        super().__init__(parent, 'Motors')



class Gui(tk.Tk):

    WIDTH = 1000
    HEIGHT = 800

    def __init__(self) -> None:
        super().__init__()
        # Some general UI
        self.BG = BASE_BACKGROUND
        self.geometry(f'{self.WIDTH}x{self.HEIGHT}')
        self.config(bg=self.BG)
        self.title('ASAC GCS')

        # Backend and control
        self._asac = ASAC()
        # Add handlers for MAVlink messages
        self._asac.add_message_handler(common.MAVLINK_MSG_ID_HEARTBEAT, self._mavlink_heartbeat)
        #self._asac.add_message_handler(common.MAVLINK_MSG_ID_SCALED_IMU, self._mavlink_scaled_imu)
        self._asac.add_message_handler(common.MAVLINK_MSG_ID_ATTITUDE, self._mavlink_attitude)

        # -- Frames --- #
        frame_pack_kw = {'padx': 5, 'pady': 5}

        self.frame = tk.Frame(self, **frame_style)
        self.frame_ctrl = tk.Frame(self.frame, **frame_style)
        self.frame_main = tk.Frame(self.frame, **frame_style)
        self.frame_sidebar = tk.Frame(self.frame_main, **frame_style)
        self.frame_content = tk.Frame(self.frame_main, **frame_style)

        # -- Control frame -- #
        ctrl_pack_kw = {'padx': '10', 'pady': '0'}
        self.img_btn_connected = get_image('btn_connected.png')
        self.img_btn_disconnected = get_image('btn_disconnected.png')
        self.img_title = get_image('title.png')
        title = tk.Label(self.frame_ctrl, image=self.img_title, **label_style)

        serial_port = tk.Label(self.frame_ctrl, text='Serial port', **label_style)
        self.combo_serial_port_var = tk.StringVar()
        self.combo_serial_port = ttk.Combobox(self.frame_ctrl, width=40,
                                              state='readonly',
                                              textvariable=self.combo_serial_port_var)
        self.btn_connect = tk.Button(self.frame_ctrl, text='Connect',
                                     command=self._connect, **btn_style)
        self.label_image_connected = tk.Label(self.frame_ctrl, **label_style)

        title.pack(side=tk.LEFT, **ctrl_pack_kw)
        self.label_image_connected.pack(side=tk.RIGHT, **ctrl_pack_kw)
        self.btn_connect.pack(side=tk.RIGHT, **ctrl_pack_kw)
        self.combo_serial_port.pack(side=tk.RIGHT, **ctrl_pack_kw)
        serial_port.pack(side=tk.RIGHT, **ctrl_pack_kw)

        # -- Main content -- #
        self.content_general = ContentGeneral(self.frame_content, self.general_save)
        self.content_pid = ContentPid(self.frame_content, self.pid_save)
        self.content_motors = ContentMotors(self.frame_content)
        self.contents = {
            'general': self.content_general,
            'pid': self.content_pid,
            'motors': self.content_motors
        }

        # -- Side bar -- #
        sidebar_btn_style = {'bg': self.BG}
        sidebar_btn_pack = {'ipadx': 10, 'ipady': 10, 'fill': tk.X}
        for content in self.contents:
            # The weird-looking lambda here is just using a default value
            # for the argument.
            btn = tk.Button(self.frame_sidebar, text=content.upper(),
                            **sidebar_btn_style,
                            command=lambda content=content: self.set_content(content))
            btn.pack(**sidebar_btn_pack)

        # Pack all frames
        self.frame_ctrl.pack(fill=tk.X, **frame_pack_kw, anchor=tk.N)
        # Add horizontal line between control bar and main
        tk.Canvas(self.frame, background='gray', height=1).pack(fill=tk.X)
        self.frame_main.pack(fill=tk.BOTH, expand=True, **frame_pack_kw)

        self.frame_sidebar.pack(side=tk.LEFT, fill=tk.Y, **frame_pack_kw)
        self.frame_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, **frame_pack_kw)

        #self.frame.pack(fill=tk.BOTH, expand=True)
        self.frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Info poup
        self._info_showing = False
        self._info = tk.Label(self, bg='red')

        # States
        self.active_content: str = 'general'

        self._available_serial_ports: List[ListPortInfo] = []
        Thread(target=self._available_serial_port_thread, daemon=True).start()

        # Update UI state once before we start
        self._update_state()

    def _connect(self) -> None:
        port = self.combo_serial_port_var.get()
        if port:
            port, desc = port.split('(')
            port = port.strip()
            connect_ok = self._asac.start(port)
            if connect_ok:
                self._asac.get_parameters(self._update_parameters)
                self._update_state()
            else:
                self.info_popup(f'Failed to connect to port {port}', bg='red')

    def _disconnect(self) -> None:
        self._asac.stop()
        self._update_state()

    def _update_parameters(self, params: Dict[str, common.MAVLink_param_value_message]) -> None:
        # TODO: Fix names
        pid_params = {
            'roll_p':  params.get('pid_gyro_roll_p', 0).param_value,
            'roll_i':  params.get('pid_gyro_roll_i', 0).param_value,
            'roll_d':  params.get('pid_gyro_roll_d', 0).param_value,
            'pitch_p': params.get('pid_gyro_pitch_p', 0).param_value,
            'pitch_i': params.get('pid_gyro_pitch_i', 0).param_value,
            'pitch_d': params.get('pid_gyro_pitch_d', 0).param_value,
            'yaw_p':   params.get('pid_gyro_yaw_p', 0).param_value,
            'yaw_i':   params.get('pid_gyro_yaw_i', 0).param_value,
            'yaw_d':   params.get('pid_gyro_yaw_d', 0).param_value
        }
        self.content_pid.set_pid_values(pid_params)

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
            x=self.winfo_width()-(len(msg)*12),
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
        return False

    def set_content(self, new_content_name: str) -> None:
        if new_content_name != self.active_content:
            self.active_content = new_content_name

        self._update_state()

    def _update_state(self) -> None:
        if self.is_connected():
            self.label_image_connected.config(image=self.img_btn_connected)
            self.btn_connect['text'] = 'Disconnect'
            self.btn_connect['command'] = self._disconnect
        else:
            self.label_image_connected.config(image=self.img_btn_disconnected)
            self.btn_connect['text'] = 'Connect'
            self.btn_connect['command'] = self._connect

        for content in self.contents.values():
            content: Content
            content.pack_forget()

        self.combo_serial_port['values'] = [f'{port.device} ({port.description})' for port in self._available_serial_ports]
        if self.combo_serial_port['values']:
            self.combo_serial_port.current(0)
        else:
            self.combo_serial_port_var.set('')

        self.contents[self.active_content].pack(fill=tk.BOTH, expand=True)

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
        print('HEARTBEAT')

    def _mavlink_attitude(self, msg: common.MAVLink_attitude_message) -> None:
        self.contents['general'].set_attitude_info(msg)

if __name__ == '__main__':
    gui = Gui()
    gui.mainloop()