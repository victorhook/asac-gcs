from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from threading import Thread
import time


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

    def __init__(self, parent, row: int, name: str, value: float) -> None:
        pack = {'padx': 5, 'pady': 5, 'sticky': tk.W}
        tk.Label(parent, text=name, **label_style).grid(row=row, column=0, **pack)
        self._entry = tk.Entry(parent, **entry_style)
        self._entry.grid(row=row, column=1, **pack)
        self.set(value)

    def get(self) -> float:
        return float(self._entry.get())

    def set(self, value: float) -> None:
        self._entry.delete(0, tk.END)
        self._entry.insert(tk.END, value)

class Content(tk.Frame):

    def __init__(self, parent, title: str) -> None:
        super().__init__(parent, **frame_style)
        title = tk.Label(self, text=title, **label_style)
        title.config(font=('Courier', 20))
        title.pack()
        self.content = tk.Frame(self, **frame_style)
        self.content.pack()
        self.name = title

class ContentGeneral(Content):
    def __init__(self, parent, save_callback: callable) -> None:
        super().__init__(parent, 'General')
        pack = {'padx': 10, 'pady': 10}

        tk.Label(self.content, text='Craft name', **label_style).grid(row=0, column=0, **pack)
        tk.Label(self.content, text='Rotation X', **label_style).grid(row=1, column=0, **pack)
        tk.Label(self.content, text='Rotation Y', **label_style).grid(row=2, column=0, **pack)
        tk.Label(self.content, text='Rotation Z', **label_style).grid(row=3, column=0, **pack)
        tk.Label(self.content, text='ESC Protocol', **label_style).grid(row=4, column=0, **pack)

        self.input_craft_name = tk.Entry(self.content, **entry_style)
        self.input_rotation_x = tk.Entry(self.content, **entry_style)
        self.input_rotation_y = tk.Entry(self.content, **entry_style)
        self.input_rotation_z = tk.Entry(self.content, **entry_style)
        self.input_esc_protocol = ttk.Combobox(self.content)

        self.input_craft_name.grid(row=0, column=1, **pack)
        self.input_rotation_x.grid(row=1, column=1, **pack)
        self.input_rotation_y.grid(row=2, column=1, **pack)
        self.input_rotation_z.grid(row=3, column=1, **pack)
        self.input_esc_protocol.grid(row=4, column=1, **pack)

        btn_save = tk.Button(self.content, text='Save', **btn_style, command=save_callback)
        btn_save.grid(row=5, columnspan=2)

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
        self.combo_serial_port = ttk.Combobox(self.frame_ctrl)
        self.btn_connect = tk.Button(self.frame_ctrl, text='Connect', **btn_style)
        self.label_image_connected = tk.Label(self.frame_ctrl, **label_style)

        title.pack(side=tk.LEFT, **ctrl_pack_kw)
        self.label_image_connected.pack(side=tk.RIGHT, **ctrl_pack_kw)
        self.btn_connect.pack(side=tk.RIGHT, **ctrl_pack_kw)
        self.combo_serial_port.pack(side=tk.RIGHT, **ctrl_pack_kw)
        serial_port.pack(side=tk.RIGHT, **ctrl_pack_kw)

        # -- Main content -- #
        self.contents = {
            'general': ContentGeneral(self.frame_content, self.general_save),
            'pid': ContentPid(self.frame_content, self.pid_save),
            'motors': ContentMotors(self.frame_content),
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
        self.active_content: str = 'pid'

        # Update UI state once before we start
        self._update_state()

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
        return False

    def set_content(self, new_content_name: str) -> None:
        if new_content_name != self.active_content:
            self.active_content = new_content_name

        self._update_state()

    def _update_state(self) -> None:
        if self.is_connected():
            self.label_image_connected.config(image=self.img_btn_connected)
        else:
            self.label_image_connected.config(image=self.img_btn_disconnected)

        for content in self.contents.values():
            content: Content
            content.pack_forget()

        self.contents[self.active_content].pack(fill=tk.BOTH, expand=True)


if __name__ == '__main__':
    gui = Gui()
    gui.mainloop()