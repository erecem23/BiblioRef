"""BiblioRef Windows launcher.

Small bootstrapper for a local Git checkout. It updates the current branch,
keeps a local virtual environment in sync, and starts the native desktop shell.
No credentials are embedded: Git uses the user's existing GitHub authentication.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import socket
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

APP_NAME = "BiblioRef"
HOST = "127.0.0.1"
PORT = 8775
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
    roots.append(Path(__file__).resolve().parent)
    roots.append(Path.cwd().resolve())

    expanded: list[Path] = []
    for root in roots:
        expanded.append(root)
        expanded.extend(root.parents)
    return list(dict.fromkeys(expanded))


def find_repo_root() -> Path:
    for root in _candidate_roots():
        if (root / ".git").exists() and (root / "run_biblioref_desktop.py").exists():
            return root
    raise RuntimeError(
        "No encuentro la carpeta del repositorio BiblioRef. "
        "Ubicá BiblioRef.exe dentro de la carpeta clonada o en una subcarpeta de ella."
    )


def log(root: Path, message: str) -> None:
    log_dir = root / ".biblioref"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / "launcher.log").open("a", encoding="utf-8") as fh:
        stamp = datetime.now().isoformat(timespec="seconds")
        fh.write(f"[{stamp}] {message}\n")


def run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )
    if check and completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"{' '.join(args)} falló: {details}")
    return completed


def port_is_open() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.25):
            return True
    except OSError:
        return False


def requirements_digest(path: Path, seen: set[Path] | None = None) -> str:
    """Hash a requirements file and local -r includes so dependency changes are noticed."""
    seen = seen or set()
    path = path.resolve()
    if path in seen:
        return ""
    seen.add(path)

    digest = hashlib.sha256()
    content = path.read_bytes()
    digest.update(str(path.name).encode("utf-8"))
    digest.update(content)

    for raw_line in content.decode("utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("-r "):
            child = (path.parent / line[3:].strip()).resolve()
            if child.exists():
                digest.update(requirements_digest(child, seen).encode("ascii"))
    return digest.hexdigest()


def find_python_command() -> list[str]:
    py = shutil.which("py")
    if py:
        return [py, "-3"]
    python = shutil.which("python")
    if python:
        return [python]
    raise RuntimeError(
        "No encuentro Python 3 en Windows. Instalá Python y asegurate de marcar "
        "\"Add Python to PATH\"."
    )


def ensure_environment(root: Path, status) -> Path:
    venv = root / ".venv"
    python_exe = venv / "Scripts" / "python.exe"
    pythonw_exe = venv / "Scripts" / "pythonw.exe"
    requirements = root / "requirements-desktop-windows.txt"
    marker = venv / ".biblioref_requirements.sha256"

    if not requirements.exists():
        raise RuntimeError("Falta requirements-desktop-windows.txt en el repositorio.")

    if not python_exe.exists():
        status("Preparando BiblioRef por primera vez…")
        run(find_python_command() + ["-m", "venv", str(venv)], cwd=root, timeout=180)

    expected = requirements_digest(requirements)
    installed = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""

    if expected != installed:
        status("Actualizando componentes de BiblioRef…")
        run(
            [str(python_exe), "-m", "pip", "install", "-r", str(requirements)],
            cwd=root,
            timeout=900,
        )
        marker.write_text(expected, encoding="utf-8")

    if not pythonw_exe.exists():
        raise RuntimeError("El entorno de Python se creó, pero falta pythonw.exe.")

    return pythonw_exe


def update_repository(root: Path, status) -> str:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("No encuentro Git en Windows.")

    branch = run([git, "rev-parse", "--abbrev-ref", "HEAD"], cwd=root).stdout.strip()
    if not branch or branch == "HEAD":
        raise RuntimeError("El repositorio está en detached HEAD; elegí main o dev.")

    dirty = run([git, "status", "--porcelain"], cwd=root).stdout.strip()
    if dirty:
        raise RuntimeError(
            "Hay cambios locales sin guardar. Para protegerlos, BiblioRef no se "
            "actualizó automáticamente. Hacé commit/stash o revertí esos cambios."
        )

    status(f"Buscando actualizaciones ({branch})…")
    run([git, "fetch", "origin", branch], cwd=root, timeout=120)
    run([git, "pull", "--ff-only", "origin", branch], cwd=root, timeout=120)
    return branch


def launch_desktop(root: Path, pythonw_exe: Path) -> None:
    if port_is_open():
        raise RuntimeError("BiblioRef ya parece estar abierto (puerto local 8775 en uso).")

    subprocess.Popen(
        [str(pythonw_exe), str(root / "run_biblioref_desktop.py")],
        cwd=str(root),
        close_fds=True,
        creationflags=CREATE_NO_WINDOW,
    )


class Launcher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("460x210")
        self.resizable(False, False)
        self.configure(padx=28, pady=24)

        self.heading = tk.Label(self, text="BiblioRef", font=("Segoe UI", 22, "bold"))
        self.heading.pack(pady=(4, 14))

        self.status_var = tk.StringVar(value="Iniciando…")
        self.status_label = tk.Label(
            self,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            wraplength=400,
            justify="center",
        )
        self.status_label.pack(pady=8)

        self.progress = tk.Label(self, text="●", font=("Segoe UI", 12))
        self.progress.pack(pady=(8, 0))

        self.after(150, self.start)

    def set_status(self, text: str) -> None:
        self.after(0, self.status_var.set, text)

    def start(self) -> None:
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self) -> None:
        root: Path | None = None
        try:
            root = find_repo_root()
            log(root, "Launcher iniciado")

            try:
                branch = update_repository(root, self.set_status)
                log(root, f"Repositorio actualizado en rama {branch}")
            except Exception as update_error:
                log(root, f"Actualización omitida: {update_error}")
                self.set_status("No se pudo actualizar; abriendo la versión local…")

            pythonw_exe = ensure_environment(root, self.set_status)
            self.set_status("Abriendo BiblioRef…")
            launch_desktop(root, pythonw_exe)
            log(root, "Aplicación iniciada")
            self.after(700, self.destroy)
        except Exception as exc:
            if root is not None:
                log(root, f"ERROR: {exc}\n{traceback.format_exc()}")
            self.after(0, lambda: self.show_error(str(exc)))

    def show_error(self, message: str) -> None:
        self.status_var.set("No se pudo iniciar BiblioRef.")
        messagebox.showerror(
            APP_NAME,
            f"{message}\n\nEl detalle técnico quedó guardado en "
            ".biblioref\\launcher.log cuando fue posible.",
        )


def main() -> None:
    Launcher().mainloop()


if __name__ == "__main__":
    main()
