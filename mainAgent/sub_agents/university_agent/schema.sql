-- =====================================================
-- 🎓 SIS University System - Complete Database Schema
-- نظام إدارة الجامعة - سكيما قاعدة البيانات الكاملة
-- =====================================================
-- Based on Final ERD with All Courses Included
-- =====================================================

-- =====================================================
-- 🏛️ ENTITY: FACULTIES (الكليات)
-- =====================================================
CREATE TABLE IF NOT EXISTS faculties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_ar TEXT,
    code TEXT UNIQUE,
    dean_name TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Insert Faculties: Industry and Energy, Health Sciences
INSERT OR IGNORE INTO
    faculties (id, name, name_ar, code)
VALUES (
        1,
        'Faculty of Industry and Energy',
        'كلية الصناعة والطاقة',
        'FIE'
    );

INSERT OR IGNORE INTO
    faculties (id, name, name_ar, code)
VALUES (
        2,
        'Faculty of Health Sciences',
        'كلية العلوم الصحية',
        'FHS'
    );

-- =====================================================
-- 🏢 ENTITY: DEPARTMENTS (الأقسام)
-- =====================================================
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_ar TEXT,
    code TEXT UNIQUE,
    faculty_id INTEGER,
    head_name TEXT,
    FOREIGN KEY (faculty_id) REFERENCES faculties (id)
);

-- Insert departments: IT (Faculty 1) and Prosthetics (Faculty 2)
INSERT OR IGNORE INTO
    departments (
        id,
        name,
        name_ar,
        code,
        faculty_id
    )
VALUES (
        1,
        'Information Technology',
        'تكنولوجيا المعلومات',
        'IT',
        1
    );

INSERT OR IGNORE INTO
    departments (
        id,
        name,
        name_ar,
        code,
        faculty_id
    )
VALUES (
        2,
        'Prosthetics',
        'الأطراف الصناعية',
        'PROS',
        2
    );

INSERT OR IGNORE INTO
    departments (
        id,
        name,
        name_ar,
        code,
        faculty_id
    )
VALUES (
        3,
        'Mechatronics',
        'الميكاترونكس',
        'MECH',
        1
    );

-- =====================================================
-- 🧱 ENTITY: SECTION (الشعب)
-- =====================================================
CREATE TABLE IF NOT EXISTS sections (
    section_id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL, -- 1, 2, 3, 4
    term INTEGER NOT NULL, -- 1 or 2
    track TEXT NOT NULL, -- SW / Network / General
    section_number INTEGER NOT NULL, -- Section number (1, 2, 3...)
    UNIQUE (
        year,
        term,
        track,
        section_number
    )
);

-- =====================================================
-- 🧱 ENTITY: STUDENT (الطلاب)
-- =====================================================
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_ar TEXT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL DEFAULT '123456',
    national_id TEXT UNIQUE,
    department_id INTEGER DEFAULT 1,
    level INTEGER DEFAULT 1 CHECK (level BETWEEN 1 AND 4),
    semester INTEGER DEFAULT 1 CHECK (semester IN (1, 2)),
    seat_number INTEGER DEFAULT 0,
    enrollment_year TEXT,
    phone TEXT,
    address TEXT,
    birth_date TEXT,
    gender TEXT CHECK (gender IN ('M', 'F')),
    balance REAL DEFAULT 0,
    gpa REAL DEFAULT 0,
    track TEXT DEFAULT 'General' CHECK (
        track IN ('SW', 'Network', 'General')
    ),
    section_id INTEGER,
    status TEXT DEFAULT 'active' CHECK (
        status IN (
            'active',
            'graduated',
            'suspended'
        )
    ),
    photo_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    FOREIGN KEY (section_id) REFERENCES sections (section_id)
);

