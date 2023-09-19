from content.content import Content
from tkinter import ttk
import tkinter as tk

from threading import Thread, Event
from typing import Tuple
import time

from asac import ASAC


class MotorSlider(ttk.Frame):

    def __init__(self, parent, motor: int, set_callback: callable) -> None:
        super().__init__(parent)
        self.motor = motor
        self.name = f'M{motor}'
        self.set_callback = set_callback

        self._stringvar = tk.StringVar()
        self._stringvar.set(0)
        self._intvar = tk.IntVar()
        self._intvar.set(0)
        label = ttk.Label(self, text=self.name)
        self.input_entry = ttk.Entry(self, width=3, textvariable=self._stringvar)
        self.input_slider = ttk.Scale(self, from_=100, to_=0, length=250, variable=self._intvar, orient=tk.VERTICAL, command=self._slider_cb)

        self.input_entry.bind('<KeyPress-Return>', self._entry_cb)

        pad = {'padx': 10, 'pady': 10}
        label.grid(row=0, column=0, **pad)
        self.input_slider.grid(row=1, column=0, **pad)
        self.input_entry.grid(row=2, column=0, ipady=7, ipadx=7, **pad)

    def reset(self) -> None:
        self._intvar.set(0)
        self._stringvar.set('0')

    def _slider_cb(self, *_: any) -> None:
        value = self._intvar.get()
        self._stringvar.set(str(value))
        self.set_callback(self.motor, self._intvar.get())

    def _entry_cb(self, *_: any) -> None:
        value = int(self._stringvar.get())
        if value < 0:
            value = 0
        elif value > 100:
            value = 100
        self._intvar.set(value)
        self.set_callback(self.motor, value)


class ContentMotors(Content):
    def __init__(self, parent, asac: ASAC, info_popup: callable) -> None:
        super().__init__(parent, 'Motors')
        self.asac = asac
        self.info_popup = info_popup

        self._checked = tk.BooleanVar()
        self.check_enabled = ttk.Checkbutton(self.content, variable=self._checked, text='I understand that using these motor sliders can be dangerous')

        self.frame_sliders = ttk.Frame(self.content)

        self._sliders = []
        for i in range(1, 5):
            slider = MotorSlider(self.frame_sliders, i, self._set_callback)
            slider.pack(side=tk.LEFT, padx=20)
            self._sliders.append(slider)

        ttk.Button(self.frame_sliders, text='Set all to 0', command=self._reset_all).pack(side=tk.LEFT, anchor=tk.S, pady=10, padx=10)

        pad = {'pady': 20}
        self.check_enabled.pack(**pad)
        self.frame_sliders.pack(**pad)

        self._motor_throttle_request_flag = Event()
        self._motor_throttle_request_flag.clear()
        self._motor_throttle_request: Tuple[int, int] # [motor, throttle]
        Thread(target=self._motor_throttle_request_thread, daemon=True).start()

    def _reset_all(self) -> None:
        for slider in self._sliders:
            slider.reset()

    def _set_callback(self, motor: int, throttle: int):
        if not self._checked.get():
            self.info_popup('Uncheck safety box please!', bg='red')
            return

        if self.asac.is_connected():
            self._motor_throttle_request = motor, throttle
            self._motor_throttle_request_flag.set()
        else:
            self.info_popup('Not connected!', bg='red')

    def _motor_throttle_request_thread(self) -> None:
        while True:
            self._motor_throttle_request_flag.wait()
            motor, throttle = self._motor_throttle_request
            self._motor_throttle_request_flag.clear()
            self.asac.set_motor_throttle_test(motor, throttle)
            # Let's wait some time before we send another request
            time.sleep(.05)
