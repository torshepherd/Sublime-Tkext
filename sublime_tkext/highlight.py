from collections import defaultdict
from dataclasses import dataclass
from multiprocessing import Pipe, Process
from multiprocessing.connection import PipeConnection
import re
from typing import Any, DefaultDict, Dict, List, Literal, Mapping, Optional, Tuple

from pygments import highlight, lex
from pygments.lexers import guess_lexer, get_lexer_by_name
from pygments.token import _TokenType


@dataclass
class HighlightRequest:
    file_id: Any
    text: str
    language: Optional[str] = None


@dataclass
class TagInfo:
    start: int
    end: int
    tag: str


@dataclass
class HighlightResponse:
    file_id: Any
    tokens: List[TagInfo]
    language: str


def highlight_process(inner_pipe: PipeConnection):
    while True:
        req = inner_pipe.recv()
        if isinstance(req, HighlightRequest):
            if req.language is None:
                lexer = guess_lexer(req.text)
            else:
                lexer = get_lexer_by_name(req.language)
            tokens = lex(req.text, lexer)

            tags: List[TagInfo] = []
            (match,) = re.findall(r"^\n*", req.text)
            current_position = 0 + len(match)
            for token in tokens:
                if token[1] != "":
                    tags.append(
                        TagInfo(
                            start=current_position,
                            end=current_position + len(token[1]),
                            tag=str(token[0]),
                        )
                    )
                current_position += len(token[1])
            inner_pipe.send(
                HighlightResponse(
                    file_id=req.file_id,
                    tokens=tags,
                    language=req.language or repr(dir(lexer)),
                )
            )


class PygmentsHighlighter:
    def __init__(self) -> None:
        self.connection, inner_connection = Pipe()
        self.highlight_process = Process(
            target=highlight_process,
            args=(inner_connection,),
            daemon=True,
        )
        self.highlight_process.start()

    def send_highlight_request(self, code: str, file_identifier: Any):
        self.connection.send(HighlightRequest(file_id=file_identifier, text=code))

    def get_response(self) -> Optional[HighlightResponse]:
        if self.connection.poll():
            return self.connection.recv()
        return None


def parse_styles(d: Mapping[_TokenType, str]) -> Dict[str, Dict]:
    output_dict: Dict[str, Dict] = {}
    for k in d:
        if str(k) not in output_dict.keys():
            output_dict[str(k)] = parse_style_string(k, d)
    return output_dict


def parse_style_string(
    k: _TokenType, d: Mapping[_TokenType, str]
) -> DefaultDict[str, Any]:
    styles = d[k].split(" ")
    style_dict: DefaultDict[str, Any] = (
        parse_style_string(k.parent, d)
        if k.parent is not None
        else defaultdict(lambda: None)
    )
    for style in styles:
        if style.startswith("#"):
            style_dict["foreground"] = style
        elif style.startswith("bg:") and len(style) > 3:
            style_dict["background"] = style[3:]
        elif style == "italic":
            style_dict["italic"] = True
        elif style == "bold":
            style_dict["bold"] = True
        elif style == "underline":
            style_dict["underline"] = True
        elif style == "noitalic":
            style_dict["italic"] = False
        elif style == "nobold":
            style_dict["bold"] = False
        elif style == "nounderline":
            style_dict["underline"] = False
    return style_dict
