"""
run.py - Project Entry Point (Start Here)

This is the MAIN file you run to start the entire ChatNCT system.
It launches TWO servers simultaneously:

  1. Attendance Server (port 5001) - Handles face recognition & QR verification
     Runs silently in the background with no console output.

  2. Main Server (port 5000) - Handles everything else:
     Chat API, login, frontend pages, instructor panel, etc.

Usage:
  python run.py

After running, you'll see two URLs:
  - Local:   https://localhost:5000/      (use this on your computer)
  - Network: https://192.168.x.x:5000/    (use this on your phone/other devices)
"""

import subprocess
import sys
import os
import time
import socket
import warnings

# Suppress the noisy "InsecureRequestWarning" from urllib3.
# This happens because our attendance server uses a self-signed SSL certificate.
# The warning is harmless but floods the terminal.
warnings.filterwarnings("ignore", message="Unverified HTTPS request")


def get_lan_ip():
    """
    Find this computer's IP address on the local network.
    This is needed so other devices (like phones) can connect.
    
    How it works: Opens a connection to Google's DNS (8.8.8.8)
    and checks which local IP address was used.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    # Get the folder where this file lives (the project root)
    project_dir = os.path.dirname(os.path.abspath(__file__))

    # ── Server 1: Attendance (Face Recognition + QR) ──────────
    # Runs as a separate process so it doesn't block the main server.
    # Uses SSL (HTTPS) because mobile cameras require a secure connection.
    # stdout/stderr are suppressed to keep the console clean.
    attendance_proc = subprocess.Popen(
        [sys.executable, "-c", 
         "import os, sys; "
         f"sys.path.insert(0, r'{project_dir}'); "
         "from mainAgent.web.attendance_server import app; "
         "import ssl; "
         "from mainAgent.web.generate_cert import generate_self_signed_cert; "
         "cert_dir = r'" + os.path.join(project_dir, "mainAgent", "web") + "'; "
         "cert_path, key_path = generate_self_signed_cert(cert_dir); "
         "ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); "
         "ssl_ctx.load_cert_chain(cert_path, key_path); "
         "app.run(host='0.0.0.0', port=5001, debug=False, ssl_context=ssl_ctx)"
        ],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Give the attendance server 2 seconds to start up
    time.sleep(2)

    # ── Server 2: Main (API + Frontend) ───────────────────────
    # This is the server users interact with directly.
    main_proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=project_dir,
    )

    # Print the URLs users can use to access the app
    lan_ip = get_lan_ip()
    print(f"\n  Local:   https://localhost:5000/")
    print(f"  Network: https://{lan_ip}:5000/\n")

    # Keep running until the user presses Ctrl+C
    try:
        main_proc.wait()
    except KeyboardInterrupt:
        # Gracefully stop both servers when user presses Ctrl+C
        attendance_proc.terminate()
        main_proc.terminate()
        attendance_proc.wait()
        main_proc.wait()


if __name__ == "__main__":
    main()
