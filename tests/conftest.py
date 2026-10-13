"""Test isolation: redirects the SQLite DB and filesystem-sandbox root to a
throwaway temp directory *before* dw_windows_mcp is imported anywhere, and
globally blocks any real subprocess/registry/service mutation so the test
suite can never touch the host system."""
from __future__ import annotations

import os
import shutil
import tempfile

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="dw_windows_mcp_test_")
os.environ["DW_MCP_DATA_DIR"] = _TEST_DATA_DIR
os.environ["DW_MCP_FS_ROOTS"] = _TEST_DATA_DIR
os.environ["DW_MCP_CONFIRM_TTL"] = "120"

import pytest

from dw_windows_mcp.db import Base, engine, init_db


@pytest.fixture(autouse=True)
def _clean_db():
    """Fresh tables for every test — no state leaks between tests."""
    init_db()
    yield
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture(autouse=True)
def _block_real_subprocess(monkeypatch):
    """Replaces subprocess.run/Popen everywhere with a recording fake, so no
    tool (power.*, services.*, install.*, network.ping, autostart.*) can ever
    execute a real command against the host during tests."""
    import subprocess

    calls: list[dict] = []

    class FakeCompletedProcess:
        def __init__(self, args):
            self.args = args
            self.returncode = 0
            self.stdout = "FAKE_OK"
            self.stderr = ""

    def fake_run(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return FakeCompletedProcess(args)

    class FakePopen:
        def __init__(self, args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs, "popen": True})
            self.pid = 424242

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    return calls


@pytest.fixture
def fake_winreg(monkeypatch):
    """Replaces the registry tool module's winreg with an in-memory fake, so
    registry tests never touch the real Windows registry and run on any OS."""
    from dw_windows_mcp.tools import registry as registry_tool

    store: dict[tuple, dict] = {}

    class FakeKey:
        def __init__(self, hive, subkey):
            self.hive = hive
            self.subkey = subkey

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = "HKLM"
        HKEY_CURRENT_USER = "HKCU"
        REG_SZ = 1
        REG_DWORD = 4
        KEY_SET_VALUE = 0x0002

        def OpenKey(self, hive, subkey, *a, **kw):
            if (hive, subkey) not in store:
                raise FileNotFoundError(subkey)
            return FakeKey(hive, subkey)

        def CreateKeyEx(self, hive, subkey, *a, **kw):
            store.setdefault((hive, subkey), {})
            return FakeKey(hive, subkey)

        def SetValueEx(self, key, name, _reserved, reg_type, value):
            store.setdefault((key.hive, key.subkey), {})[name] = (value, reg_type)

        def QueryValueEx(self, key, name):
            data = store.get((key.hive, key.subkey), {})
            if name not in data:
                raise FileNotFoundError(name)
            return data[name]

        def DeleteValue(self, key, name):
            del store[(key.hive, key.subkey)][name]

        def EnumValue(self, key, index):
            data = store.get((key.hive, key.subkey), {})
            items = list(data.items())
            if index >= len(items):
                raise OSError("no more items")
            name, (value, reg_type) = items[index]
            return name, value, reg_type

        def EnumKey(self, key, index):
            raise OSError("no subkeys")

    fake = FakeWinreg()
    monkeypatch.setattr(registry_tool, "winreg", fake)
    monkeypatch.setattr(
        registry_tool,
        "_HIVES",
        {"HKEY_LOCAL_MACHINE": fake.HKEY_LOCAL_MACHINE, "HKEY_CURRENT_USER": fake.HKEY_CURRENT_USER},
    )
    return store


@pytest.fixture
def fake_psutil_process(monkeypatch):
    """Replaces psutil.Process so process.kill never touches a real PID."""
    import psutil

    killed = []

    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid

        def name(self):
            return f"fake-proc-{self.pid}"

        def kill(self):
            killed.append(self.pid)

    monkeypatch.setattr(psutil, "Process", FakeProcess)
    return killed


@pytest.fixture
def fake_pyautogui(monkeypatch):
    """Injects a fake pyautogui module so gui.* tools never move the real
    mouse, type into the real focused window, or screenshot the real screen."""
    import sys
    import types

    calls: list[tuple] = []
    fake = types.ModuleType("pyautogui")

    def _record(name):
        def _fn(*args, **kwargs):
            calls.append((name, args, kwargs))

        return _fn

    fake.moveTo = _record("moveTo")
    fake.click = _record("click")
    fake.write = _record("write")
    fake.hotkey = _record("hotkey")

    class _FakeImage:
        width, height = 10, 10

        def save(self, buf, format):
            buf.write(b"\x89PNG\r\n\x1a\nFAKE")

    fake.screenshot = lambda: _FakeImage()

    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    return calls


@pytest.fixture
def fake_win32com(monkeypatch):
    """Injects a fake win32com.client so tts.* tools never speak out loud or
    touch the real SAPI engine during tests."""
    import sys
    import types

    calls: list[tuple] = []

    class FakeSpVoice:
        def __init__(self):
            self.Rate = 0
            self.Volume = 100
            self.AudioOutputStream = None

        def Speak(self, text):
            calls.append(("Speak", text))

    class FakeSpFileStream:
        def Open(self, path, mode, *a):
            calls.append(("Open", path, mode))
            with open(path, "wb") as f:
                f.write(b"RIFF_FAKE_WAV")

        def Close(self):
            calls.append(("Close",))

    def dispatch(name):
        if name == "SAPI.SpVoice":
            return FakeSpVoice()
        if name == "SAPI.SpFileStream":
            return FakeSpFileStream()
        raise ValueError(f"unexpected Dispatch target: {name}")

    client_module = types.ModuleType("win32com.client")
    client_module.Dispatch = dispatch
    win32com_module = types.ModuleType("win32com")
    win32com_module.client = client_module

    monkeypatch.setitem(sys.modules, "win32com", win32com_module)
    monkeypatch.setitem(sys.modules, "win32com.client", client_module)
    return calls


@pytest.fixture
def fake_urlopen(monkeypatch):
    """Replaces urllib.request.urlopen everywhere under dw_windows_mcp.tools
    with a scripted fake response, so network.* tools never make a real
    internet request during tests."""
    import urllib.request

    class FakeResponse:
        def __init__(self, body: bytes, status: int = 200, headers: dict | None = None):
            self._body = body
            self.status = status
            self.headers = headers or {}

        def read(self, n: int | None = None):
            if n is None:
                data, self._body = self._body, b""
                return data
            data, self._body = self._body[:n], self._body[n:]
            return data

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    state = {"response": FakeResponse(b"")}

    def fake_urlopen(req, timeout=None):
        return state["response"]

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return state


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
