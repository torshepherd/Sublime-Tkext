from collections import defaultdict
from dataclasses import dataclass
import dataclasses
import json
import os
from typing import Dict, Generic, List, Literal, Protocol, Set, Type, TypeVar

from .utils import SetEncoder, get_path_to_configs


class Dictable:
    def __init_from_dict__(self, data: Dict):
        self.__init__(**data)

    def to_dict(self):
        return dataclasses.asdict(self)


T = TypeVar("T", bound=Dictable)


class Config(Generic[T]):
    def __init__(self, filename: str, config_class: Type[T]):
        self.filename = filename
        self.config_class = config_class
        self.data = config_class()

    @property
    def path_to_config(self):
        return get_path_to_configs() / self.filename

    def _save_unsafe(self):
        with open(self.path_to_config, "w") as f:
            json.dump(self.data.to_dict(), f, indent=2, cls=SetEncoder)

    def _ensure_exists(self):
        os.makedirs(os.path.dirname(self.path_to_config), exist_ok=True)
        if not os.path.exists(self.path_to_config):
            self._save_unsafe()

    def save(self):
        self._ensure_exists()
        self._save_unsafe()

    def load(self):
        self._ensure_exists()
        with open(self.path_to_config) as f:
            try:
                self.data.__init_from_dict__(json.load(f))
            except json.JSONDecodeError as e:
                print("Failed to load config file.")
                print(e)
        return self


# Settings


@dataclass
class Settings(Dictable):
    workbench_ui_theme: str = "dark"
    # TODO: pass this to Editor
    editor_color_theme: str = "material"
    # TODO: pass this to Editor
    editor_font_family: str = "Consolas"
    # TODO: support font size both in UI and editor
    editor_font_size: int = 12
    # TODO: support ligatures
    editor_font_ligatures: bool = True
    # TODO: support minimap
    editor_minimap_enabled: bool = True
    # TODO: support line numbers
    editor_line_numbers: Literal["on", "off", "relative"] = "on"
    files_insert_final_newline: bool = True
    font_size: int = 12
    tab_size: int = 4
    line_numbers: bool = True


# Workspace


@dataclass
class WorkspaceConfig:
    tab_paths: List[str] = dataclasses.field(default_factory=list)
    active_tab: int = 0


@dataclass
class WindowConfig:
    x: int = 0
    y: int = 0
    width: int = 800
    height: int = 600
    zoomed: bool = False

    def to_tkinter_form(self) -> str:
        return f"{self.width}x{self.height}+{self.x}+{self.y}"

    @classmethod
    def from_tkinter_form(cls, geometry_string: str) -> "WindowConfig":
        width, rest = geometry_string.split("x")
        height, x, y = rest.split("+")
        return cls(
            x=int(x),
            y=int(y),
            width=int(width),
            height=int(height),
            zoomed=False,
        )


@dataclass
class EditorSavedState(Dictable):
    workspaces: Dict[str, WorkspaceConfig] = dataclasses.field(default_factory=dict)
    recent_folder_paths: Set[str] = dataclasses.field(default_factory=set)
    recent_file_paths: Set[str] = dataclasses.field(default_factory=set)
    window_config: WindowConfig = dataclasses.field(default_factory=WindowConfig)

    def __init_from_dict__(self, data: Dict):
        self.__init__(
            workspaces={
                name: WorkspaceConfig(**workspace)
                for name, workspace in data["workspaces"].items()
            },
            recent_folder_paths=set(data["recent_folder_paths"]),
            recent_file_paths=set(data["recent_file_paths"]),
            window_config=WindowConfig(**data["window_config"]),
        )
