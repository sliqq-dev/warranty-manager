"""
Auto-updater module for Warranty Manager.
Checks GitHub Releases, shows splash screen, downloads + replaces exe if needed.
"""

import sys
import os
import json
import threading
import subprocess
import tempfile
import shutil
import tkinter as tk
from tkinter import messagebox

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_USER    = "sliqq-dev"
GITHUB_REPO    = "warranty-manager"
GITHUB_API     = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
CURRENT_VER_FILE = os.path.join(
    os.path.dirname(sys.executable if getattr(sys,"frozen",False) else os.path.abspath(__file__)),
    "version.json"
)

# ── Colours (match main app) ──────────────────────────────────────────────────
BG      = "#0F0F17"
SURFACE = "#1A1A2E"
BORDER  = "#2A2A45"
ACCENT  = "#7C6EF5"
TEXT    = "#EEEEF5"
TEXT2   = "#8888AA"
TEXT3   = "#55556A"
SUCCESS = "#34D399"
DANGER  = "#F87171"

def get_current_version():
    try:
        with open(CURRENT_VER_FILE, "r") as f:
            return json.load(f).get("version", "0.0.0")
    except Exception:
        return "0.0.0"

def save_version(version):
    try:
        with open(CURRENT_VER_FILE, "w") as f:
            json.dump({"version": version}, f)
    except Exception:
        pass

def parse_version(v):
    """Convert '1.2.3' → (1, 2, 3) for comparison."""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)

# ══════════════════════════════════════════════════════════════════════════════
#  SPLASH / UPDATE WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class SplashScreen(tk.Tk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)   # No title bar
        self.configure(bg=BG)
        self.attributes("-topmost", True)

        # DPI fix
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                pass

        W, H = 480, 300
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self._build()
        self.result  = "launch"   # "launch" | "updated" | "error"
        self._done   = False

    def _build(self):
        # Thin accent top border
        tk.Frame(self, bg=ACCENT, height=3).pack(fill="x")

        # Logo area
        logo_frame = tk.Frame(self, bg=BG, pady=32)
        logo_frame.pack(fill="x")
        tk.Label(logo_frame, text="⚙", font=("Segoe UI", 36),
                 bg=BG, fg=ACCENT).pack()
        tk.Label(logo_frame, text="Warranty Manager",
                 font=("Segoe UI", 18, "bold"), bg=BG, fg=TEXT).pack()
        self.version_label = tk.Label(
            logo_frame, text=f"v{get_current_version()}",
            font=("Segoe UI", 10), bg=BG, fg=TEXT3)
        self.version_label.pack(pady=(2, 0))

        # Status area
        status_frame = tk.Frame(self, bg=BG)
        status_frame.pack(fill="x", padx=40)

        self.status_label = tk.Label(
            status_frame, text="Checking for updates...",
            font=("Segoe UI", 10), bg=BG, fg=TEXT2, anchor="w")
        self.status_label.pack(fill="x", pady=(0, 8))

        # Progress bar (canvas-based, no ttk blurriness)
        self.bar_canvas = tk.Canvas(
            status_frame, height=4, bg=SURFACE,
            highlightthickness=1, highlightbackground=BORDER)
        self.bar_canvas.pack(fill="x")
        self._bar_rect = self.bar_canvas.create_rectangle(
            0, 0, 0, 4, fill=ACCENT, outline="")

        # Step label  e.g. "1 / 3"
        self.step_label = tk.Label(
            status_frame, text="",
            font=("Consolas", 9), bg=BG, fg=TEXT3, anchor="e")
        self.step_label.pack(fill="x", pady=(4, 0))

        # Bottom note
        tk.Label(self, text="© sliqq-dev", font=("Segoe UI", 8),
                 bg=BG, fg=TEXT3).pack(side="bottom", pady=12)

    def set_status(self, text, step=None, total=None, color=TEXT2):
        self.status_label.config(text=text, fg=color)
        if step is not None and total is not None:
            self.step_label.config(text=f"{step} / {total}")
            self._set_progress(step / total)
        self.update_idletasks()

    def _set_progress(self, fraction):
        self.bar_canvas.update_idletasks()
        w = self.bar_canvas.winfo_width()
        if w < 2: w = 400
        self.bar_canvas.coords(self._bar_rect, 0, 0, int(w * fraction), 4)
        self.bar_canvas.itemconfig(self._bar_rect, fill=ACCENT)

    def finish(self, success=True, message="Launching..."):
        color = SUCCESS if success else DANGER
        self.status_label.config(text=message, fg=color)
        self._set_progress(1.0)
        self.bar_canvas.itemconfig(self._bar_rect, fill=color)
        self.step_label.config(text="")
        self.update_idletasks()

    def close(self):
        self._done = True
        self.destroy()