-- =====================================================
-- 🧱 ENTITY: COURSE (المواد الدراسية)
-- =====================================================
CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name TEXT NOT NULL,
    course_code TEXT UNIQUE,
    year INTEGER NOT NULL CHECK (year BETWEEN 1 AND 4),
    term INTEGER NOT NULL CHECK (term IN (1, 2)),
    track TEXT NOT NULL CHECK (
        track IN ('SW', 'Network', 'General')
    ),
    credit_hours INTEGER DEFAULT 3,
    description TEXT,
    is_active INTEGER DEFAULT 1
);

-- =====================================================
-- 🧱 ENTITY: INSTRUCTOR (المحاضرين / الدكاترة)
-- =====================================================
CREATE TABLE IF NOT EXISTS instructors (
    instructor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    password TEXT DEFAULT '123456',
    phone TEXT,
    specialization TEXT,
    title TEXT, -- Dr., Prof., Eng.
    is_active INTEGER DEFAULT 1
);

-- Sample Instructor
INSERT OR IGNORE INTO
    instructors (
        instructor_id,
        name,
        email,
        password,
        specialization,
        title,
        is_active
    )
VALUES (
        1,
        'Dr. Mohamed Ahmed',
        'dr.mohamed@university.edu',
        '123456',
        'Software Engineering',
        'Dr.',
        1
    );

-- =====================================================
-- 🧱 ENTITY: CLASSROOM (القاعات والمعامل)
-- =====================================================
CREATE TABLE IF NOT EXISTS classrooms (
    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_code TEXT UNIQUE NOT NULL,
    capacity INTEGER DEFAULT 50,
    building TEXT,
    room_type TEXT DEFAULT 'Hall' CHECK (
        room_type IN ('Hall', 'Lab', 'Lecture Room')
    )
);

-- =====================================================
-- 🧱 ENTITY: COURSE_OFFERING (تعيين المادة للدكتور والشعبة)
-- =====================================================
CREATE TABLE IF NOT EXISTS course_offerings (
    offering_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    instructor_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL, -- e.g., "2024-2025"
    semester INTEGER NOT NULL CHECK (semester IN (1, 2)),
    FOREIGN KEY (course_id) REFERENCES courses (course_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors (instructor_id),
    FOREIGN KEY (section_id) REFERENCES sections (section_id)
);

-- Sample Sections
INSERT OR IGNORE INTO
    sections (
        section_id,
        year,
        term,
        track,
        section_number
    )
VALUES (1, 1, 1, 'General', 1);

INSERT OR IGNORE INTO
    sections (
        section_id,
        year,
        term,
        track,
        section_number
    )
VALUES (2, 1, 1, 'General', 2);

-- Sample Course Offerings (Assign Dr. Mohamed to first 3 courses)
INSERT OR IGNORE INTO
    course_offerings (
        offering_id,
        course_id,
        instructor_id,
        section_id,
        academic_year,
        semester
    )
VALUES (1, 1, 1, 1, '2024-2025', 1);

INSERT OR IGNORE INTO
    course_offerings (
        offering_id,
        course_id,
        instructor_id,
        section_id,
        academic_year,
        semester
    )
VALUES (2, 2, 1, 1, '2024-2025', 1);

INSERT OR IGNORE INTO
    course_offerings (
        offering_id,
        course_id,
        instructor_id,
        section_id,
        academic_year,
        semester
    )
VALUES (3, 3, 1, 1, '2024-2025', 1);

-- =====================================================
-- 🧱 ENTITY: SCHEDULE (الجدول الدراسي)
-- =====================================================
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    offering_id INTEGER NOT NULL,
    day TEXT NOT NULL CHECK (
        day IN (
            'Saturday',
            'Sunday',
            'Monday',
            'Tuesday',
            'Wednesday',
            'Thursday'
        )
    ),
    time TEXT NOT NULL, -- e.g., "08:00-09:30"
    room_id INTEGER,
    FOREIGN KEY (offering_id) REFERENCES course_offerings (offering_id),
    FOREIGN KEY (room_id) REFERENCES classrooms (room_id)
);

