import tkinter as tk
from tkinter import ttk
import utils


class Content(ttk.Frame):

    def __init__(self, parent, title: str) -> None:
        super().__init__(parent)
        title = ttk.Label(self, text=title)
        title.config(font=('Courier', 20))
        title.pack()
        self.content = ttk.Frame(self)
        self.content.pack()
        self.name = title
        self.logger = utils.get_logger()


class ParamFloat:

    def __init__(self, parent, row: int, name: str, value: float,
                 readonly: bool = False, decimals: int = 4) -> None:
        self._decimals = decimals
        if readonly:
            state = 'readonly'
        else:
            state = 'normal'
        pack = {'padx': 5, 'pady': 5, 'sticky': tk.W}
        ttk.Label(parent, text=name).grid(row=row, column=0, **pack)
        self._entry = ttk.Entry(parent, state=state)
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