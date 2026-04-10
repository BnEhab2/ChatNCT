"""
run_production.py — ChatNCT Production Launcher (for Render / Cloud)

Starts both servers without SSL (Render handles HTTPS):
  1. Attendance Server (internal port 5001)
  2. Main Server (external PORT from environment)
"""

import subprocess
import sys
import os
import time
import threading

def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    port = int(os.environ.get("PORT", 5000))

    print("\n" + "=" * 60)
    print("ChatNCT — Production Mode")
    print("=" * 60)

    # Start attendance server on internal port 5001 (no SSL)
    print("\nStarting Attendance Server (internal port 5001)...")
    attendance_proc = subprocess.Popen(
        [sys.executable, "-c",
         "import os, sys; "
         f"sys.path.insert(0, r'{project_dir}'); "
         "from mainAgent.web.attendance_server import app; "
         "app.run(host='127.0.0.1', port=5001, debug=False)"
        ],
        cwd=project_dir,
    )

    time.sleep(3)

    # Start main server on PORT (no SSL — Render provides HTTPS)
    print(f"Starting Main Server (port {port})...")

    # Import and run directly (not subprocess) so Render can track the process
    sys.path.insert(0, project_dir)

    # Set the attendance server URL to internal HTTP (no SSL locally)
    os.environ["ATTENDANCE_SERVER_URL"] = "http://127.0.0.1:5001"

    from server import app
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
