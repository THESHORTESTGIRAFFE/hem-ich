# Ingutsheni Central | HEM
## Hospital Equipment Management System

A full-featured, audit-ready Flask web application for tracking, maintaining,
and managing biomedical equipment across a hospital department.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run Production Server
python run_production.py
# → Open http://localhost:8000
```


---

## Demo Credentials

Credentials are not hardcoded. Upon first run, an `admin` account is created with a secure, randomly generated temporary password printed to the terminal. Please change it immediately after login.

---

## Features

### Equipment Registry
- Receive & register with full metadata: name, manufacturer, model, serial number,
  country of origin, donor name, department, location, state, condition
- Auto-generated asset tags: `HEM-YYYY-NNNN`
- Live serial number duplicate check on receive form
- Search & filter by name, tag, serial, state, category
- Bulk CSV import with downloadable template (Chief only)

### Maintenance
- Log Routine / Preventive / Corrective / Calibration / Emergency records
- Record findings, outcome, cost, next due date
- Full maintenance timeline per equipment
- Forward-looking schedule: 30 / 60 / 90 day windows
- Overdue alerts on dashboard and notification bell

### Disposal Workflow
- Technicians/Chiefs submit disposal requests with reason & method
- Chief Engineer approves or rejects — requires explicit sign-off
- Completion modal: final method confirmation + sign-off notes
- Full traceability: request → approval → completion

### Attachments
- Upload PDFs, images, Word/Excel docs against any equipment record
- Download or delete; stored securely in `/uploads/` folder

### Export
- Printable equipment lifecycle report (HTML → browser Print → PDF)
- Includes all metadata, full maintenance history, disposal record, and sign-off block

### Issue Flagging (Interns)
- Interns flag equipment issues with severity (Low / Medium / High)
- Technicians / Chiefs assign, update status, and record resolutions
- Open flags appear on the chief dashboard and notification bell

### Audit Trail (Chief only)
- Every action logged: login, receive, edit, maintenance, disposal, flag, import, password change
- Filter by user, action type, date range
- Paginated, with IP address and timestamp

### User Management (Chief only)
- Add technicians and interns
- Activate / deactivate accounts

---

## Role Permissions

| Action                    | Chief | Technician | Intern |
|---------------------------|-------|------------|--------|
| View equipment            | ✅    | ✅         | ✅     |
| Receive / edit equipment  | ✅    | ✅         | ❌     |
| Bulk CSV import           | ✅    | ❌         | ❌     |
| Log maintenance           | ✅    | ✅         | ❌     |
| Upload attachments        | ✅    | ✅         | ❌     |
| Request disposal          | ✅    | ✅         | ❌     |
| Approve / complete disposal| ✅   | ❌         | ❌     |
| Flag issues               | ✅    | ✅         | ✅     |
| Resolve issues            | ✅    | ✅         | ❌     |
| View audit trail          | ✅    | ❌         | ❌     |
| Manage users              | ✅    | ❌         | ❌     |
| Change own password       | ✅    | ✅         | ✅     |
| View financial data       | ✅    | ✅         | ❌     |

---

## Tech Stack

- **Backend:** Python 3.12 · Flask 3.x · SQLite3 (no ORM)
- **Frontend:** Vanilla HTML/CSS · GSAP 3 animations · Chart.js
- **Auth:** Werkzeug password hashing · Flask sessions · 8-hour timeout
- **No external DB required** — SQLite file auto-created on first run

---

## File Structure

```
hem_inventory/
├── app.py                   # All routes, DB logic, filters
├── hem.db            # SQLite DB (auto-created)
├── uploads/                 # Equipment attachments
├── templates/
│   ├── base.html            # Layout, sidebar, notifications, mobile nav
│   ├── login.html           # Animated split-screen login
│   ├── dashboard.html       # Chief/Technician dashboard
│   ├── intern_dashboard.html
│   ├── equipment_list.html
│   ├── equipment_detail.html
│   ├── receive_equipment.html
│   ├── edit_equipment.html
│   ├── add_maintenance.html
│   ├── maintenance_list.html
│   ├── maintenance_schedule.html
│   ├── disposal_list.html
│   ├── request_disposal.html
│   ├── export_equipment.html
│   ├── import_equipment.html
│   ├── issue_list.html
│   ├── flag_issue.html
│   ├── audit_log.html
│   ├── user_list.html
│   ├── add_user.html
│   └── profile.html
└── README.md
```

---

*Ingutsheni Central Hospital — Health Equipment Maintenance*