-- =====================================================
-- 🧱 ENTITY: ENROLLMENT (تسجيل المواد)
-- =====================================================
CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    academic_year TEXT NOT NULL,
    semester INTEGER NOT NULL CHECK (semester IN (1, 2)),
    status TEXT DEFAULT 'Enrolled' CHECK (
        status IN (
            'Enrolled',
            'Dropped',
            'Completed',
            'Failed'
        )
    ),
    enrollment_date TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students (id),
    FOREIGN KEY (course_id) REFERENCES courses (course_id),
    UNIQUE (
        student_id,
        course_id,
        academic_year,
        semester
    )
);

-- Sample Students (Year 1 = 2024xxx IDs)
INSERT OR IGNORE INTO
    students (
        id,
        name,
        email,
        password,
        department_id,
        level
    )
VALUES (
        2024001,
        'Ahmed Mohamed',
        'ahmed@university.edu',
        '123456',
        1,
        1
    );

INSERT OR IGNORE INTO
    students (
        id,
        name,
        email,
        password,
        department_id,
        level
    )
VALUES (
        2024002,
        'Sara Ali',
        'sara@university.edu',
        '123456',
        1,
        1
    );

INSERT OR IGNORE INTO
    students (
        id,
        name,
        email,
        password,
        department_id,
        level
    )
VALUES (
        2024003,
        'Mohamed Hassan',
        'mohamed@university.edu',
        '123456',
        1,
        1
    );

-- Year 2 Student (2023xxx ID)
INSERT OR IGNORE INTO
    students (
        id,
        name,
        email,
        password,
        department_id,
        level
    )
VALUES (
        2023001,
        'Ali Mahmoud',
        'ali@university.edu',
        '123456',
        1,
        2
    );

-- Year 3 Student (2022xxx ID)
INSERT OR IGNORE INTO
    students (
        id,
        name,
        email,
        password,
        department_id,
        level
    )
VALUES (
        2022001,
        'Nour Ahmed',
        'nour@university.edu',
        '123456',
        1,
        3
    );

-- Year 4 Student (2021xxx ID)
INSERT OR IGNORE INTO
    students (
        id,
        name,
        email,
        password,
        department_id,
        level
    )
VALUES (
        2021001,
        'Youssef Khaled',
        'youssef@university.edu',
        '123456',
        1,
        4
    );

-- Sample Enrollments (Students enrolled in courses)
INSERT OR IGNORE INTO
    enrollments (
        enrollment_id,
        student_id,
        course_id,
        academic_year,
        semester,
        status
    )
VALUES (
        1,
        2024001,
        1,
        '2024-2025',
        1,
        'Enrolled'
    );

INSERT OR IGNORE INTO
    enrollments (
        enrollment_id,
        student_id,
        course_id,
        academic_year,
        semester,
        status
    )
VALUES (
        2,
        2024001,
        2,
        '2024-2025',
        1,
        'Enrolled'
    );

INSERT OR IGNORE INTO
    enrollments (
        enrollment_id,
        student_id,
        course_id,
        academic_year,
        semester,
        status
    )
VALUES (
        3,
        2024002,
        1,
        '2024-2025',
        1,
        'Enrolled'
    );

INSERT OR IGNORE INTO
    enrollments (
        enrollment_id,
        student_id,
        course_id,
        academic_year,
        semester,
        status
    )
VALUES (
        4,
        2024002,
        2,
        '2024-2025',
        1,
        'Enrolled'
    );

INSERT OR IGNORE INTO
    enrollments (
        enrollment_id,
        student_id,
        course_id,
        academic_year,
        semester,
        status
    )
VALUES (
        5,
        2024003,
        1,
        '2024-2025',
        1,
        'Enrolled'
    );

INSERT OR IGNORE INTO
    enrollments (
        enrollment_id,
        student_id,
        course_id,
        academic_year,
        semester,
        status
    )
VALUES (
        6,
        2024003,
        3,
        '2024-2025',
        1,
        'Enrolled'
    );

-- Year 2 student enrollments
INSERT OR IGNORE INTO
    enrollments (
        enrollment_id,
        student_id,
        course_id,
        academic_year,
        semester,
        status
    )
