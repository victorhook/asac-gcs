from content.content import Content
from tkinter import ttk


class ContentVTX(Content):
    def __init__(self, parent) -> None:
        super().__init__(parent, 'VTX')

        self.input_enabled = ttk.Checkbutton(self.content, text='VTX Enabled')
        self.input_enabled.grid()
