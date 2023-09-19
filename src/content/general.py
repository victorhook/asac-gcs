from asac import ASAC
from content.content import Content, ParamFloat
from tkinter import ttk
import tkinter as tk
from pymavlink.dialects.v10 import common

from utils import run_thread


class AttitudeInfo(ttk.LabelFrame):

    def __init__(self, parent) -> None:
        super().__init__(parent, text='Attitude')
        pad = {}
        self.time_boot_ms = ParamFloat(self, 0, 'MS since boot', 0, True)
        self.roll = ParamFloat(self, 1, 'Roll', 0, True)
        self.pitch = ParamFloat(self, 2, 'Pitch', 0, True)
        self.yaw = ParamFloat(self, 3, 'Yaw', 0, True)
        self.rollspeed = ParamFloat(self, 4, 'Roll Speed', 0, True)
        self.pitchspeed = ParamFloat(self, 5, 'Pitch Speed', 0, True)
        self.yawspeed = ParamFloat(self, 6, 'Yaw Speed', 0, True)



class ContentGeneral(Content):
    def __init__(self, parent, asac: ASAC, save_callback: callable) -> None:
        super().__init__(parent, 'General')
        self.asac = asac
        pack = {'padx': 10, 'pady': 10}

        self.config_frame = ttk.Frame(self.content)
        self.attitude_info = AttitudeInfo(self.content)

        ttk.Label(self.config_frame, text='Craft name').grid(row=0, column=0, **pack)
        ttk.Label(self.config_frame, text='Rotation X').grid(row=1, column=0, **pack)
        ttk.Label(self.config_frame, text='Rotation Y').grid(row=2, column=0, **pack)
        ttk.Label(self.config_frame, text='Rotation Z').grid(row=3, column=0, **pack)
        ttk.Label(self.config_frame, text='ESC Protocol').grid(row=4, column=0, **pack)

        self.input_craft_name = ttk.Entry(self.config_frame)
        self.input_rotation_x = ttk.Entry(self.config_frame)
        self.input_rotation_y = ttk.Entry(self.config_frame)
        self.input_rotation_z = ttk.Entry(self.config_frame)
        self.input_esc_protocol = ttk.Combobox(self.config_frame)

        self.input_craft_name.grid(row=0, column=1, **pack)
        self.input_rotation_x.grid(row=1, column=1, **pack)
        self.input_rotation_y.grid(row=2, column=1, **pack)
        self.input_rotation_z.grid(row=3, column=1, **pack)
        self.input_esc_protocol.grid(row=4, column=1, **pack)

        btn_save = ttk.Button(self.config_frame, text='Save', command=save_callback)
        btn_save.grid(row=5, columnspan=2, **pack)
        btn_save = ttk.Button(self.config_frame, text='Reset system settings', command=self._reset_settings)
        btn_save.grid(row=6, columnspan=2, **pack)

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

    def _reset_settings(self) -> None:
        self.logger.info('Resetting system parameters!')
        run_thread(self.asac.reset_parameters)

