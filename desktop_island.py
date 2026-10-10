"""
Alfred notch — a Coucou-style island that lives at the top-centre of your screen.

A frameless, always-on-top pywebview window (720x320, hidden from the taskbar). The page
reports the island's live shape every frame and we clip the window to it with a Win32
region, so only the island is visible and clickable — everything else passes through
to the apps underneath. While hidden, only an invisible 240px wake strip on the top
edge remains; hover it and the island peeks out.

Usage:
    python desktop_island.py                 # uses / starts the Alfred backend on :8000
    python desktop_island.py --url URL       # point at another server (e.g. Vite dev)
"""
import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import threading
import time
from ctypes import wintypes

import requests

BACKEND = "http://127.0.0.1:8000"
PANEL_W, PANEL_H = 720, 320
STRIP_W, STRIP_H = 240, 4

user32 = ctypes.windll.user32 if sys.platform == "win32" else None
gdi32 = ctypes.windll.gdi32 if sys.platform == "win32" else None

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
LWA_ALPHA = 0x2
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

if user32:
    user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
    user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    gdi32.CreateRectRgn.restype = wintypes.HRGN
    gdi32.CreateRoundRectRgn.restype = wintypes.HRGN
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    user32.GetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN]
    user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user32.MonitorFromPoint.restype = wintypes.HMONITOR
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


MONITOR_DEFAULTTONEAREST = 2


def _log(msg):
    try:
        os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"), exist_ok=True)
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "notch.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def ensure_backend():
    try:
        if requests.get(BACKEND, timeout=1.0).status_code == 200:
            return
    except Exception:
        pass
    print("[Notch] Starting Alfred backend...")
    root = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen([sys.executable, os.path.join(root, "web", "app.py")], cwd=root)
    for _ in range(30):
        time.sleep(0.5)
        try:
            if requests.get(BACKEND, timeout=0.5).status_code == 200:
                print("[Notch] Backend online.")
                return
        except Exception:
            pass
    print("[Notch] Backend did not come up in time; the notch will keep retrying.")