VALUES (
        7,
        2023001,
        4,
        '2024-2025',
        1,
        'Enrolled'
    );

-- =====================================================
-- 🧱 ENTITY: GRADE (الدرجات - S1, S2, Final, Total)
-- =====================================================
CREATE TABLE IF NOT EXISTS grades (
    grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER UNIQUE NOT NULL,
    s1 REAL DEFAULT 0, -- درجة السعي الأول (Midterm 1)
    s2 REAL DEFAULT 0, -- درجة السعي الثاني (Midterm 2)
    final_exam REAL DEFAULT 0, -- درجة الفاينال
    total REAL DEFAULT 0, -- المجموع الكلي
    letter_grade TEXT, -- A+, A, B+, B, C+, C, D+, D, F
    grade_points REAL DEFAULT 0, -- GPA points
    mercy_applied INTEGER DEFAULT 0, -- هل تم تطبيق الرأفة
    mercy_points REAL DEFAULT 0, -- درجات الرأفة المضافة
    updated_at TEXT,
    FOREIGN KEY (enrollment_id) REFERENCES enrollments (enrollment_id)
);

-- =====================================================
-- 🧱 ENTITY: EXAM (جدول الامتحانات - S1, S2, Final)
-- =====================================================
CREATE TABLE IF NOT EXISTS exams (
    exam_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    exam_type TEXT NOT NULL CHECK (
        exam_type IN (
            'S1',
            'S2',
            'Final',
            'Practical'
        )
    ),
    exam_date DATE NOT NULL,
    exam_time TEXT, -- e.g., "09:00"
    duration_minutes INTEGER DEFAULT 120,
    room_id INTEGER,
    academic_year TEXT,
    semester INTEGER,
    FOREIGN KEY (course_id) REFERENCES courses (course_id),
    FOREIGN KEY (room_id) REFERENCES classrooms (room_id)
);

-- =====================================================
-- 🧱 ENTITY: ATTENDANCE_SESSIONS (جلسات الحضور)
-- =====================================================
CREATE TABLE IF NOT EXISTS attendance_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_code TEXT UNIQUE NOT NULL,
    course_id INTEGER NOT NULL,
    instructor_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (course_id) REFERENCES courses (course_id),
    FOREIGN KEY (instructor_id) REFERENCES instructors (instructor_id)
);

-- =====================================================
-- 🧱 ENTITY: ATTENDANCE (الحضور والغياب)
-- =====================================================
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    session_id INTEGER,
    date DATE NOT NULL,
    status TEXT DEFAULT 'Present' CHECK (
        status IN (
            'Present',
            'Absent',
            'Late',
            'Excused'
        )
    ),
    verified_by TEXT DEFAULT 'manual' CHECK (
        verified_by IN ('face', 'manual', 'qr')
    ),
    notes TEXT,
    FOREIGN KEY (student_id) REFERENCES students (id),
    FOREIGN KEY (course_id) REFERENCES courses (course_id),
    FOREIGN KEY (session_id) REFERENCES attendance_sessions (session_id)
);

-- =====================================================
-- 🧱 ENTITY: PAYMENT (المدفوعات)
-- =====================================================
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    method TEXT CHECK (
        method IN (
            'Cash',
            'Card',
            'Bank Transfer',
            'Online'
        )
    ),
    date DATE DEFAULT CURRENT_DATE,
    status TEXT DEFAULT 'Pending' CHECK (
        status IN (
            'Pending',
            'Paid',
            'Failed',
            'Refunded'
        )
    ),
    description TEXT,
    receipt_number TEXT UNIQUE,
    FOREIGN KEY (student_id) REFERENCES students (student_id)
);

-- =====================================================
-- 🧱 ENTITY: STUDENT_PORTAL (بوابة الطالب)
-- =====================================================
CREATE TABLE IF NOT EXISTS student_portals (
    portal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER UNIQUE NOT NULL,
    last_login DATETIME,
    notifications TEXT, -- JSON array of notifications
    settings TEXT, -- JSON settings
    FOREIGN KEY (student_id) REFERENCES students (student_id)
);

