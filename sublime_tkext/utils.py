# /---- Evil hack to make the title bar dark (https://stackoverflow.com/a/70724666) ----\

import ctypes as ct
import json
from pathlib import Path
from queue import Queue
from re import compile
from string import ascii_letters
from subprocess import PIPE, Popen
from threading import Thread
from tkinter import END, INSERT, RIGHT, Canvas, Text
from tkinter.ttk import Scrollbar
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union
from platform import system

from pylsp_jsonrpc import streams


class Callback(Protocol):
    def __call__(self, *args: Any) -> None:
        ...


def set_title_bar_color(window, dark: bool):
    """
    MORE INFO:
    https://docs.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute
    """
    if system() == "Windows":
        window.update()
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        set_window_attribute = ct.windll.dwmapi.DwmSetWindowAttribute
        get_parent = ct.windll.user32.GetParent
        hwnd = get_parent(window.winfo_id())
        rendering_policy = DWMWA_USE_IMMERSIVE_DARK_MODE
        value = 2 if dark else 0
        value = ct.c_int(value)
        set_window_attribute(hwnd, rendering_policy, ct.byref(value), ct.sizeof(value))


# From: https://stackoverflow.com/questions/665566/redirect-command-line-results-to-a-tkinter-gui
def iter_except(function, exception):
    """Works like builtin 2-argument `iter()`, but stops on `exception`."""
    try:
        while True:
            yield function()
    except exception:
        return


# From: https://stackoverflow.com/questions/16369470/tkinter-adding-line-number-to-text-widget
class TextLineNumbers(Canvas):
    def __init__(self, *args, textwidget: "StackOverflowText", **kwargs):
        Canvas.__init__(self, *args, **kwargs)
        self.textwidget = textwidget

    def update_textwidget(self, textwidget):
        self.textwidget = textwidget

    def redraw(self, *args):
        """redraw line numbers"""
        self.delete("all")

        i = self.textwidget.index("@0,0")
        while True:
            dline = self.textwidget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            # print(self.textwidget.configure())
            self.create_text(
                4,
                y,
                anchor="nw",
                text=linenum,
                font=self.textwidget.cget("font"),
                justify=RIGHT,
            )
            i = self.textwidget.index("%s+1line" % i)


