"""Offline voice input and safe Windows application launching for AURA."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import queue
from pathlib import Path


def parse_open_command(text: str) -> str | None:
    """Return an app name for phrases such as 'open Chrome' or 'launch Notepad'."""
    phrase = text.casefold().strip().rstrip(".!?")
    match = re.fullmatch(r"(?:please\s+)?(?:open|launch|start)\s+(.+?)(?:\s+please)?", phrase)
    if not match:
        return None
    app = match.group(1).strip()
    if app in {"the browser", "my browser", "browser"}:
        return "Chrome"
    return app[:80] or None


def _normalise_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _start_menu_shortcut(app_name: str) -> Path | None:
    roots = []
    for env_name in ("APPDATA", "PROGRAMDATA"):
        base = os.environ.get(env_name)
        if base:
            roots.append(Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs")

    wanted = _normalise_name(app_name)
    candidates = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for item in root.rglob("*.lnk"):
                stem = _normalise_name(item.stem)
                if stem == wanted:
                    return item
                if wanted and (stem.startswith(wanted) or wanted in stem):
                    candidates.append(item)
        except OSError:
            continue
    return candidates[0] if candidates else None


def launch_application(app_name: str) -> tuple[bool, str]:
    """Launch an installed app without invoking a shell or executing voice text."""
    if os.name != "nt":
        return False, "App launching is available on Windows only"

    name = app_name.strip().strip('"\'')
    aliases = {
        "google chrome": "chrome",
        "microsoft edge": "msedge",
        "edge": "msedge",
        "file explorer": "explorer",
        "windows explorer": "explorer",
        "calculator": "calc",
    }
    key = name.casefold()
    executable = aliases.get(key, name)

    known_paths = {
        "chrome": [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "C:/Users/Default/AppData/Local")) / "Google/Chrome/Application/chrome.exe",
        ],
        "msedge": [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        ],
        "firefox": [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Mozilla Firefox/firefox.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Mozilla Firefox/firefox.exe",
        ],
    }
    for path in known_paths.get(executable.casefold(), []):
        if path.is_file():
            subprocess.Popen([str(path)], shell=False)
            return True, f"opened {name}"

    shortcut = _start_menu_shortcut(name)
    if shortcut:
        os.startfile(str(shortcut))
        return True, f"opened {name}"

    path = shutil.which(executable) or shutil.which(executable + ".exe")
    if path:
        subprocess.Popen([path], shell=False)
        return True, f"opened {name}"
    return False, f"could not find an installed app named {name}"


class VoiceListener:
    """Continuously transcribe microphone audio offline on a daemon thread."""

    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        self.status = "starting offline voice"
        self._events: queue.Queue[str] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="AURA-voice", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def get_commands(self) -> list[str]:
        items = []
        while True:
            try:
                items.append(self._events.get_nowait())
            except queue.Empty:
                return items

    def _run(self) -> None:
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model, SetLogLevel

            if not self.model_path.is_dir():
                self.status = f"model missing: {self.model_path.name}"
                return

            SetLogLevel(-1)
            model = Model(str(self.model_path))
            recognizer = KaldiRecognizer(model, 16000)
            audio_blocks: queue.Queue[bytes] = queue.Queue(maxsize=32)

            def on_audio(indata, frames, timing, status):
                if status:
                    self.status = f"mic: {status}"
                try:
                    audio_blocks.put_nowait(bytes(indata))
                except queue.Full:
                    pass

            with sd.RawInputStream(
                samplerate=16000,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=on_audio,
            ):
                self.status = "listening offline"
                while not self._stop.is_set():
                    try:
                        block = audio_blocks.get(timeout=0.15)
                    except queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(block):
                        phrase = json.loads(recognizer.Result()).get("text", "").strip()
                        if phrase:
                            self._events.put(phrase)
        except Exception as exc:
            self.status = f"unavailable ({type(exc).__name__})"
