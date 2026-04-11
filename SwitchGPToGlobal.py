import os
import glob
import sys
import traceback
import time
import pygetwindow as gw
import pyautogui
from pythonosc import dispatcher, osc_server, udp_client

# ==========================================
# 1. KONFIGURATION & AUTO-LAUNCHER
# ==========================================
# Deine gemessenen Koordinaten vom Finder:
TARGET_X = 726
TARGET_Y = 73

gp_folder = r"C:\Users\marti\OneDrive\Keyboard\GigPerformer"
gp_window_title = "Gig Performer" # Fallback

try:
    print("Suche nach der aktuellsten .gig Datei...")
    gig_files = glob.glob(os.path.join(gp_folder, "*.gig"))
    if gig_files:
        latest_gig = max(gig_files, key=os.path.getmtime)
        base_name = os.path.basename(latest_gig)
        gp_window_title = os.path.splitext(base_name)[0] 
        print(f"--> Lade: {base_name}\n--> Ziel-Fenster: '{gp_window_title}'")
        os.startfile(latest_gig)
    print("-" * 40)

    # ==========================================
    # 2. DIE GEISTERHAND (OSC CALLBACK)
    # ==========================================
    def press_ctrl_g(unused_addr, args):
        print("\n--- OSC-Signal erhalten! ---")
        try:
            # Fenster suchen
            gp_windows = gw.getWindowsWithTitle(gp_window_title)
            if gp_windows:
                gp_win = gp_windows[0]
                print(f"Echtes Fenster gefunden: '{gp_win.title}'")
                
                # 1. Fenster aktivieren
                if not gp_win.isActive:
                    gp_win.activate()
                time.sleep(0.3)

                # 2. Klick-Position berechnen (Relativ zum Fenster)
                click_x = gp_win.left + TARGET_X
                click_y = gp_win.top + TARGET_Y
                
                # 3. Maus-Aktion (schnell und präzise)
                old_pos = pyautogui.position()
                print(f"Klicke Weltkugel bei {click_x}, {click_y}...")
                pyautogui.click(click_x, click_y)
                pyautogui.moveTo(old_pos) # Maus sofort zurückbewegen
                
                print("[OK] Weltkugel geklickt!")
            else:
                print(f"[WARNUNG] Fenster '{gp_window_title}' nicht gefunden!")
        except Exception as e:
            print(f"[FEHLER] Klick-Sequenz fehlgeschlagen: {e}")

        # 4. Bestätigung an GP senden
        time.sleep(0.5)
        client = udp_client.SimpleUDPClient("127.0.0.1", 54344)
        client.send_message("/GP/ViewReady", 1.0)
        print("----------------------------\n")

    # ==========================================
    # 3. CRASH-TRACE RECEIVER
    # ==========================================
    # Ring buffer holding the last N traces so a post-crash dump shows
    # the sequence leading up to silence. GP calls Trace(msg) which,
    # when CrashDebugMode=true, emits /GP/Trace to this server.
    TRACE_BUFFER_SIZE = 50
    trace_buffer = []
    last_trace_time = [time.time()]  # list so the closure can mutate

    def on_trace(unused_addr, *args):
        msg = args[0] if args else "(empty)"
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] GP-TRACE: {msg}"
        print(line)
        trace_buffer.append(line)
        if len(trace_buffer) > TRACE_BUFFER_SIZE:
            trace_buffer.pop(0)
        last_trace_time[0] = time.time()

    # OSC Server Setup
    disp = dispatcher.Dispatcher()
    disp.map("/GP/PressCtrlG", press_ctrl_g)
    disp.map("/GP/Trace", on_trace)
    server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 8000), disp)
    print("Geisterhand 4.1 (Laser-Klick + Crash-Trace) lauscht auf Port 8000.")
    print(f"  /GP/PressCtrlG -> Weltkugel-Klick auf Gig Performer")
    print(f"  /GP/Trace      -> Live-Trace (ring buffer size {TRACE_BUFFER_SIZE})")
    print("-" * 40)
    server.serve_forever()

except Exception as e:
    print("\n" + "="*50)
    print(" 🚨 FEHLER BEIM START:")
    traceback.print_exc()
    print("="*50)
    input("\nDrücke ENTER, um dieses Fenster zu schließen...")