-- =====================================================
-- 🧱 ENTITY: NEWS (الأخبار والإعلانات)
-- =====================================================
CREATE TABLE IF NOT EXISTS news (
    news_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    date DATE DEFAULT CURRENT_DATE,
    posted_by TEXT,
    category TEXT DEFAULT 'General',
    is_pinned INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);

-- =====================================================
-- 🧱 ENTITY: ADMIN (المسؤولين)
-- =====================================================
CREATE TABLE IF NOT EXISTS admins (
    admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    full_name TEXT,
    email TEXT,
    role TEXT DEFAULT 'Admin' CHECK (
        role IN (
            'Admin',
            'Registrar',
            'Instructor',
            'Control'
        )
    ),
    permissions TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 🔧 INDEXES FOR PERFORMANCE
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_students_email ON students (email);

CREATE INDEX IF NOT EXISTS idx_students_national_id ON students (national_id);

CREATE INDEX IF NOT EXISTS idx_students_section ON students (section_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments (student_id);

CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments (course_id);

CREATE INDEX IF NOT EXISTS idx_grades_enrollment ON grades (enrollment_id);

CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance (student_id);

CREATE INDEX IF NOT EXISTS idx_attendance_course ON attendance (course_id);

CREATE INDEX IF NOT EXISTS idx_payments_student ON payments (student_id);

CREATE INDEX IF NOT EXISTS idx_schedules_offering ON schedules (offering_id);

CREATE INDEX IF NOT EXISTS idx_exams_course ON exams (course_id);

CREATE INDEX IF NOT EXISTS idx_attendance_session ON attendance (session_id);

CREATE INDEX IF NOT EXISTS idx_att_sessions_code ON attendance_sessions (session_code);

CREATE INDEX IF NOT EXISTS idx_att_sessions_active ON attendance_sessions (is_active);

-- =====================================================
-- 📚 INSERT ALL COURSES DATA
-- =====================================================

-- =====================================================
-- 🔵 1st Year — Term 1 (General Track)
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'Physics I',
        'PHY101',
        1,
        1,
        'General',
        3
    ),
    (
        'IT Essentials',
        'IT101',
        1,
        1,
        'General',
        3
    ),
    (
        'Python Programming',
        'PY101',
        1,
        1,
        'General',
        3
    ),
    (
        'Introduction to Cyber Security',
        'CYB101',
        1,
        1,
        'General',
        3
    ),
    (
        'Mathematics I',
        'MATH101',
        1,
        1,
        'General',
        3
    ),
    (
        'English I',
        'ENG101',
        1,
        1,
        'General',
        3
    );

-- =====================================================
-- 🔵 1st Year — Term 2 (General Track)
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'MS Office',
        'OFF101',
        1,
        2,
        'General',
        3
    ),
    (
        'Introduction to IoT',
        'IOT101',
        1,
        2,
        'General',
        3
    ),
    (
        'Mathematics II',
        'MATH102',
        1,
        2,
        'General',
        3
    ),
    (
        'Cyber Security Essentials',
        'CYB102',
        1,
        2,
        'General',
        3
    ),
    (
        'Programming Essentials in C',
        'C101',
        1,
        2,
        'General',
        3
    ),
    (
        'Technical English II',
        'ENG102',
        1,
        2,
        'General',
        3
    );

-- =====================================================
-- 🟧 2nd Year — Term 1 (General Track)
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'Linux Operating System',
        'LIN201',
        2,
        1,
        'General',
        3
    ),
    (
        'Introduction to Database',
        'DB201',
        2,
        1,
        'General',
        3
    ),
    (
        'Web Programming I',
        'WEB201',
        2,
        1,
        'General',
        3
    ),
    (
        'Programming Essentials in C++',
        'CPP201',
        2,
        1,
        'General',
        3
    ),
    (
        'Digital Electronics',
        'DIG201',
        2,
        1,
        'General',
        3
    ),
    (
        'Operating Systems',
        'OS201',
        2,
        1,
        'General',
        3
    );

