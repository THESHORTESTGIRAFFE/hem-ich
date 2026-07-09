import os
import sys
import socket
import subprocess
from app import create_app
from waitress import serve

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 8.8.8.8 is Google DNS, connection is not actually established but used to resolve local interface IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

def find_free_port(start_port=8080):
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # bind to all interfaces to test if port is free
                s.bind(('0.0.0.0', port))
                return port
            except OSError:
                port += 1
    raise RuntimeError("No free ports found.")

def run_migrations():
    print("------------------------------------------------------------")
    print("🏥 ICH-Wards: Running database migrations/checks...")
    print("------------------------------------------------------------")
    try:
        # Use sys.executable to ensure we run with the current venv's python
        result = subprocess.run([sys.executable, "-m", "flask", "db", "upgrade"], capture_output=True, text=True)
        if result.returncode == 0:
            print("Database is up-to-date.")
            if result.stdout.strip():
                print(result.stdout)
        else:
            print("Warning: Database upgrade returned a non-zero exit code.")
            print(result.stderr)
    except Exception as e:
        print(f"Warning: Could not run migrations: {e}")
    print("------------------------------------------------------------\n")

def main():
    # Load .env file manually if python-dotenv is not handling it automatically
    from dotenv import load_dotenv
    load_dotenv()

    # Run DB upgrade/checks before starting
    run_migrations()

    # Initialize flask application
    app = create_app()

    # Determine port
    default_port = int(os.environ.get("PORT", 8080))
    try:
        port = find_free_port(default_port)
    except Exception as e:
        print(f"Error finding a free port: {e}")
        sys.exit(1)

    local_ip = get_local_ip()

    # Beautiful console banner
    dev_banner = """
        ███████╗███╗   ███╗███╗   ███╗ ██████╗ ██████╗ ██████╗ ██╗  ██╗██╗ ██████╗
        ██╔════╝████╗ ████║████╗ ████║██╔═══██╗██╔══██╗██╔══██╗██║  ██║██║██╔════╝
        █████╗  ██╔████╔██║██╔████╔██║██║   ██║██████╔╝██████╔╝███████║██║██║     
        ██╔══╝  ██║╚██╔╝██║██║╚██╔╝██║██║   ██║██╔══██╗██╔═══╝ ██╔══██║██║██║     
        ███████╗██║ ╚═╝ ██║██║ ╚═╝ ██║╚██████╔╝██║  ██║██║     ██║  ██║██║╚██████╗
        ╚══════╝╚═╝     ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝ ╚═════╝
                                                                                 
        Project   : ICH Wards
        Developer : EMMORPHIC
        Contact   : +263 77 268 8336
        Status    : Production
"""
    banner = f"""
============================================================
🏥  ICH-WARDS MANAGEMENT SYSTEM - PRODUCTION SERVER
============================================================
Status:          RUNNING (via Waitress WSGI)
Local Access:    http://localhost:{port}
Network Access:  http://{local_ip}:{port}
============================================================
ℹ️  Other devices on the same local network can access the 
   system using the "Network Access" URL shown above.

👉 Press Ctrl+C to shut down the server.
============================================================
"""
    print(dev_banner)
    print(banner)

    try:
        serve(app, host='0.0.0.0', port=port, threads=4)
    except KeyboardInterrupt:
        print("\nStopping ICH-Wards server. Goodbye!")

if __name__ == '__main__':
    main()
