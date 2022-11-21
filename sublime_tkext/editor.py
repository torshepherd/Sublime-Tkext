import os
from tkinter.font import Font
from rich import print
import string
from tkinter import E, END, INSERT, TOP, PhotoImage, StringVar, Text
from tkinter.filedialog import asksaveasfilename
from tkinter.messagebox import askyesnocancel
from tkinter.ttk import Button, Entry, Frame, Notebook, Scrollbar
from typing import Any, Dict, List, Optional, Tuple, Union

from .highlight import PygmentsHighlighter, TagInfo, parse_style_string, parse_styles
from .lsp import ThreadedLsp
from .config import Settings
from .dropdown_menu import DropdownMenu
from .utils import Callback, StackOverflowText, TextLineNumbers, iter_except

# Popups:
# info_window.bind_all("<Leave>", lambda e: info_window.destroy())
# https://www.tutorialspoint.com/list-of-all-tkinter-events


class Document(Frame):
    def __init__(
        self,
        *args,
        tab_name: StringVar,
        settings: Settings,
        highlighter: PygmentsHighlighter,
        path: Optional[str] = None,
        theme: Optional[Dict[object, str]] = None,
        on_save: Optional[Callback] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._path = path
        self.settings = settings

        self.tab_name = tab_name
        self.on_save = on_save
        self.highlighter = highlighter

        self.hidden = False

        self.content = StackOverflowText(
            self,
            undo=True,
            wrap="none",
            font=(settings.editor_font_family, settings.editor_font_size),
            padx=20,
            pady=10,
            borderwidth=0,
        )
        # self.line_numbers = Text(
        #     self,
        #     width=4,
        #     takefocus=0,
        #     font=(settings.editor_font_family, settings.editor_font_size),
        #     padx=10,
        #     pady=10,
        #     borderwidth=0,
        # )
        # TODO: fix line numbers
        # self.line_numbers = TextLineNumbers(
        #     self,
        #     textwidget=self.content,
        #     width=8,
        #     takefocus=0,
        #     borderwidth=2,
        # )
        # self.old_line_count = 0
        self.scroll = Scrollbar(self)

        # def yview(*_):
        #     self.content.yview(*_)
        #     self.line_numbers.yview(*_)

        self.scroll.config(command=self.content.yview)
        self.content.configure(yscrollcommand=self.scroll.set)
        # self.line_numbers.configure(yscrollcommand=self.scroll.set)
        # self.content.bind(
        #     "<<Scroll>>",
        #     lambda e: self.line_numbers.yview_moveto(self.content.yview()[0]),
        # )
        self.autocomplete = DropdownMenu(
            self, on_choose=print, columns=("description",)
        )
        self.autocomplete.dropdown.column("description", anchor=E)

        self.find = StringVar()

        self.entry = Entry(self, width=48, textvariable=self.find)

        self.theme = theme
        if theme is not None:
            self.update_theme(theme)

        def open_dropdown(*_):
            # TODO: Send request to LSP here
            self.autocomplete.pack()
            self.autocomplete.set_choices(
                [
                    (("print", ""), print),
                    (("print_function", "__future__"), print),
                ]
            )

            pos = self.content.bbox("insert")
            if pos is not None:
                self.autocomplete.place(x=pos[0], y=pos[1] + pos[3], anchor="nw")
                self.content.up_down_disable()

        def close_dropdown(*_):
            self.autocomplete.place_forget()
            self.content.up_down_enable()

        def should_autocomplete():
            return not self.content.get("insert-1c") in string.whitespace

        def open_search(*_):
            print("open search")

        def on_text_deleted(*_):
            if should_autocomplete() and self.autocomplete.winfo_ismapped():
                open_dropdown()
            else:
                close_dropdown()

        def on_text_inserted(*_):
            if should_autocomplete():
                open_dropdown()
            else:
                close_dropdown()

        def on_text_modified(*_):
            self._mark_modified()
            self.highlighter.send_highlight_request(
                code=self.content.get("1.0", "end - 1c"), file_identifier=self.path
            )  # TODO: This line causes slowdown...
            # self.line_numbers.redraw()
            # new_line_count = int(self.content.index("end-1c").split(".")[0])
            # while self.old_line_count < new_line_count:
            #     self.line_numbers.insert("end", str(self.old_line_count + 1) + "\n")
            #     self.old_line_count += 1
            # while self.old_line_count > new_line_count:
            #     self.line_numbers.delete("end-2c", "end")
            #     self.old_line_count -= 1

        def on_move(*_):
            old_position = self.content.index("insert")

        self.content.bind("<<TextDeleted>>", on_text_deleted)
        self.content.bind("<<TextInserted>>", on_text_inserted)
        # self.content.bind("<<TextReplaced>>", on_text_replaced)
        self.content.bind("<<TextModified>>", on_text_modified)
        self.content.bind(
            "<<CursorMoved>>", close_dropdown
        )  # TODO: Up/Down should navigate through the dropdown, left right should sometimes close it
        # self.content.bind("<<Change>>", lambda *_: self.line_numbers.redraw())
        self.content.bind("<Control-space>", open_dropdown)
        # TODO: ctrl-f should open a search bar
        self.content.bind("<Control-f>", open_search)
        self.content.bind("<Escape>", close_dropdown)
        self.content.bind("<Control-s>", lambda *_: self.save())

        if path is not None:
            self.load(path)
        # TODO: bind ctrl-shift-s save as
        # TODO: Do multiple cursors using tags
        self.scroll.pack(side="right", fill="y")
        self.content.pack(side="right", fill="both", expand=True)
        # self.line_numbers.pack(side="right", fill="both", expand=True)

        super().pack(fill="both", expand=True)

    def _mark_modified(self):
        # TODO: this sometimes marks the wrong tab modified and renames the rightmost tab??
        self.tab_name.set(self.tab_name.get().rstrip(" *") + " *")

    def _mark_saved(self):
        self.tab_name.set(self.tab_name.get().rstrip(" *") + "  ")

    @property
    def path(self) -> Optional[str]:
        return self._path

    @path.setter
    def path(self, path: Optional[str]) -> None:
        self._path = path
        if path is not None:
            self.tab_name.set(os.path.basename(path))

    def load(self, path: Optional[str]):
        self.content.delete("1.0", "end")
        if path is not None:
            with open(path, "r") as f:
                self.content.insert("1.0", f.read())
        self.content.edit_modified(False)
        self._mark_saved()
        self.content.edit_reset()
        self.path = path

    def ask_then_save(self) -> bool:
        result = askyesnocancel(
            title="Sublime Tkext",
            message=f"Do you want to save the changes you made{' to ' + os.path.basename(self.path) if self.path is not None else ''}?",
        )
        if result is None:
            return False
        elif result is True:
            return self.save()
        return True

    def save(self) -> bool:
        if self.path is not None:
            try:
                f = open(self.path, "w")
                f.write(self.content.get("1.0", "end-1c"))
                self.content.edit_modified(False)
                self._mark_saved()
                f.close()
                if self.on_save is not None:
                    self.on_save()
                return True
            except Exception:
                return False
        else:
            return self.save_as()

    def save_as(self) -> bool:
        try:
            path = asksaveasfilename()
            if path != "":
                self.path = path
                return self.save()
        except Exception:
            ...
        return False

    def is_different_from_disk(self) -> bool:
        if self.path is None:
            return self.content.get("1.0", "end - 1c") != ""
        with open(self.path, "r") as f:
            return f.read() != self.content.get("1.0", "end - 1c")

    def update_settings(self, settings: "Settings"):
        self.settings = settings
        self.content.config(
            font=(settings.editor_font_family, settings.editor_font_size)
        )
        # self.line_numbers.config(
        #     font=(settings.editor_font_family, settings.editor_font_size)
        # )
        # self.line_numbers.update_textwidget(self.content)

    def update_theme(self, theme: Dict[object, str]):
        self.theme = theme
        flattened_theme = parse_styles(theme)  # type: ignore
        for k, v in flattened_theme.items():
            self.content.tag_config(
                k,
                foreground=v["foreground"],
                background=v["background"],
                font=Font(
                    family=self.settings.editor_font_family,
                    size=self.settings.editor_font_size,
                    weight="bold" if v["bold"] == True else "normal",
                    slant="italic" if v["italic"] == True else "roman",
                    underline=v["underline"] == True,
                ),
            )
        self.content.tag_config(
            "sel",
            background="#2f2f2f",
        )

    def update_tags(self, tags: List[TagInfo]):
        self.content.tag_delete(*self.content.tag_names()[1:])
        for tag in tags:
            self.content.tag_add(
                tag.tag, f"1.0 + {tag.start} chars", f"1.0 + {tag.end} chars"
            )
        if self.theme is not None:
            self.update_theme(self.theme)


class Editor(Notebook):
    def __init__(
        self,
        *args,
        settings: Settings,
        theme: Dict[object, str],
        lsp: ThreadedLsp,
        highlighter: PygmentsHighlighter,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.settings = settings
        self.theme = theme
        self.lsp = lsp
        self.highlighter = highlighter

        self.untitled_file_counter = 1

        # self.bind("<ButtonPress-2>", self._on_close_press, True)
        # self.bind("<ButtonRelease-2>", self._on_close_release)

        # def _on_close_press(self, event):
        #     if self.identify(event.x, event.y) == "label":
        #         print(event)

        self.poll_lsp_messages()

    def update_theme(self, theme: Dict[object, str]):
        self.theme = theme
        for t in self.tabs():
            self.nametowidget(t).update_theme(theme)

    def hide(self, tab_id) -> None:
        self.nametowidget(tab_id).hidden = True
        return super().hide(tab_id)

    def add(self, child, **kw) -> None:
        child.hidden = False
        return super().add(child, **kw)

    def focus_file(self, name: str):
        for t in self.tabs():
            if self.tab(t, "text") == name:
                self.select(t)
                self.nametowidget(t).content.focus_set()
                return

    def new_tab(self, path: Optional[str] = None, on_save: Optional[Callback] = None):
        tab_name_var = StringVar()

        if path is None:
            # New file
            tab_name_var.set(f"Untitled-{self.untitled_file_counter}  ")
            self.untitled_file_counter += 1

        else:
            # Open file
            tab_name_var.set(os.path.basename(path) + "  ")
            if not os.path.isfile(path):
                # print(f"{path} is not a file")
                return
            for i in self.tabs():
                current_tab = self.tab(i, option="text")
                if tab_name_var.get().rstrip(" *") == current_tab.rstrip(" *"):
                    self.focus_file(current_tab)
                    return

        current_doc = Document(
            self,
            path=path,
            theme=self.theme,
            tab_name=tab_name_var,
            on_save=on_save,
            settings=self.settings,
            highlighter=self.highlighter,
        )
        self.add(current_doc, text=tab_name_var.get())
        self.focus_file(tab_name_var.get())

        if path is not None:
            # textDocument/didOpen
            # textDocument/documentSymbol
            # textDocument/semanticTokens/full
            # textDocument/documentLink
            # textDocument/inlayHint
            ...

        tab_name_var.trace(
            "w",
            lambda *_: self.tab(len(self.tabs()) - 1, text=tab_name_var.get()),
        )

        # tip = Hovertip(root.nametowidget(self.select()), path, 1000)

    def close_tab(self, name: str, permanent: bool = False):
        for t in self.tabs():
            if t == name:
                if (
                    self.nametowidget(t).content.edit_modified()
                    and self.nametowidget(t).is_different_from_disk()
                ):
                    if self.nametowidget(t).ask_then_save():
                        self.forget(t) if permanent else self.hide(t)
                else:
                    self.forget(t) if permanent else self.hide(t)
                return self.nametowidget(t)

    def close_all(self, permanent: bool = False):
        for t in self.tabs():
            self.close_tab(t, permanent=permanent)

    def reopen_tab(self, widget):
        self.add(widget)
        widget.load(widget.path)
        self.focus_file(widget.tab_name.get())

    def ensure_all_saved(self):
        successes = []
        for t in self.tabs():
            if (
                self.nametowidget(t).content.edit_modified()
                and self.nametowidget(t).is_different_from_disk()
            ):
                self.focus_file(self.tab(t, "text"))
                successes.append(self.nametowidget(t).ask_then_save())
        return all(successes)

    def get_state(self) -> list[str]:
        return [
            self.nametowidget(t).path
            for t in self.tabs()
            if not self.nametowidget(t).hidden
        ]

    def try_goto(self, row: int | None, col: int | None):
        if len(self.tabs()) > 0 and row is not None:
            if col is not None:
                self.nametowidget(self.select()).content.mark_set(
                    "insert", f"{row}.{col - 1}"
                )
            else:
                self.nametowidget(self.select()).content.mark_set("insert", f"{row}.0")
            self.focus_file(self.tab(self.select(), "text"))

    def update_settings(self, settings: "Settings"):
        print("Updating editor settings")
        for t in self.tabs():
            self.nametowidget(t).update_settings(settings)

    def get_tab_by_path(self, path: str) -> Optional[Document]:
        for t in self.tabs():
            if self.nametowidget(t).path == path:
                return self.nametowidget(t)
        return None

    def poll_lsp_messages(self):
        # TODO: Maybe the editor class should handle this instead? Since get removes from the queue
        """Update GUI with items from the queue."""
        # print("Polling LSP messages")
        rsp = self.lsp.get_response()
        # TODO: Delegate to a tab, call a tab's method to handle this depending on type of message
        # if rsp is not None:
        #     print(rsp)

        highlight_rsp = self.highlighter.get_response()

        if highlight_rsp is not None:
            if (
                meant_for_tab := self.get_tab_by_path(highlight_rsp.file_id)
            ) is not None:
                meant_for_tab.update_tags(highlight_rsp.tokens)

        self.after(40, self.poll_lsp_messages)  # schedule next update
