__version__ = "0.2.0"

# TODO: add refresh function to refresh based on settings change and another for window refresh

import os
from tkinter import (
    BOTH,
    CENTER,
    HORIZONTAL,
    INSERT,
    LEFT,
    NONE,
    RIGHT,
    VERTICAL,
    E,
    StringVar,
    Tk,
    W,
)
from tkinter.filedialog import askdirectory, askopenfilenames
from tkinter.ttk import (
    Button,
    Frame,
    PanedWindow,
    Style,
)
from typing import Dict, Optional, Tuple
from pathlib import Path

import click
from pygments.styles import get_all_styles, get_style_by_name
from sv_ttk import set_theme

from .highlight import PygmentsHighlighter
from .lsp import ThreadedLsp
from .dropdown_menu import CommandPalette, DropdownMenu
from .editor import Editor
from .file_explorer import Explorer
from .utils import iter_except, set_title_bar_color
from .config import Settings, EditorSavedState, Config, WindowConfig, WorkspaceConfig

VERBOSITY = False


@click.command()
@click.version_option(version=__version__)
@click.argument("path", type=click.Path(exists=True, dir_okay=True), required=False)
def main(path: Optional[str]) -> None:
    last_state = Config("workspace.json", EditorSavedState).load()
    settings = Config("settings.json", Settings).load()
    color_theme = get_style_by_name("default").styles
    closed_file_path_buffer = []

    # TODO: remove these two variables
    editing_path = Path(os.getcwd() if path is None else path).resolve()

    root = Tk()

    root.unbind_all("<Tab>")
    # root.unbind_all("<Control-O>")
    root.unbind_all("<<NextWindow>>")
    root.unbind_all("<<PrevWindow>>")

    # TODO: Break this whole block out to a function or class
    lsp = ThreadedLsp(["pylsp"])  # , "-v"])
    highlighter = PygmentsHighlighter()

    # TODO: set this on open workspace
    root.title(f"Sublime Tkext {__version__} {editing_path}")
    root.geometry(last_state.data.window_config.to_tkinter_form())
    if last_state.data.window_config.zoomed:
        root.state("zoomed")

    app = PanedWindow(root, orient=HORIZONTAL)
    editor = PanedWindow(app, orient=VERTICAL)

    workspace = Frame(editor, padding=10)
    # terminal = Frame(editor, padding=10)

    notebook = Editor(
        workspace,
        settings=settings.data,
        theme=color_theme,  # type: ignore
        lsp=lsp,
        highlighter=highlighter,
    )
    tree = Explorer(
        app,
        on_select=notebook.new_tab,
    )

    editor.add(workspace, weight=3)
    # editor.add(terminal, weight=1)

    app.add(tree, weight=0)
    app.add(editor, weight=3)

    notebook.pack(fill=BOTH, expand=True)

    def reload_settings(*_):
        print("Reloading settings...")
        settings.load()
        style = Style(root)
        if settings.data.workbench_ui_theme == "dark":
            set_title_bar_color(root, True)
            try:
                set_theme("dark")
            except Exception as e:
                print(e)
        elif settings.data.workbench_ui_theme == "light":
            set_title_bar_color(root, False)
            try:
                set_theme("light")
            except Exception as e:
                print(e)
        try:
            color_theme = get_style_by_name(settings.data.editor_color_theme).styles
            notebook.update_theme(color_theme)  # type: ignore
        except Exception as e:
            print(e)
            color_theme = get_style_by_name("default").styles
            notebook.update_theme(color_theme)  # type: ignore
        style.configure("TMenubutton.Option", font=("Segoe UI", 36))
        # style.configure("lefttab.TNotebook", tabposition="wn")
        # style.configure("lefttab.TNotebook.Tab", width=3)
        # style.configure("lefttab.TNotebook.Tab", height=300)
        # style.configure("lefttab.TNotebook.Tab", font=("Segoe UI", 18))

        notebook.update_settings(settings.data)

    reload_settings()

    def close_palette(*_):
        app.tkraise()
        # TODO: Focus editor here

    def open_settings(*_):
        # TODO: test this on multiple platforms/ installs
        notebook.new_tab(settings.path_to_config.as_posix(), on_save=reload_settings)

    def parse_goto_line_and_char(loc: Tuple[str]) -> tuple[int | None, int | None]:
        line, char = loc[0].split(":")
        line = line.lstrip("Line ")
        char = char.lstrip("character ")

        if line == "_":
            return None, None
        elif char == "_":
            return int(line), None
        return int(line), int(char)

    command_frame = CommandPalette(
        on_choose_file=lambda p: notebook.new_tab(p[1]),
        on_choose_location=lambda loc: notebook.try_goto(
            *parse_goto_line_and_char(loc)
        ),
        on_close=close_palette,
        available_commands=[
            (("Actions: Format Document", "Shift + Alt + F"), print),
            (("Preferences: Open Settings (JSON)", ""), open_settings),
        ],
    )

    def open_from_dialog(*_):
        for fname in askopenfilenames(initialdir=editing_path):
            notebook.new_tab(fname)
            last_state.data.recent_file_paths.add(fname)

    def open_dir(path: str):
        if os.path.isdir(path):
            tree.set_directory(path)
            command_frame.set_available_file_dir(path)
            last_state.data.recent_folder_paths.add(path)

            if path in last_state.data.workspaces.keys():
                workspace_config = last_state.data.workspaces[path]
                if notebook.ensure_all_saved():
                    notebook.close_all(permanent=True)
                    for fname in workspace_config.tab_paths:
                        notebook.new_tab(
                            fname,
                            on_save=reload_settings
                            if fname == settings.path_to_config.as_posix()
                            else None,
                        )

    def open_dir_from_dialog(*_):
        open_dir(askdirectory(initialdir=editing_path))

    if path:
        open_dir(editing_path.as_posix())

    app.pack(fill=BOTH, expand=True)

    def collapse_explorer(*_):
        if len(app.panes()) == 1:
            app.remove(editor)
            app.add(tree, weight=0)
            app.add(editor, weight=3)
        else:
            app.remove(tree)

    # def collapse_terminal(*_):
    #     if len(editor.panes()) == 1:
    #         editor.add(terminal, weight=1)
    #     else:
    #         editor.remove(terminal)

    def update_window_state(_):
        if root.state() == "zoomed":
            last_state.data.window_config.zoomed = True
        else:
            last_state.data.window_config = WindowConfig.from_tkinter_form(
                root.geometry()
            )
        last_state.save()

    def close_tab(*_):
        tab_closed = notebook.close_tab(notebook.select())
        if tab_closed is not None:
            closed_file_path_buffer.append(tab_closed)

    def reopen_tab(*_):
        if len(closed_file_path_buffer) > 0:
            notebook.reopen_tab(closed_file_path_buffer.pop())

    command_frame.place(relx=0.5, rely=0, anchor="n", width=600)
    app.tkraise()

    root.bind("<Control-p>", lambda *_: command_frame.open())
    root.bind("<Control-P>", lambda *_: command_frame.open(prefix=">"))
    root.bind("<Control-g>", lambda *_: command_frame.open(prefix=":"))

    root.bind("<Control-o>", open_from_dialog)
    root.bind("<Control-N>", open_dir_from_dialog)
    root.bind("<Control-n>", lambda *_: notebook.new_tab())
    root.bind("<Control-w>", close_tab)
    root.bind("<Control-T>", reopen_tab)
    root.bind("<Control-b>", collapse_explorer)
    # root.bind("<Control-`>", collapse_terminal)
    root.bind("<Configure>", update_window_state)

    def update_open_files(*_):
        last_state.data.workspaces[editing_path.as_posix()] = WorkspaceConfig(
            tab_paths=notebook.get_state()
        )
        last_state.save()

    def on_close(*_):
        update_open_files()
        if notebook.ensure_all_saved():
            lsp.process.kill()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
