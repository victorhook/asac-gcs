from content.content import Content
from tkinter import ttk
import tkinter as tk
from asac import ASAC
import utils

from pymavlink.dialects.v10 import common


RX_PROTOCOLS = ['ibus', 'elrs']


class ProgressBar(tk.Canvas):

    BACKGROUND = '#aaaaaa'
    FILL = '#00aa00'

    def __init__(self, parent) -> None:
        self.w = 250
        self.h = 20
        super().__init__(parent, width=self.w, height=self.h, bg=self.BACKGROUND)
        self.fill = self.create_rectangle(0, 0, self.w, self.h, fill=self.FILL)
        self.text = self.create_text(self.w//2, self.h//2, text='')
        self.set(1500)

    def set(self, value: int) -> None:
        perc = (value - 1000) / 1000
        self.coords(self.fill, 0, 0, self.w * perc, self.h)
        self.itemconfig(self.text, text=f'{int(perc*100)} %')


class RxChannel:

    def __init__(self, parent, channel: int):
        self._text_var = tk.StringVar()
        self._text_var.set(500)

        label = ttk.Label(parent, text=f'Channel {channel}', justify=tk.LEFT)
        label_value = ttk.Label(parent, textvariable=self._text_var)
        self.progress_bar = ProgressBar(parent)

        pad = {'padx': 10, 'pady': 1, 'sticky': tk.W}
        label.grid(row=channel, column=0, **pad)
        self.progress_bar.grid(row=channel, column=1, **pad)
        label_value.grid(row=channel, column=2, **pad)

    def set(self, value: int) -> None:
        '''
        value: RX channel value, between 1000 and 2000
        '''
        self.progress_bar.set(value)
        self._text_var.set(str(value))


class ContentRx(Content):
    def __init__(self, parent, asac: ASAC) -> None:
        super().__init__(parent, 'RX')
        asac.add_message_handler(common.MAVLink_rc_channels_message, self._new_data)

        self.frame_channels = ttk.Frame(self.content)

        self.channels = {ch: RxChannel(self.frame_channels, ch ) for ch in range(1, 17)}

        # Config
        self.frame_config = ttk.Frame(self.content)
        pad = {'padx': 10, 'pady': 10}
        ttk.Label(self.frame_config, text='RX Protocol').grid(row=0, column=0, **pad)
        ttk.Combobox(self.frame_config, values=RX_PROTOCOLS).grid(row=0, column=1, **pad)

        self.frame_channels.grid(row=0, column=0, sticky=tk.N)
        self.frame_config.grid(row=0, column=1, sticky=tk.N)

    def _new_data(self, msg: common.MAVLink_rc_channels_message) -> None:
        for ch, ui_ch in self.channels.items():
            attr_name = f'chan{ch}_raw'
            ch_value = getattr(msg, attr_name)
            ui_ch.set(ch_value)
