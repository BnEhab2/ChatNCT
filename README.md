# ChatNCT – AI-Powered Assistant for NCT University

## Overview

**ChatNCT** is an AI-powered platform designed for students and instructors at NCT University. It enhances the educational experience through an intelligent chat system that supports learning, academic assistance, and automated attendance tracking.

---

## Features

### Student Portal

* Secure login باستخدام university email
* AI Chat Assistant capable of:

  * Explaining course materials using Retrieval-Augmented Generation (RAG)
  * Generating quizzes
  * Summarizing content
  * Writing and explaining code
  * Answering academic and administrative questions
  * Generating prompts using CoSTAR methodology
* Q&A system for student affairs
* Attendance system:

  * QR Code scanning
  * Face verification with liveness detection
* Chat history with saved sessions

---

### Instructor Portal

* Instructor authentication
* Create and manage attendance sessions
* Generate dynamic QR codes for attendance
* Close sessions securely
* Export attendance reports as CSV files

---

## System Architecture

* **Frontend:** HTML, CSS, JavaScript
* **Backend:** Flask (Python)
* **Database:** Supabase (PostgreSQL)
* **AI Integration:**

  * OpenAI API (chat, RAG)
  * Google Gemini API (search, code generation)
* **Framework:** Google ADK

---

## Database Design

The system is built on a structured relational database including:

* users
* students
* instructors
* courses
* enrollment
* attendance
* attendance_sessions
* messages
* sessions

---

## Authentication

* No manual sign-up required
* Students and instructors are pre-registered in the system
* Login credentials:

  * University Email
  * National ID (as password)

---

## Attendance Workflow

1. Instructor creates an attendance session
2. A dynamic QR code is generated
3. Students:

   * Scan the QR code
   * Complete face verification with liveness detection
4. Attendance is recorded automatically in the database
5. Instructor exports attendance as CSV

---

## Installation

```bash id="a1b2c3"
git clone https://github.com/your-repo/chatnct.git
cd chatnct
pip install -r requirements.txt
```

---

## Run the Project

```bash id="d4e5f6"
python app.py
```

---

## Team

NCT University Students

---

## License

This project is developed for educational purposes.
