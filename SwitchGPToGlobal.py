"""
Geisterhand 5.0 — Gig Performer companion console.

Responsibilities:
  1. Launch the latest .gig file on startup — DETACHED, so this Python
     process can exit without killing Gig Performer.
  2. Listen on 127.0.0.1:8000 for OSC messages from GP:
       /GP/PressCtrlG  → laser-click the "globe" button (auto-switch to
                         Global Rackspace view, etc.)
       /GP/Trace       → live trace receiver for CrashDebugMode, ring
                         buffer of the last N lines for post-mortem.
  3. Act as a singleton. Starting a second instance cleanly terminates
     the old Python process (via its PID file) WITHOUT touching Gig
     Performer, then takes over port 8000.

Why the singleton handshake matters:
  - Closing Geisterhand must not close GP (decoupled via DETACHED_PROCESS).
  - Starting a second Geisterhand while GP is already running must not
    re-launch GP (would spawn a duplicate instance) and must not fail on
    the OSC bind (would leave the user without a trace receiver).

PID file lives at %TEMP%\\geisterhand.pid on Windows. On a clean exit the
file is removed; on a crash it stays behind and the next startup uses
the is_pid_alive() probe to detect and skip stale entries.
"""

import os
import sys
import glob
import time
import traceback
import subprocess
import tempfile

import pygetwindow as gw
import pyautogui
from pythonosc import dispatcher, osc_server, udp_client


# ============================================================
# CONFIGURATION
# ============================================================
TARGET_X = 726            # globe-button X coordinate inside GP window
TARGET_Y = 73             # globe-button Y coordinate inside GP window

GP_FOLDER = r"C:\Users\marti\OneDrive\Keyboard\GigPerformer"
GP_WINDOW_FALLBACK = "Gig Performer"

OSC_IP = "127.0.0.1"
OSC_PORT = 8000
GP_REPLY_PORT = 54344     # standard GP listening port for /GP/ViewReady

TRACE_BUFFER_SIZE = 50

PID_FILE = os.path.join(tempfile.gettempdir(), "geisterhand.pid")


