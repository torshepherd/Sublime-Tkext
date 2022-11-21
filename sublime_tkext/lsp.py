import os
from queue import Empty, Queue
from subprocess import PIPE, Popen
from threading import Thread
from typing import Dict, List, Optional, Union

from pylsp_jsonrpc import streams

# interface TextDocumentItem {
# 	/**
# 	 * The text document's URI.
# 	 */
# 	uri: DocumentUri;

# 	/**
# 	 * The text document's language identifier.
# 	 */
# 	languageId: string;

# 	/**
# 	 * The version number of this document (it will increase after each
# 	 * change, including undo/redo).
# 	 */
# 	version: integer;

# 	/**
# 	 * The content of the opened text document.
# 	 */
# 	text: string;
# }


class ThreadedLsp:
    def __init__(self, cmd: List[str], language_target: str = "python") -> None:
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

        self.initialization_id = -1
        self.capabilities = {}

        self.send_initialize_request(root_uri=None)

        self.language_target = language_target

    def _generate_request_id(self) -> int:
        self.request_id += 1
        return self.request_id

    def read(self, msg: Dict):
        if msg["id"] == self.initialization_id:
            self.capabilities = msg["result"]["capabilities"]
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
        self.send_exit_request()
        self.process.kill()
        self.writer.close()
        self.reader.close()

    def get_response(self) -> Optional[Dict]:
        try:
            return self.rsp_queue.get_nowait()
        except Empty:
            return None

    def send_initialize_request(self, root_uri: Optional[str]):
        self.initialization_id = self.send(
            method="initialize",
            params={
                "processId": os.getpid(),
                "rootUri": root_uri,
                "capabilities": {},
            },
        )

    def send_exit_request(self):
        pass

    def send_did_open_noti(self, path: str, text_document: str):
        self.did_open_id = self.send(
            method="textDocument/didOpen",
            params={
                "textDocument": {
                    "uri": "file://" + path,
                    "languageId": self.language_target,
                    "version": 1,
                    "text": text_document,
                }
            },
        )

    def send_did_change_noti(self, path: str, text_document: str):
        self.did_change_id = self.send(
            method="textDocument/didChange",
            params={
                "textDocument": {
                    "uri": "file://" + path,
                    "version": 2,
                },
                "contentChanges": [
                    {
                        "text": text_document,
                    }
                ],
            },
        )

    def send_did_close_noti(self, path: str):
        self.did_close_id = self.send(
            method="textDocument/didClose",
            params={
                "textDocument": {
                    "uri": "file://" + path,
                }
            },
        )

    def send_did_save_noti(self, path: str):
        self.did_save_id = self.send(
            method="textDocument/didSave",
            params={
                "textDocument": {
                    "uri": "file://" + path,
                },
                "reason": 1,
            },
        )
