# Ingutsheni Central | HEM — Deployment Guide

## Requirements

- Python 3.10 or newer
- A Windows or Linux machine on the hospital network
- No internet required after initial install

---

## 1. Install Python dependencies

Open a terminal in the project folder and run:

```bash
pip install -r requirements.txt
```

This installs Flask, Werkzeug, and **Waitress** — a pure-Python production server that
lets every machine on the hospital LAN connect without any extra configuration.

---

## 2. First-time setup

Run the setup script **once** before starting the server:

```bash
python setup.py
```

It will:
- Ask for host, port, and storage paths (press Enter to accept defaults)
- Generate a cryptographically strong `SECRET_KEY`
- Write a `.env` configuration file
- Create the `uploads/` directory
- Initialise the database and **print a one-time admin password to the screen**

```
============================================================
  HEM — FIRST RUN SETUP
============================================================
  Username : admin
  Password : xK9mP2_vQrLt4Nw

  ⚠  Save this password now. It will NOT be shown again.
  Change it immediately via Profile → Change Password.
============================================================
```

**Write this down or copy it before continuing.** It is never stored in code.

---

## 3. Start the server

```bash
python serve.py
```

Output will show the address other machines can use:

```
============================================================
  Ingutsheni Central | HEM
  Health Equipment Maintenance System
============================================================
  Server  : Waitress (production WSGI)
  Address : http://0.0.0.0:8000
  Threads : 4
  DB      : /opt/hem/hem.db
============================================================
  Access from other machines:
  → http://192.168.1.45:8000
  Press Ctrl+C to stop.
============================================================
```

Any machine on the same network can open `http://192.168.1.45:8000` in a browser.

---

## 4. First login & setup

1. Open the URL in a browser
2. Log in with username `admin` and the temporary password
3. Go to **👤 Profile → Change Password** immediately
4. Go to **👥 Users → Add User** to create accounts for technicians and interns

---

## Running automatically on startup

### Windows (Task Scheduler)

1. Open **Task Scheduler** → Create Basic Task
2. Name: `HEM Server`
3. Trigger: **When the computer starts**
4. Action: **Start a program**
   - Program: `python`
   - Arguments: `serve.py`
   - Start in: `C:\path\to\hem_inventory`
5. Check **"Run whether user is logged on or not"**
6. Check **"Run with highest privileges"**

### Linux / Ubuntu (systemd)

Create `/etc/systemd/system/hem.service`:

```ini
[Unit]
Description=Ingutsheni Central HEM Server
After=network.target

[Service]
Type=simple
User=hem
WorkingDirectory=/opt/hem
ExecStart=/usr/bin/python3 serve.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hem
sudo systemctl start hem
sudo systemctl status hem
```

### Linux (simple background process)

```bash
nohup python serve.py > hem.log 2>&1 &
echo $! > hem.pid    # saves process ID so you can kill it later
```

To stop: `kill $(cat hem.pid)`

---

## Configuration reference (.env)

| Variable        | Default                | Description                               |
|----------------|------------------------|-------------------------------------------|
| `SECRET_KEY`   | *(required)*           | Flask session encryption key              |
| `HOST`         | `0.0.0.0`              | `0.0.0.0` = all interfaces, LAN-accessible|
| `PORT`         | `8000`                 | TCP port the server listens on            |
| `THREADS`      | `4`                    | Concurrent request threads                |
| `DATABASE_PATH`| `./hem.db`      | SQLite database file path                 |
| `UPLOAD_FOLDER`| `./uploads/`           | Attachment storage directory              |
| `SESSION_HOURS`| `8`                    | Idle session timeout in hours             |

---

## Changing the port

Edit `.env`:
```
PORT=9000
```
Then restart `serve.py`. Users access the app at `http://<ip>:9000`.

---

## Rotating the secret key

Re-running `python setup.py` generates a new `SECRET_KEY`. This **invalidates all
active sessions** — every user will be logged out. Do this if you suspect the
`.env` file has been compromised.

---

## Backups

Back up these two things regularly:

```
hem.db    # All equipment, maintenance, disposal, and audit records
uploads/         # All uploaded attachments
```

A simple daily copy to a network drive or USB is sufficient.

---

## Security checklist before going live

- [ ] Changed the default admin password via Profile → Change Password
- [ ] Created individual accounts for each staff member (no shared logins)
- [ ] Confirmed `.env` is not accessible via the browser (it is server-side only)
- [ ] Scheduled regular backups of `hem.db` and `uploads/`
- [ ] Confirmed the server machine has OS-level firewall limiting port 8000 to LAN only
