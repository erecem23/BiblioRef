"""Windows-oriented desktop shell for the same local BiblioRef web application."""
from __future__ import annotations

import socket
import threading
import time

import uvicorn
import webview

import app as app_module
from biblioref.metadata.integration import install_cover_metadata
from biblioref.parsing.review_export import install_parser_review_export

install_cover_metadata(app_module)
install_parser_review_export(app_module)
app = app_module.app

HOST = "127.0.0.1"
PORT = 8775


def _serve():
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def _wait_server(timeout: float = 15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("BiblioRef no pudo iniciar su servidor local")


def main():
    # pywebview disables file downloads by default. BiblioRef exports XLSX/CSV/JSON
    # as HTTP attachments, so desktop mode must opt in explicitly.
    webview.settings["ALLOW_DOWNLOADS"] = True

    threading.Thread(target=_serve, daemon=True).start()
    _wait_server()
    webview.create_window(
        "BiblioRef",
        f"http://{HOST}:{PORT}",
        width=1480,
        height=920,
        min_size=(1050, 700),
        text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