class ReportingBar(Scrollbar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # create a proxy for the underlying widget
        self._orig = self._w + "_orig"  # type: ignore
        self.tk.call("rename", self._w, self._orig)  # type: ignore
        self.tk.createcommand(self._w, self._proxy)  # type: ignore

    def _proxy(self, command, *args):
        cmd = (self._orig, command) + args
        print("Scrollbar command:", cmd)
        result = self.tk.call(cmd)
        return result


# From: https://stackoverflow.com/a/40618152/11106801
class StackOverflowText(Text):
    def __init__(self, *args, **kwargs):
        """A text widget that report on internal widget commands"""
        Text.__init__(self, *args, **kwargs)

        # create a proxy for the underlying widget
        self._orig = self._w + "_orig"  # type: ignore
        self.tk.call("rename", self._w, self._orig)  # type: ignore
        self.tk.createcommand(self._w, self._proxy)  # type: ignore

        self.bind("<Control-BackSpace>", self.ctrl_backspace)
        self.bind("<Control-Delete>", self.ctrl_delete)

        self.up_down_enabled = True

    def _proxy(self, command, *args):
        mark_set = command == "mark" and args[0] == "set" and args[1] == "insert"
        # if mark_set:
        #     print("mark set", args)
        #     # TODO: add in old position to data here
        #     old_row, old_col = (int(i) for i in self.index(INSERT).split("."))
        #     if not args[2].startswith("end"):
        #         # TODO: This is broken (ValueError: invalid literal for int() with base 10: 'insert-1displayindices')
        #         row, col = (int(i) for i in args[2].split("."))
        #         if row != old_row:
        #             ...
        #         if abs(col - old_col) == 1:
        #             print("left/right")

        cmd = (self._orig, command) + args
        # print("calling the command:", cmd)
        try:
            result = self.tk.call(cmd)
        except Exception as e:
            print("proxy object had exception:", e)
            result = None

        if command in ("insert", "delete", "replace"):
            self.event_generate("<<TextModified>>")

        if command == "insert":
            self.event_generate("<<TextInserted>>")
        elif command == "delete":
            self.event_generate("<<TextDeleted>>")
        elif command == "replace":
            self.event_generate("<<TextReplaced>>")

        if mark_set:
            self.event_generate("<<CursorMoved>>")

        return result

    def up_down_enable(self):
        self.up_down_enabled = True
        # TODO: remove the up/down bindings when dropdown is open

    def up_down_disable(self):
        self.up_down_enabled = False
        # TODO: remove the up/down bindings when dropdown is open

    # https://stackoverflow.com/questions/23376594/tkinter-options-besides-similar-to-but-besides-insert-1c
    def ctrl_delete(self, *_):
        insert = self.get(INSERT)
        if insert in "  " and insert != "":
            while insert in "  " and insert != "":
                self.delete(INSERT)
                insert = self.get("insert+1c")
        elif insert not in "\n\t  .?!,@#…¿/\\\"'—–":
            while insert not in "\n\t  .?!,@#…¿/\\\"'—–":
                self.delete(INSERT)
                insert = self.get("insert+1c")
        else:
            if insert in "\n\t" and insert != "":
                if self.get(INSERT, END).strip() == "" and self.index(
                    INSERT
                ) != self.index(END):
                    self.delete(INSERT, END)
                else:
                    while insert in "\n\t  " and insert != "":
                        self.delete(INSERT)
                        insert = self.get("insert+1c")
            else:
                self.delete(INSERT)

    # https://stackoverflow.com/questions/23376594/tkinter-options-besides-similar-to-but-besides-insert-1c
    def ctrl_backspace(self, *_):
        if self.index("insert-1c") != "1.0" and self.index(INSERT) != "1.0":
            if self.index("insert wordstart-1c") == "1.0":
                i = 0
                while self.index(INSERT) != "1.0" and i < 25:
                    self.delete("insert-1c")
                    i += 1
            else:
                insertm1c = self.get("insert-1c")
                if insertm1c in "\n\t.?!,@#…¿/\\\"'—–" and insertm1c != "":
                    insertm1c = self.get("insert-2c")
                    i = 0
                    while (
                        insertm1c in "\n\t.?!,@#…¿/\\\"'—–" and insertm1c != ""
                    ) and i < 25:
                        self.delete("insert-1c")
                        insertm1c = self.get("insert-2c")
                        i += 1
                else:
                    while insertm1c not in "\n\t  .?!,@#…¿/\\\"'—–" and insertm1c != "":
                        self.delete("insert-1c")
                        insertm1c = self.get("insert-2c")
                    while insertm1c in "  " and insertm1c != "":
                        self.delete("insert-1c")
                        insertm1c = self.get("insert-2c")


def build_query(query_string, wildcard="*"):
    return wildcard + "".join(
        f"[{q.lower()}{q.upper()}]{wildcard}"
        if q in ascii_letters
        else f"[{q}]{wildcard}"
        for q in query_string
    )


def get_path_to_configs():
    # if system() == "Windows":
    #     return os.path.join(os.environ["AppData"], "SublimeTkext", self.filename)
    # # TODO: Mac and Linux
    # return os.path.join(
    #     os.environ["HOME"], ".config", "SublimeTkext", self.filename
    # )
    return Path(__file__).parent / "config"


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


class JsonRpcProcessProxy:
    def __init__(self, cmd: List[str]) -> None:
        self.request_id = 0

        self.process = Popen(
            cmd,
            stdin=PIPE,
            stdout=PIPE,
        )

        self.rsp_queue: Queue[Dict] = Queue(maxsize=1024)
        self.writer = streams.JsonRpcStreamWriter(self.process.stdin)
        self.reader = streams.JsonRpcStreamReader(self.process.stdout)

        self.thread = Thread(target=lambda: self.reader.listen(self.read), daemon=True)
        self.thread.start()

    def _generate_request_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def read(self, msg: Dict):
        self.rsp_queue.put(msg)

    def send(
        self,
        method: str,
        params: Optional[Union[Dict, List]] = None,
    ):
        self.writer.write(
            {
                "jsonrpc": "2.0",
                "id": (out := self._generate_request_id()),
                "method": method,
                "params": params,
            }
        )
        return out

    def exit(self):
        self.process.kill()
        self.writer.close()
        self.reader.close()
