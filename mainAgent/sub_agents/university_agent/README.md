# 🎓 University Agent System — Google ADK + SQLite

A multi-agent university management system built with **Google Agent Development Kit (ADK)** and **SQLite**.
Includes a **Face + QR attendance system** for secure, automated attendance tracking.

---

## 📁 Project Structure

```
agent_database/                         ← Parent folder (run adk web here)
└── university_agent/                   ← Agent package
    ├── __init__.py                     ← ADK entry point
    ├── agent.py                        ← Root orchestrator agent
    ├── .env                            ← API key configuration
    ├── university.db                   ← SQLite database (auto-created)
    ├── schema.sql                      ← Full database schema + seed data
    ├── photos/                         ← Student registered photos
    ├── db/
    │   ├── __init__.py
    │   └── database.py                 ← DB connection & init
    ├── tools/
    │   ├── __init__.py
    │   ├── db_tools.py                 ← Dynamic SQL query tools
    │   ├── face_tools.py               ← Face verification & liveness tools
    │   └── attendance_tools.py         ← Attendance session management tools
    ├── sub_agents/
    │   ├── __init__.py
    │   ├── database_agent.py           ← Database sub-agent
    │   ├── face_recognition_agent.py   ← Face verification sub-agent
    │   └── attendance_agent.py         ← Attendance session sub-agent
    └── web/
        ├── attendance_server.py        ← Flask server for Face+QR attendance
        ├── static/
        │   ├── css/
        │   │   ├── instructor.css
        │   │   └── student.css
        │   └── js/
        │       ├── instructor.js
        │       └── student.js
        └── templates/
            ├── instructor.html         ← Instructor dashboard
            └── student.html            ← Student check-in page
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│              USER (ADK Web UI / Flask)            │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│          ROOT AGENT (university_agent)            │
│  Delegates to the appropriate sub-agent          │
└──┬──────────────┬───────────────┬────────────────┘
   │              │               │
   ▼              ▼               ▼
┌──────────┐ ┌──────────────┐ ┌──────────────────┐
│ database │ │ face_recog   │ │ attendance       │
│ _agent   │ │ _agent       │ │ _agent           │
│          │ │              │ │                  │
│ SQL      │ │ webcam       │ │ create/close     │
│ queries  │ │ verify +     │ │ sessions, view   │
│          │ │ liveness     │ │ reports          │
└──────────┘ └──────────────┘ └──────────────────┘
```

---

## 📱 Face + QR Attendance System

### How It Works

1. **Instructor** opens `http://localhost:5000/` → selects course → starts session
2. A **6-character code** and **QR code** are generated
3. **Students** scan QR or enter code → open camera → take selfie
4. System runs **DeepFace verification** against registered photo
5. If verified → attendance recorded automatically as `Present` ✅

### Running the Attendance Server

```bash
cd agent_database
.venv\Scripts\activate
python -m university_agent.web.attendance_server
```

- **Instructor dashboard**: http://localhost:5000/
- **Student check-in**: http://localhost:5000/student?code=XXXXXX

---

## 🗄️ Database Schema (17 tables)

| Table | Description |
|:------|:------------|
| **faculties** | Colleges/faculties |
| **departments** | Academic departments |
| **sections** | Year/term/track groupings |
| **students** | Student records (with `photo_path`) |
| **instructors** | Teaching staff |
| **admins** | System administrators |
| **courses** | Course catalog |
| **course_offerings** | Course-instructor-section assignments |
| **enrollments** | Student-course registrations |
| **grades** | S1, S2, Final, total, letter grade |
| **schedules** | Weekly timetable |
| **classrooms** | Rooms and labs |
| **exams** | Exam schedule |
| **attendance_sessions** | QR attendance sessions (code, expiry) |
| **attendance** | Attendance records (with `verified_by`) |
| **payments** | Financial transactions |
| **student_portals** | Student portal settings |
| **news** | Announcements |

---

## 🚀 How to Run

### 1. Setup

```bash
cd "c:\Users\Mina diaa\OneDrive\Desktop\agent_database"
python -m venv .venv
.venv\Scripts\activate
pip install google-adk deepface flask opencv-python
```

### 2. Configure API Key

Edit `university_agent/.env`:
```
OPENAI_API_KEY=sk-...your-key...
```

### 3. Run ADK Agent

```bash
adk web --no-reload
```

Open http://localhost:8000 → select `university_agent`

### 4. Run Attendance Server (separate terminal)

```bash
python -m university_agent.web.attendance_server
```

---

## 💬 Example Prompts

| Prompt | Agent |
|:-------|:------|
| "Show me info about student 2024001" | database_agent |
| "List all courses" | database_agent |
| "Start attendance for IT101" | attendance_agent |
| "Close attendance session AB3X7K" | attendance_agent |
| "Show attendance report for session AB3X7K" | attendance_agent |
| "Verify student 2024001 identity" | face_recognition_agent |

---

## 🔑 Login Credentials

| ID | Name | Type |
|:---|:-----|:-----|
| 2024001 | Ahmed Mohamed | Student (Year 1) |
| 2024002 | Sara Ali | Student (Year 1) |
| 2024003 | Mohamed Hassan | Student (Year 1) |
| 2023001 | Ali Mahmoud | Student (Year 2) |
| 2022001 | Nour Ahmed | Student (Year 3) |
| 2021001 | Youssef Khaled | Student (Year 4) |
| 1 | Dr. Mohamed Ahmed | Instructor |