-- =====================================================
-- 🟧 2nd Year — Term 2 (General Track)
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'Java Programming I',
        'JAVA201',
        2,
        2,
        'General',
        3
    ),
    (
        'CCNA I',
        'CCNA201',
        2,
        2,
        'General',
        3
    ),
    (
        'Data Structure',
        'DS201',
        2,
        2,
        'General',
        3
    ),
    (
        'Database Programming',
        'DBP201',
        2,
        2,
        'General',
        3
    ),
    (
        'Web Programming II',
        'WEB202',
        2,
        2,
        'General',
        3
    ),
    (
        'CCNA R&S I',
        'CCNARS201',
        2,
        2,
        'General',
        3
    );

-- =====================================================
-- 🟩 3rd Year — Software Track — Term 1
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'Microprocessor',
        'MICRO301',
        3,
        1,
        'SW',
        3
    ),
    (
        'Computer Graphics',
        'CG301',
        3,
        1,
        'SW',
        3
    ),
    (
        'Advanced Programming in C',
        'ADVC301',
        3,
        1,
        'SW',
        3
    ),
    (
        'Data Communication',
        'DC301',
        3,
        1,
        'SW',
        3
    ),
    (
        'Computer Architecture',
        'CA301',
        3,
        1,
        'SW',
        3
    ),
    (
        'Java Programming II',
        'JAVA301',
        3,
        1,
        'SW',
        3
    );

-- =====================================================
-- 🟩 3rd Year — Software Track — Term 2
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'Mobile Programming I',
        'MOB301',
        3,
        2,
        'SW',
        3
    ),
    (
        'Software Engineering',
        'SE301',
        3,
        2,
        'SW',
        3
    ),
    (
        'Network Programming',
        'NP301',
        3,
        2,
        'SW',
        3
    ),
    (
        'Algorithm',
        'ALG301',
        3,
        2,
        'SW',
        3
    ),
    (
        'Advanced Programming in C++',
        'ADVCPP301',
        3,
        2,
        'SW',
        3
    ),
    (
        'Embedded System',
        'EMB301',
        3,
        2,
        'SW',
        3
    );

-- =====================================================
-- 🟫 3rd Year — Network Track — Term 1
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'CCNA II',
        'CCNA301',
        3,
        1,
        'Network',
        3
    ),
    (
        'Microprocessor',
        'MICRO302',
        3,
        1,
        'Network',
        3
    ),
    (
        'Java Programming II',
        'JAVA302',
        3,
        1,
        'Network',
        3
    ),
    (
        'Data Communication',
        'DC302',
        3,
        1,
        'Network',
        3
    ),
    (
        'Computer Architecture',
        'CA302',
        3,
        1,
        'Network',
        3
    ),
    (
        'Network Administration',
        'NA301',
        3,
        1,
        'Network',
        3
    );

-- =====================================================
-- 🟫 3rd Year — Network Track — Term 2
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'CCNA R&S III',
        'CCNARS301',
        3,
        2,
        'Network',
        3
    ),
    (
        'Software Engineering',
        'SE302',
        3,
        2,
        'Network',
        3
    ),
    (
        'Distributed System',
        'DIS301',
        3,
        2,
        'Network',
        3
    ),
    (
        'Network Programming',
        'NP302',
        3,
        2,
        'Network',
        3
    ),
    (
        'Embedded System',
        'EMB302',
        3,
        2,
        'Network',
        3
    ),
    (
        'Distributed Systems II',
        'DIS302',
        3,
        2,
        'Network',
        3
    );

