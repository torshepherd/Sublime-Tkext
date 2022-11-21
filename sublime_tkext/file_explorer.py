import os
import string
from tkinter import Event
from tkinter.ttk import Frame, Scrollbar, Treeview
from typing import Any, Callable, Optional
from pathlib import Path

# Based on https://stackoverflow.com/questions/16746387/display-directory-content-with-tkinter-treeview-widget
class Explorer(Frame):
    def __init__(
        self, *args, on_select: Optional[Callable[[str], Any]] = None, **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.scroll = Scrollbar(self)
        self.scroll.pack(side="right", fill="y")
        self.file_tree = Treeview(
            self,
            height=11,
            selectmode="browse",
            show=("tree",),
            yscrollcommand=self.scroll.set,
        )
        self.scroll.config(command=self.file_tree.yview)
        self.file_tree.bind("<<TreeviewOpen>>", self.open_node)
        self.file_tree.pack(expand=True, fill="both")

        self.nodes = dict()

        if on_select is not None:

            def wrapper(_):
                current = self.file_tree.focus()
                running_path = self.file_tree.item(current, "text")
                name = running_path
                while True:
                    current = self.file_tree.parent(current)
                    if current == "":
                        break
                    running_path = os.path.join(
                        self.file_tree.item(current, "text"), running_path
                    )
                on_select(running_path)

            self.file_tree.bind(
                "<<TreeviewSelect>>",
                wrapper,
            )

    def insert_node(self, parent, text, abspath):
        node = self.file_tree.insert(parent, "end", text=text, open=False)
        if os.path.isdir(abspath):
            self.nodes[node] = abspath
            self.file_tree.insert(node, "end")

    def open_node(self, _):
        node = self.file_tree.focus()
        abspath = self.nodes.pop(node, None)
        if abspath:
            self.file_tree.delete(self.file_tree.get_children(node))  # type: ignore

            all_subnodes = os.listdir(abspath)
            only_folders = [
                x for x in all_subnodes if os.path.isdir(os.path.join(abspath, x))
            ]
            only_files = [
                x for x in all_subnodes if not os.path.isdir(os.path.join(abspath, x))
            ]
            for p in (*only_folders, *only_files):
                self.insert_node(node, p, os.path.join(abspath, p))

    def set_directory(self, path: str):
        expanded_path = Path(path).resolve()
        self.insert_node("", expanded_path, expanded_path)
        self.toplevel_dir = expanded_path


# Based on https://stackoverflow.com/questions/16746387/display-directory-content-with-tkinter-treeview-widget
# def explorer(
#     parent_widget,
#     abspath=".",
#     on_select: Optional[Callable[[str], Any]] = None,
# ) -> Treeview:
#     file_explorer_scrollbar = Scrollbar(parent_widget)
#     file_explorer_scrollbar.pack(side="right", fill="y")
#     file_tree = Treeview(
#         parent_widget,
#         height=11,
#         selectmode="browse",
#         show=("tree",),
#         yscrollcommand=file_explorer_scrollbar.set,
#     )
#     file_explorer_scrollbar.config(command=file_tree.yview)
#     file_tree.pack(expand=True, fill="both")

#     nodes = dict()

#     def insert_node(parent, text, abspath):
#         node = file_tree.insert(parent, "end", text=text, open=False)
#         if os.path.isdir(abspath):
#             nodes[node] = abspath
#             file_tree.insert(node, "end")

#     def open_node(event):
#         node = file_tree.focus()
#         abspath = nodes.pop(node, None)
#         if abspath:
#             file_tree.delete(file_tree.get_children(node))  # type: ignore

#             all_subnodes = os.listdir(abspath)
#             only_folders = [
#                 x for x in all_subnodes if os.path.isdir(os.path.join(abspath, x))
#             ]
#             only_files = [
#                 x for x in all_subnodes if not os.path.isdir(os.path.join(abspath, x))
#             ]
#             for p in (*only_folders, *only_files):
#                 insert_node(node, p, os.path.join(abspath, p))

#     insert_node("", abspath, abspath)
#     file_tree.bind("<<TreeviewOpen>>", open_node)

#     # file_tree.see
#     # file_tree.selection_set(10)

#     if on_select is not None:

#         def wrapper(_):
#             current = file_tree.focus()
#             running_path = file_tree.item(current, "text")
#             name = running_path
#             while True:
#                 current = file_tree.parent(current)
#                 if current == "":
#                     break
#                 running_path = os.path.join(
#                     file_tree.item(current, "text"), running_path
#                 )
#             on_select(running_path)

#         file_tree.bind(
#             "<<TreeviewSelect>>",
#             wrapper,
#         )

#     return file_tree