# ============================================================
# SINGLETON — kill old Geisterhand Python (NOT Gig Performer)
# ============================================================
def is_pid_alive(pid: int) -> bool:
    """Return True iff the OS still has a live process with that PID."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        # tasklist exits 0 and prints the process name when alive
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=2.0,
            )
            return str(pid) in out.stdout
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def kill_old_geisterhand() -> None:
    """If a prior Geisterhand Python process is still running, terminate
    it via taskkill. Does NOT touch GP — we only kill the PID recorded
    in our own PID file."""
    if not os.path.exists(PID_FILE):
        return
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            old_pid = int(f.read().strip() or "0")
    except (OSError, ValueError):
        return

    if old_pid == os.getpid():
        return  # somehow our own PID — ignore

    if not is_pid_alive(old_pid):
        print(f"[singleton] Stale PID file (PID {old_pid} gone), cleaning up")
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
        return

    print(f"[singleton] Old Geisterhand instance alive (PID {old_pid}) — terminating...")
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/PID", str(old_pid)],
            capture_output=True, check=False,
        )
    else:
        try:
            os.kill(old_pid, 15)
        except OSError:
            pass

    # Wait briefly for the OS to release the OSC port
    for _ in range(20):
        time.sleep(0.1)
        if not is_pid_alive(old_pid):
            break
    print(f"[singleton] Old instance terminated. GP untouched.")


def write_pid_file() -> None:
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except OSError as e:
        print(f"[singleton] WARN: could not write PID file {PID_FILE}: {e}")


def remove_pid_file() -> None:
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


# ============================================================
# GP LAUNCHER — DETACHED so closing Python does not close GP
# ============================================================
def is_gp_running(window_title: str) -> bool:
    try:
        return len(gw.getWindowsWithTitle(window_title)) > 0
    except Exception:
        return False


def launch_gp_detached(gig_path: str) -> None:
    """Launch GP in its own process group, detached from this Python
    process. On Windows we use 'cmd /c start' which spawns a child that
    immediately re-launches the target and exits — the resulting GP
    process has no parent-child relationship to us."""
    if sys.platform == "win32":
        # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP ensures the target
        # does not share our console and is not killed on console close.
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            ["cmd", "/c", "start", "", gig_path],
            shell=False,
            close_fds=True,
            creationflags=flags,
        )
    else:
        # Unix: double-fork equivalent via setsid
        subprocess.Popen(
            ["xdg-open", gig_path],
            close_fds=True,
            start_new_session=True,
        )


# ============================================================
# OSC HANDLERS
# ============================================================
def make_press_ctrl_g_handler(gp_window_title: str):
    def press_ctrl_g(unused_addr, *args):
        print("\n--- OSC signal /GP/PressCtrlG received ---")
        try:
            gp_windows = gw.getWindowsWithTitle(gp_window_title)
            if not gp_windows:
                print(f"[WARN] Window '{gp_window_title}' not found.")
                return

            gp_win = gp_windows[0]
            print(f"Window found: '{gp_win.title}'")

            if not gp_win.isActive:
                gp_win.activate()
            time.sleep(0.3)

            click_x = gp_win.left + TARGET_X
            click_y = gp_win.top + TARGET_Y

            old_pos = pyautogui.position()
            print(f"Clicking globe at {click_x}, {click_y}...")
            pyautogui.click(click_x, click_y)
            pyautogui.moveTo(old_pos)

            print("[OK] globe clicked")
        except Exception as e:
            print(f"[ERR] click sequence failed: {e}")

        # Reply to GP so the script knows the click landed
        time.sleep(0.5)
        try:
            client = udp_client.SimpleUDPClient("127.0.0.1", GP_REPLY_PORT)
            client.send_message("/GP/ViewReady", 1.0)
        except Exception as e:
            print(f"[ERR] reply send failed: {e}")
        print("-" * 40)
    return press_ctrl_g


def make_on_trace_handler(trace_buffer: list, last_trace_time: list):
    def on_trace(unused_addr, *args):
        msg = args[0] if args else "(empty)"
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] GP-TRACE: {msg}"
        print(line)
        trace_buffer.append(line)
        if len(trace_buffer) > TRACE_BUFFER_SIZE:
            trace_buffer.pop(0)
        last_trace_time[0] = time.time()
    return on_trace


# ============================================================
# MAIN
# ============================================================
def main() -> None:
    print("=" * 50)
    print(" Geisterhand 5.0 — Gig Performer companion")
    print("=" * 50)

    # --- 1. Singleton lock (kills prior Python, leaves GP alone) ---
    kill_old_geisterhand()
    write_pid_file()

    # --- 2. Find the latest .gig file ---
    print("Searching newest .gig file...")
    gig_files = glob.glob(os.path.join(GP_FOLDER, "*.gig"))
    if not gig_files:
        print(f"[ERR] No .gig files found in {GP_FOLDER}")
        return

    latest_gig = max(gig_files, key=os.path.getmtime)
    base_name = os.path.basename(latest_gig)
    gp_window_title = os.path.splitext(base_name)[0]
    print(f"  latest .gig:  {base_name}")
    print(f"  window title: '{gp_window_title}'")

    # --- 3. Launch GP only if not already running ---
    if is_gp_running(gp_window_title):
        print(f"[launcher] GP '{gp_window_title}' is already running — skipping launch.")
        print(f"[launcher] Attaching OSC listener to the existing instance.")
    else:
        print(f"[launcher] Starting GP detached (survives Python exit)...")
        launch_gp_detached(latest_gig)

    print("-" * 50)

    # --- 4. OSC handlers ---
    press_ctrl_g = make_press_ctrl_g_handler(gp_window_title)

    trace_buffer: list = []
    last_trace_time = [time.time()]
    on_trace = make_on_trace_handler(trace_buffer, last_trace_time)

    disp = dispatcher.Dispatcher()
    disp.map("/GP/PressCtrlG", press_ctrl_g)
    disp.map("/GP/Trace", on_trace)

    # --- 5. Bind OSC server ---
    try:
        server = osc_server.ThreadingOSCUDPServer((OSC_IP, OSC_PORT), disp)
    except OSError as e:
        print(f"[ERR] could not bind OSC server on {OSC_IP}:{OSC_PORT}: {e}")
        print("[ERR] likely another Geisterhand is still releasing the port.")
        print("[ERR] wait a few seconds and retry, or check the task list.")
        remove_pid_file()
        return

    print(f"Geisterhand listening on {OSC_IP}:{OSC_PORT}")
    print(f"  /GP/PressCtrlG -> laser-click GP globe button")
    print(f"  /GP/Trace      -> live trace (ring buffer size {TRACE_BUFFER_SIZE})")
    print("-" * 50)
    print("Press Ctrl+C or close this window to stop. GP will keep running.")
    print("-" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[exit] Ctrl+C — shutting down Geisterhand. GP stays alive.")
    finally:
        remove_pid_file()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("\n" + "=" * 50)
        print(" 🚨 FEHLER:")
        traceback.print_exc()
        print("=" * 50)
        remove_pid_file()
        input("\nDrücke ENTER zum Schliessen...")
