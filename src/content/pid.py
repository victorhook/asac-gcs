from content.content import Content, ParamFloat
from typing import Dict

from asac import ASAC
from tkinter import ttk
import tkinter as tk
from utils import run_thread

from pymavlink.dialects.v10 import common


class ContentPid(Content):
    def __init__(self, parent, save_callback: callable, asac: ASAC) -> None:
        super().__init__(parent, 'PID')
        self._asac = asac
        pack = {'padx': 10, 'pady': 10, 'ipadx': 5, 'ipady': 5}
        self.frame_roll = ttk.LabelFrame(self.content, text='ROLL')
        self.frame_pitch = ttk.LabelFrame(self.content, text='PITCH')
        self.frame_yaw = ttk.LabelFrame(self.content, text='YAW')

        self.pid_gyro_roll_p = ParamFloat(self.frame_roll, 0, 'P', 0)
        self.pid_gyro_roll_i = ParamFloat(self.frame_roll, 1, 'I', 0)
        self.pid_gyro_roll_d = ParamFloat(self.frame_roll, 2, 'D', 0)
        self.pid_gyro_roll_f = ParamFloat(self.frame_roll, 3, 'FF', 0)
        self.pid_gyro_pitch_p = ParamFloat(self.frame_pitch, 0, 'P', 0)
        self.pid_gyro_pitch_i = ParamFloat(self.frame_pitch, 1, 'I', 0)
        self.pid_gyro_pitch_d = ParamFloat(self.frame_pitch, 2, 'D', 0)
        self.pid_gyro_pitch_f = ParamFloat(self.frame_pitch, 3, 'FF', 0)
        self.pid_gyro_yaw_p = ParamFloat(self.frame_yaw, 0, 'P', 0)
        self.pid_gyro_yaw_i = ParamFloat(self.frame_yaw, 1, 'I', 0)
        self.pid_gyro_yaw_d = ParamFloat(self.frame_yaw, 2, 'D', 0)
        self.pid_gyro_yaw_f = ParamFloat(self.frame_yaw, 3, 'FF', 0)

        self.frame_roll.pack(side=tk.LEFT, **pack)
        self.frame_pitch.pack(side=tk.LEFT, **pack)
        self.frame_yaw.pack(side=tk.LEFT, **pack)

        btn_save = ttk.Button(self, text='Save', command=self._save)
        btn_save.pack()

    def _save(self) -> None:
        parameters = {
            b'pid_gyro_roll_p': (self.pid_gyro_roll_p.get(), 9),
            b'pid_gyro_roll_i': (self.pid_gyro_roll_i.get(), 9),
            b'pid_gyro_roll_d': (self.pid_gyro_roll_d.get(), 9),
            b'pid_gyro_roll_f': (self.pid_gyro_roll_f.get(), 9),
            b'pid_gyro_pitch_p': (self.pid_gyro_pitch_p.get(), 9),
            b'pid_gyro_pitch_i': (self.pid_gyro_pitch_i.get(), 9),
            b'pid_gyro_pitch_d': (self.pid_gyro_pitch_d.get(), 9),
            b'pid_gyro_pitch_f': (self.pid_gyro_pitch_f.get(), 9),
            b'pid_gyro_yaw_p': (self.pid_gyro_yaw_p.get(), 9),
            b'pid_gyro_yaw_i': (self.pid_gyro_yaw_i.get(), 9),
            b'pid_gyro_yaw_d': (self.pid_gyro_yaw_d.get(), 9),
            b'pid_gyro_yaw_f': (self.pid_gyro_yaw_f.get(), 9),
        }

        run_thread(self._asac.set_parameters, parameters, self._on_param_set)

    def _on_param_set(self) -> None:
        print('PARAM SET OK, writing to flash..')
        self._asac.write_params_to_flash(self._on_write_to_flash_ok)

    def _on_write_to_flash_ok(self) -> None:
        print('Write to flash OK, rebooting..')
        self._asac.reboot()

    def set_pid_values(self, pid_values: Dict[str, common.MAVLink_param_value_message]) -> None:
        PID_PARAMS = [
            'pid_gyro_roll_p',
            'pid_gyro_roll_i',
            'pid_gyro_roll_d',
            'pid_gyro_roll_f',
            'pid_gyro_pitch_p',
            'pid_gyro_pitch_i',
            'pid_gyro_pitch_d',
            'pid_gyro_pitch_f',
            'pid_gyro_yaw_p',
            'pid_gyro_yaw_i',
            'pid_gyro_yaw_d',
            'pid_gyro_yaw_f',
        ]
        for pid_param in PID_PARAMS:
            value = pid_values.get(pid_param)
            if value is not None:
                value = value.param_value
            else:
                value = 0

            getattr(self, pid_param).set(value)