-- =====================================================
-- 🟥 4th Year — Software Track — Term 1
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'Mobile Programming II',
        'MOB401',
        4,
        1,
        'SW',
        3
    ),
    (
        'CCNA II',
        'CCNA401',
        4,
        1,
        'SW',
        3
    ),
    (
        'Windows Programming I',
        'WIN401',
        4,
        1,
        'SW',
        3
    ),
    (
        'Artificial Intelligence',
        'AI401',
        4,
        1,
        'SW',
        3
    ),
    (
        'IoT Architecture',
        'IOTA401',
        4,
        1,
        'SW',
        3
    ),
    (
        'Signal Processing',
        'SIG401',
        4,
        1,
        'SW',
        3
    );

-- =====================================================
-- 🟥 4th Year — Software Track — Term 2
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'IoT Security',
        'IOTS401',
        4,
        2,
        'SW',
        3
    ),
    (
        'Robotics',
        'ROB401',
        4,
        2,
        'SW',
        3
    ),
    (
        'Windows Programming II',
        'WIN402',
        4,
        2,
        'SW',
        3
    ),
    (
        'Machine Learning',
        'ML401',
        4,
        2,
        'SW',
        3
    ),
    (
        'Big Data & Analytics',
        'BDA401',
        4,
        2,
        'SW',
        3
    ),
    (
        'Entrepreneurship',
        'ENT401',
        4,
        2,
        'SW',
        3
    );

-- =====================================================
-- 🟪 4th Year — Network Track — Term 1
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'Server Administration',
        'SERV401',
        4,
        1,
        'Network',
        3
    ),
    (
        'CCNA R&S IV',
        'CCNARS401',
        4,
        1,
        'Network',
        3
    ),
    (
        'Cyber Security Operations',
        'CYBO401',
        4,
        1,
        'Network',
        3
    ),
    (
        'Encryption Algorithm',
        'ENC401',
        4,
        1,
        'Network',
        3
    ),
    (
        'Artificial Intelligence',
        'AI402',
        4,
        1,
        'Network',
        3
    ),
    (
        'IoT Architecture',
        'IOTA402',
        4,
        1,
        'Network',
        3
    );

-- =====================================================
-- 🟪 4th Year — Network Track — Term 2
-- =====================================================
INSERT OR IGNORE INTO
    courses (
        course_name,
        course_code,
        year,
        term,
        track,
        credit_hours
    )
VALUES (
        'IoT Security',
        'IOTS402',
        4,
        2,
        'Network',
        3
    ),
    (
        'Machine Learning',
        'ML402',
        4,
        2,
        'Network',
        3
    ),
    (
        'CCNP Switch',
        'CCNPS401',
        4,
        2,
        'Network',
        3
    ),
    (
        'CCNP Route',
        'CCNPR401',
        4,
        2,
        'Network',
        3
    ),
    (
        'Big Data & Analytics',
        'BDA402',
        4,
        2,
        'Network',
        3
    ),
    (
        'Entrepreneurship',
        'ENT402',
        4,
        2,
        'Network',
        3
    );

-- =====================================================
-- 🏫 INSERT SAMPLE SECTIONS
-- =====================================================
INSERT OR IGNORE INTO
    sections (
        year,
        term,
        track,
        section_number
    )
VALUES (1, 1, 'General', 1),
    (1, 1, 'General', 2),
    (1, 2, 'General', 1),
    (1, 2, 'General', 2),
    (2, 1, 'General', 1),
    (2, 1, 'General', 2),
    (2, 2, 'General', 1),
    (2, 2, 'General', 2),
    (3, 1, 'SW', 1),
    (3, 1, 'Network', 1),
    (3, 2, 'SW', 1),
    (3, 2, 'Network', 1),
    (4, 1, 'SW', 1),
    (4, 1, 'Network', 1),
    (4, 2, 'SW', 1),
    (4, 2, 'Network', 1);

-- =====================================================
-- 🏛️ INSERT SAMPLE CLASSROOMS
-- =====================================================
INSERT OR IGNORE INTO
    classrooms (
        room_code,
        capacity,
        building,
        room_type
    )