# ══════════════════════════════════════════════════════════════════════════════
#  UPDATE LOGIC
# ══════════════════════════════════════════════════════════════════════════════
def run_update_check(splash: SplashScreen):
    """
    Runs in a background thread.
    Steps:
      1. Check GitHub for latest release
      2. Compare versions
      3. Download new exe if needed
      4. Replace + relaunch
    """
    TOTAL_STEPS = 3

    try:
        # ── Step 1: Fetch release info ────────────────────────────────────────
        splash.after(0, splash.set_status,
                     "Connecting to update server...", 1, TOTAL_STEPS)

        if not REQUESTS_OK:
            splash.after(0, splash.finish, True, "Launching (no update check)...")
            splash.after(800, splash.close)
            return

        try:
            resp = requests.get(GITHUB_API, timeout=6,
                                headers={"Accept": "application/vnd.github+json"})
            resp.raise_for_status()
            release = resp.json()
        except Exception:
            # Can't reach GitHub — just launch normally
            splash.after(0, splash.finish, True, "Launching (offline mode)...")
            splash.after(800, splash.close)
            return

        latest_ver  = release.get("tag_name", "0.0.0").lstrip("v")
        current_ver = get_current_version()

        # ── Step 2: Compare versions ──────────────────────────────────────────
        splash.after(0, splash.set_status,
                     f"Checking version...  current: v{current_ver}  latest: v{latest_ver}",
                     2, TOTAL_STEPS)

        if parse_version(latest_ver) <= parse_version(current_ver):
            splash.after(0, splash.finish, True,
                         f"You're up to date!  (v{current_ver})")
            splash.after(900, splash.close)
            return

        # ── Step 3: Download new exe ──────────────────────────────────────────
        # Find the Windows exe asset in the release
        assets = release.get("assets", [])
        exe_asset = next(
            (a for a in assets if a["name"].lower().endswith(".exe")), None)

        if not exe_asset:
            # No exe attached to release — just launch
            splash.after(0, splash.finish, True,
                         f"Update v{latest_ver} found but no exe attached.")
            splash.after(1200, splash.close)
            return

        download_url = exe_asset["browser_download_url"]
        file_size    = exe_asset.get("size", 0)

        splash.after(0, splash.set_status,
                     f"Downloading v{latest_ver}...", 3, TOTAL_STEPS)

        # Stream download with progress
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".exe")
        os.close(tmp_fd)

        with requests.get(download_url, stream=True, timeout=60) as dl:
            dl.raise_for_status()
            downloaded = 0
            with open(tmp_path, "wb") as f:
                for chunk in dl.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if file_size > 0:
                            frac = 2/3 + (downloaded / file_size) * (1/3)
                            pct  = int(downloaded / file_size * 100)
                            splash.after(0, splash.set_status,
                                         f"Downloading v{latest_ver}...  {pct}%",
                                         3, TOTAL_STEPS)
                            splash.after(0, splash.bar_canvas.itemconfig,
                                         splash._bar_rect, )
                            # Directly update bar fraction
                            splash.after(0, _set_bar, splash, frac)

        # ── Replace exe + relaunch ────────────────────────────────────────────
        save_version(latest_ver)

        current_exe = sys.executable if getattr(sys, "frozen", False) \
                      else os.path.abspath(__file__)

        if sys.platform == "win32":
            # Write a small bat that waits, replaces, relaunches
            bat = (
                f'@echo off\n'
                f'ping 127.0.0.1 -n 3 > nul\n'
                f'move /y "{tmp_path}" "{current_exe}"\n'
                f'start "" "{current_exe}"\n'
            )
            bat_path = tmp_path + "_update.bat"
            with open(bat_path, "w") as bf:
                bf.write(bat)
            splash.after(0, splash.finish, True,
                         f"Updated to v{latest_ver}! Relaunching...")
            splash.after(800, lambda: [
                subprocess.Popen(["cmd", "/c", bat_path],
                                 creationflags=subprocess.CREATE_NO_WINDOW),
                splash.close(),
                sys.exit(0)
            ])
        else:
            # macOS / Linux: replace directly
            shutil.move(tmp_path, current_exe)
            os.chmod(current_exe, 0o755)
            splash.after(0, splash.finish, True,
                         f"Updated to v{latest_ver}! Relaunching...")
            splash.after(800, lambda: [
                subprocess.Popen([current_exe]),
                splash.close(),
                sys.exit(0)
            ])

    except Exception as e:
        splash.after(0, splash.finish, False, f"Update error — launching anyway")
        splash.after(1200, splash.close)


def _set_bar(splash, fraction):
    try:
        w = splash.bar_canvas.winfo_width()
        if w < 2: w = 400
        splash.bar_canvas.coords(splash._bar_rect, 0, 0, int(w * fraction), 4)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def check_and_update():
    """
    Call this at the very start of main().
    Shows splash, checks for updates, blocks until splash closes.
    """
    splash = SplashScreen()

    # Start update check in background thread
    t = threading.Thread(target=run_update_check, args=(splash,), daemon=True)
    t.start()

    splash.mainloop()   # Blocks here until splash.close() is called
