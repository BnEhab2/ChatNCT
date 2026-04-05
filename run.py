"""
run.py — ChatNCT Unified Launcher

Starts both servers:
  1. Attendance Server (port 5001) — Face + QR verification
  2. Main Server (port 5000) — API middleware + Frontend
"""

import subprocess
import sys
import os
import time
import signal

def main():
    print("\n" + "=" * 60)
    print("🎓 ChatNCT — University AI System")
    print("=" * 60)
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Start attendance server on port 5001
    print("\n📱 Starting Attendance Server (port 5001)...")
    attendance_proc = subprocess.Popen(
        [sys.executable, "-c", 
         "import os, sys; "
         f"sys.path.insert(0, r'{project_dir}'); "
         "os.chdir(r'" + os.path.join(project_dir, "mainAgent", "sub_agents", "university_agent") + "'); "
         "from web.attendance_server import app; "
         "import ssl; "
         "from web.generate_cert import generate_self_signed_cert; "
         "cert_dir = r'" + os.path.join(project_dir, "mainAgent", "sub_agents", "university_agent", "web") + "'; "
         "cert_path, key_path = generate_self_signed_cert(cert_dir); "
         "ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); "
         "ssl_ctx.load_cert_chain(cert_path, key_path); "
         "app.run(host='0.0.0.0', port=5001, debug=False, ssl_context=ssl_ctx)"
        ],
        cwd=project_dir,
    )
    
    time.sleep(2)
    
    # Start main server on port 5000
    print("🚀 Starting Main Server (port 5000)...")
    main_proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=project_dir,
    )
    
    print("\n" + "=" * 60)
    print("✅ Both servers are running!")
    print(f"  🌐 Frontend:    http://localhost:5000/")
    print(f"  🤖 Chat API:    http://localhost:5000/api/chat")
    print(f"  📱 Attendance:  https://localhost:5001/")
    print("=" * 60)
    print("\nPress Ctrl+C to stop all servers.\n")
    
    try:
        main_proc.wait()
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down servers...")
        attendance_proc.terminate()
        main_proc.terminate()
        attendance_proc.wait()
        main_proc.wait()
        print("✅ All servers stopped.")

if __name__ == "__main__":
    main()