VALUES (
        'Hall-A',
        100,
        'Main Building',
        'Hall'
    ),
    (
        'Hall-B',
        80,
        'Main Building',
        'Hall'
    ),
    (
        'Lab-1',
        30,
        'IT Building',
        'Lab'
    ),
    (
        'Lab-2',
        30,
        'IT Building',
        'Lab'
    ),
    (
        'Lab-3',
        25,
        'IT Building',
        'Lab'
    ),
    (
        'LR-101',
        50,
        'Main Building',
        'Lecture Room'
    ),
    (
        'LR-102',
        50,
        'Main Building',
        'Lecture Room'
    ),
    (
        'LR-201',
        40,
        'Main Building',
        'Lecture Room'
    ),
    (
        'LR-202',
        40,
        'Main Building',
        'Lecture Room'
    );

-- =====================================================
-- 👨‍💼 INSERT DEFAULT ADMIN
-- =====================================================
INSERT OR IGNORE INTO
    admins (
        username,
        password,
        full_name,
        email,
        role,
        is_active
    )
VALUES (
        'admin',
        'admin123',
        'System Administrator',
        'admin@university.edu',
        'Admin',
        1
    );

INSERT OR IGNORE INTO
    admins (
        username,
        password,
        full_name,
        email,
        role,
        is_active
    )
VALUES (
        'control',
        'control123',
        'Control Officer',
        'control@university.edu',
        'Control',
        1
    );

-- =====================================================
-- 🏛️ INSERT DEPARTMENTS
-- =====================================================
INSERT OR IGNORE INTO
    instructors (
        instructor_id,
        name,
        email,
        specialization,
        title,
        is_active
    )
VALUES (
        1,
        'Dr. Ahmed Hassan',
        'ahmed.hassan@university.edu',
        'Computer Science',
        'Professor',
        1
    );

INSERT OR IGNORE INTO
    instructors (
        instructor_id,
        name,
        email,
        specialization,
        title,
        is_active
    )
VALUES (
        2,
        'Dr. Mohamed Ali',
        'mohamed.ali@university.edu',
        'Networking',
        'Associate Professor',
        1
    );

-- =====================================================
-- 👨‍🎓 INSERT SAMPLE STUDENTS
-- =====================================================
INSERT OR IGNORE INTO
    students (
        id,
        name,
        name_ar,
        email,
        password,
        department_id,
        level,
        seat_number,
        track,
        status
    )
VALUES (
        1,
        'Ahmed Mohamed',
        'أحمد محمد',
        'ahmed@university.edu',
        '123456',
        1,
        1,
        1001,
        'General',
        'active'
    );

INSERT OR IGNORE INTO
    students (
        id,
        name,
        name_ar,
        email,
        password,
        department_id,
        level,
        seat_number,
        track,
        status
    )
VALUES (
        2,
        'Sara Ali',
        'سارة علي',
        'sara@university.edu',
        '123456',
        1,
        2,
        1002,
        'SW',
        'active'
    );

INSERT OR IGNORE INTO
    students (
        id,
        name,
        name_ar,
        email,
        password,
        department_id,
        level,
        seat_number,
        track,
        status
    )
VALUES (
        3,
        'Mohamed Hassan',
        'محمد حسن',
        'mohamed@university.edu',
        '123456',
        1,
        3,
        1003,
        'Network',
        'active'
    );

-- =====================================================
-- 📰 INSERT SAMPLE NEWS
-- =====================================================
INSERT OR IGNORE INTO
    news (
        news_id,
        title,
        description,
        date,
        posted_by,
        category,
        is_pinned,
        is_active
    )
VALUES (
        1,
        'Welcome to New Semester',
        'We welcome all students to the academic year 2024-2025',
        '2024-09-01',
        'Admin',
        'General',
        1,
        1
    );

INSERT OR IGNORE INTO
    news (
        news_id,
        title,
        description,
        date,
        posted_by,
        category,
        is_pinned,
        is_active
    )
VALUES (
        2,
        'Registration Open',
        'Course registration is now open for all students',
        '2024-09-05',
        'Admin',
        'Academic',
        0,
        1
    );

-- =====================================================
-- END OF SCHEMA
-- =====================================================