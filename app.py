"""
app.py - Hugging Face Spaces Entry Point

On HF Spaces only one port (7860) is exposed externally.
This file starts BOTH servers inside the same container:

  - Attendance server (port 5001) in a background daemon thread
  - Main server (port 7860) in the main thread

The main server proxies attendance API calls to 127.0.0.1:5001
which is reachable internally even though it is not exposed outside.
"""

import os
import sys
import ssl
import time
import socket
import threading

# ── Path setup ────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)


# ── Helpers ───────────────────────────────────────────────────────────

def _wait_for_port(host: str, port: int, timeout: int = 180) -> bool:
    """Poll until a TCP port accepts connections or timeout expires."""
    deadline = time.time() + timeout
    dots = 0
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                print(f"\n[OK] Attendance Server is ready on port {port}!")
                return True
        except (ConnectionRefusedError, OSError):
            dots += 1
            print(f"\r[...] Waiting for Attendance Server{'.' * (dots % 4)}   ",
                  end="", flush=True)
            time.sleep(3)
    return False


# ── Attendance Server Thread ──────────────────────────────────────────

def _run_attendance_server():
    """Load and start the attendance Flask app on port 5001 with SSL."""
    try:
        # Heavy imports happen here (TensorFlow / DeepFace)
        from mainAgent.web.attendance_server import app as att_app
        from mainAgent.web.generate_cert import generate_self_signed_cert

        cert_dir = os.path.join(PROJECT_DIR, "mainAgent", "web")
        cert_path, key_path = generate_self_signed_cert(cert_dir)

        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(cert_path, key_path)

        print("[INFO] Attendance Server starting on port 5001...")
        att_app.run(host="0.0.0.0", port=5001, ssl_context=ssl_ctx,
                    debug=False, use_reloader=False)
    except Exception as exc:
        print(f"[ERROR] Attendance Server failed to start: {exc}")


# ── Start Attendance Server in background ─────────────────────────────
print("[INFO] Launching Attendance Server thread (loading AI models)...")
_att_thread = threading.Thread(target=_run_attendance_server, daemon=True)
_att_thread.start()

# Wait until port 5001 is actually accepting connections (up to 3 min)
_ready = _wait_for_port("127.0.0.1", 5001, timeout=180)
if not _ready:
    print("\n[WARN] Attendance Server did not become ready in time."
          " Main server will start anyway — attendance may fail on first request.")

# ── Main Server ───────────────────────────────────────────────────────
print("[INFO] Starting Main Server...")

from server import app  # noqa: E402  (import after path setup)

PORT = int(os.getenv("PORT", 7860))
print(f"[INFO] Main Server listening on port {PORT}")

app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
