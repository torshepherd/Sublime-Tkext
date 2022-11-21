import os
from pathlib import Path
import re
from tkinter import E, INSERT, StringVar
from tkinter.ttk import Entry, Frame, Scrollbar, Treeview
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, TypeVar

from .utils import Callback, build_query


MAX_ITEMS = 11


class DropdownMenu(Frame):
    def __init__(
        self,
        *args,
        columns: Tuple[str, ...],
        on_choose: Optional[Callback] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.dropdown = Treeview(
            self,
            height=MAX_ITEMS,
            selectmode="browse",
            show="tree",
            columns=columns,
        )
        self.scroll = Scrollbar(self)
        self.scroll.config(command=self.dropdown.yview)
        # self.scroll.pack(side="right", fill="y")
        # self.dropdown.pack(expand=True, fill="both")
        self.dropdown.configure(yscrollcommand=self.scroll.set)
        self.callbacks: Dict[str, Callback] = {}

        self.dropdown.bind(
            "<<TreeviewOpen>>",
            self._on_choose_wrapper,
        )

        self.on_choose = on_choose

    def _on_choose_wrapper(self, *_):
        selected_text = self.dropdown.item(current := self.dropdown.focus(), "text")
        selected_values = self.dropdown.item(current, "values")

        if selected_text in self.callbacks.keys():
            self.callbacks[selected_text]((selected_text, *selected_values))

        self.dropdown.delete(*self.dropdown.get_children(current))  # type: ignore

        if self.on_choose is not None:
            self.on_choose()

    def set_choices(
        self,
        choices: List[Tuple[Tuple[str, ...], Callback]],
        filter_query: Optional[str] = None,
    ):
        if filter_query is not None:
            filter = re.compile(build_query(filter_query, ".*"))
            choices = list(cmd for cmd in choices if filter.match(cmd[0][0]))

        self.dropdown.delete(*self.dropdown.get_children())
        for choice, callback in choices:
            self.dropdown.insert(
                self.dropdown.insert(
                    "",
                    "end",
                    text=choice[0],
                    values=choice[1:] if len(choice) > 1 else [],
                    open=False,
                ),
                "end",
            )
            self.callbacks[choice[0]] = callback
        self.dropdown.configure(height=min(len(choices), MAX_ITEMS))

    def pack(self, *args, **kwargs):
        super().pack(*args, **kwargs)
        self.scroll.pack(side="right", fill="y")
        self.dropdown.pack(expand=True, fill="both")


class CommandPalette(DropdownMenu):
    def __init__(
        self,
        *args,
        on_close: Callback,
        on_choose_file: Callback,
        on_choose_location: Callback,
        available_commands: List[Tuple[Tuple[str, ...], Callback]],
        **kwargs,
    ):
        super().__init__(*args, on_choose=on_close, **kwargs, columns=("keybinds",))

        self.available_commands = available_commands
        self.available_file_dir = None

        self.command = StringVar()

        self.entry = Entry(self, width=48, textvariable=self.command)
        self.entry.pack(expand=True, fill="both")
        super().pack()

        def on_up(*_):
            up_one = self.dropdown.prev(self.dropdown.focus())
            tabs = self.dropdown.get_children()
            if len(tabs) > 0:
                self.dropdown.focus(up_one if up_one != "" else tabs[-1])
            self.dropdown.selection_set(self.dropdown.focus())

        def on_down(*_):
            down_one = self.dropdown.next(self.dropdown.focus())
            tabs = self.dropdown.get_children()
            if len(tabs) > 0:
                self.dropdown.focus(down_one if down_one != "" else tabs[0])
            self.dropdown.selection_set(self.dropdown.focus())

        def on_filter_change(*_):
            if len(self.command.get()) > 0:
                # Filter list of commands
                if self.command.get()[0] == ">":
                    filter = re.compile(build_query(self.command.get()[1:], ".*"))
                    self.set_choices(
                        list(
                            cmd
                            for cmd in self.available_commands
                            if filter.match(cmd[0][0])
                        )
                    )
                    self._select_first()
                    return
                # TODO: Line number
                elif self.command.get()[0] == ":":
                    query = self.command.get().split(":")
                    l, c = "_", "_"
                    if len(query) > 1 and query[1].isdigit() and int(query[1]) != 0:
                        l = f"{query[1]}"
                    if len(query) > 2 and query[2].isdigit() and int(query[2]) != 0:
                        c = f"{query[2]}"
                    self.set_choices(
                        [((f"Line {l}: character {c}",), on_choose_location)]
                    )
                    self._select_first()
                    return
            # Filter list of files in workspace
            if self.available_file_dir is not None:
                self.set_choices(
                    list(
                        (
                            (
                                os.path.basename(f.resolve()),
                                f.resolve()
                                .relative_to(self.available_file_dir)
                                .as_posix(),
                            ),
                            on_choose_file,
                        )
                        for f in self.available_file_dir.rglob(
                            build_query(self.command.get())
                        )
                        if f.is_file()
                    )
                )
                self._select_first()
            return

        self.entry.bind(
            "<Return>",
            self._on_choose_wrapper,
        )
        self.dropdown.bind("<FocusIn>", lambda *_: self.entry.focus_set())
        self.bind("<FocusOut>", on_close)
        self.entry.bind("<Escape>", on_close)
        self.entry.bind("<Up>", on_up)
        self.entry.bind("<Down>", on_down)
        self.command.trace("w", on_filter_change)

        self.dropdown.column("#0", width=300)
        self.dropdown.column("keybinds", anchor=E)

    def _select_first(self):
        tabs = self.dropdown.get_children()
        if len(tabs) > 0:
            self.dropdown.focus(tabs[0])
        self.dropdown.selection_set(self.dropdown.focus())

    def open(self, prefix=""):
        self.tkraise()
        self.command.set(prefix)
        self.entry.icursor(self.entry.index(INSERT) + 1)
        self.entry.focus_set()
        self._select_first()

    def add_available_command(self, command: Tuple[Tuple[str, ...], Callback]):
        self.available_commands.append(command)

    def set_available_file_dir(self, file_dir: str):
        self.available_file_dir = Path(file_dir).resolve()