class NotchApi:
    """Exposed to the page as window.pywebview.api."""

    def __init__(self):
        self._window = None
        self._hwnd = None
        self._scale = 1.0
        self._alpha = None
        self._last_shape = None
        self._monitor = None

    def close(self):
        if self._window:
            self._window.destroy()


    # ── window setup (on "shown", and lazily from set_shape if that didn't happen) ──
    def _attach(self):
        if self._hwnd:
            return
        try:
            self._do_attach()
        except Exception as e:  # never leave a full black panel on screen
            self._hwnd = None
            _log(f"attach failed: {e!r}")

    def _do_attach(self):
        hwnd = 0
        try:
            hwnd = self._window.native.Handle.ToInt32()
        except Exception:
            hwnd = user32.FindWindowW(None, "Alfred")
        if not hwnd:
            raise RuntimeError("notch window handle not found")
        form = self._window.native
        self._hwnd = hwnd
        try:
            self._scale = user32.GetDpiForWindow(self._hwnd) / 96.0
        except Exception:
            self._scale = 1.0
        try:
            from System.Drawing import Color  # pythonnet, available with the WinForms backend
            form.BackColor = Color.Black
        except Exception:
            pass

        ex = user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
        ex = (ex | WS_EX_LAYERED | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, ex)

        # Start as the invisible wake strip on the cursor's monitor
        self._place_on_cursor_monitor(force=True)
        threading.Thread(target=self._follow_cursor_monitor, daemon=True).start()

    # ── multi-monitor: the hidden notch moves to the top-centre of the screen you're on ──
    def _cursor_monitor(self):
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)

    def _place_on_cursor_monitor(self, force=False):
        mon = self._cursor_monitor()
        if not force and mon == self._monitor:
            return
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return
        self._monitor = mon
        m = info.rcMonitor
        self._mon_rect = (m.left, m.top, m.right)
        # Move onto that monitor first so Windows applies its DPI, then re-fit the window
        user32.SetWindowPos(self._hwnd, HWND_TOPMOST, (m.left + m.right) // 2, m.top, 1, 1, SWP_NOACTIVATE)
        try:
            self._scale = user32.GetDpiForWindow(self._hwnd) / 96.0
        except Exception:
            pass
        shape, self._last_shape = self._last_shape, None
        self.set_shape(*(shape or (0, 0, STRIP_W, STRIP_H, 0, True)))

    def _follow_cursor_monitor(self):
        """While hidden, keep the wake strip on the monitor the cursor is on."""
        while self._hwnd:
            time.sleep(0.5)
            try:
                if self._last_shape and self._last_shape[5]:  # only while hidden, never mid-use
                    self._place_on_cursor_monitor()
            except Exception as e:
                _log(f"monitor follow failed: {e!r}")

    def _set_alpha(self, alpha):
        if alpha != self._alpha:
            self._alpha = alpha
            user32.SetLayeredWindowAttributes(self._hwnd, 0, alpha, LWA_ALPHA)

    # ── called from the page every frame with the island's live size ──
    # The window is resized to exactly the island (WebView2 draws through a GPU layer that
    # Windows doesn't reliably clip to a window region, so there must be no spare window area).
    def set_shape(self, x, y, w, h, r, hidden=False):
        if not self._hwnd:
            self._attach()
            if not self._hwnd or not hasattr(self, "_mon_rect"):
                return
        shape = (round(x), round(y), round(w), round(h), round(r), bool(hidden))
        if shape == self._last_shape:
            return
        self._last_shape = shape
        s = self._scale
        left, top, right = self._mon_rect
        if hidden or h < 2:
            pw, ph = int(STRIP_W * s), max(1, int(STRIP_H * s))  # invisible wake strip
        else:
            pw, ph = max(1, int(round(w * s))), max(1, int(round(h * s)))
        user32.SetWindowPos(self._hwnd, HWND_TOPMOST, (left + right - pw) // 2, top, pw, ph, SWP_NOACTIVATE | SWP_SHOWWINDOW)
        if hidden or h < 2:
            user32.SetWindowRgn(self._hwnd, None, True)
            self._set_alpha(1)
            return
        # Rounded bottom corners (best effort; square black corners are the fallback)
        d = max(2, int(2 * r * s))
        user32.SetWindowRgn(self._hwnd, gdi32.CreateRoundRectRgn(0, -d, pw + 1, ph + 1, d, d), True)
        self._set_alpha(255)


def launch_with_pywebview(url):
    import webview

    api = NotchApi()
    window = webview.create_window(
        "Alfred",
        url,
        js_api=api,
        width=PANEL_W,
        height=PANEL_H,
        x=-4000,  # starts off-screen; _attach moves it into place once it's clipped
        y=-4000,
        min_size=(1, 1),
        frameless=True,
        easy_drag=False,
        on_top=True,
        resizable=False,
        background_color="#000000",
        shadow=False,
    )
    api._window = window
    window.events.shown += api._attach
    webview.start()


def launch_with_browser(url):
    """Fallback when pywebview isn't available: Edge/Chrome app window."""
    for browser in (
        shutil.which("msedge") or r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        shutil.which("chrome") or r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ):
        if browser and os.path.exists(browser):
            subprocess.Popen([browser, f"--app={url}", f"--window-size={PANEL_W},{PANEL_H}"])
            return
    import webbrowser
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Alfred notch")
    parser.add_argument("--url", help="Server to load (default: the Alfred backend)")
    args = parser.parse_args()

    base = args.url or BACKEND
    if not args.url:
        ensure_backend()
    url = base.rstrip("/") + "/?mode=island"

    if sys.platform != "win32":
        launch_with_browser(url)
        return
    try:
        import webview  # noqa: F401
    except ImportError:
        print("[Notch] pywebview not installed; falling back to a browser app window.")
        launch_with_browser(url)
        return
    launch_with_pywebview(url)


if __name__ == "__main__":
    main()
