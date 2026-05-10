# 📖 شرح جزئية الـ PHP Backend — ChatNCT

## الفكرة العامة

المشروع الأساسي شغال بـ **Python (Flask)** — ده اللي بيشغّل الـ AI Chat والـ Attendance والـ Prompt Generator.

جزئية الـ PHP دي غرضها إن الـ **Login** يشتغل من خلال **XAMPP (Apache + MySQL)** بدل سيرفر Python.

- **اللوجن** → PHP + MySQL (XAMPP)
- **باقي الفيتشرز** (شات، حضور، بروميت) → Python Flask Server (الأصلي)

---

## 🗂️ هيكل الملفات

```
php_backend/
├── index.html                 ← صفحة اللوجن
├── dashboard.html             ← صفحة الداشبورد بعد اللوجن
├── .htaccess                  ← إعدادات Apache
├── api/
│   ├── auth/
│   │   └── login.php          ← API اللوجن
│   └── proxy.php              ← وسيط لسيرفر Python
├── config/
│   ├── database.php           ← الاتصال بـ MySQL
│   └── setup_database.sql     ← إنشاء الجداول
└── Documentation.md           ← الملف ده
```

---

## 📄 شرح كل ملف بالتفصيل

---

### 1. `.htaccess` (سطر واحد)

```
DirectoryIndex index.html
```

**بيعمل إيه بالظبط:**
- بيقول لسيرفر Apache إن لما حد يفتح الفولدر ده من غير ما يحدد ملف معين، يفتحله `index.html` أوتوماتيك.
- يعني لما تكتب `http://localhost/gradproject/php_backend/` هيفتحلك صفحة اللوجن على طول.

---

### 2. `config/database.php` (18 سطر)

```php
define('DB_HOST', 'localhost');
define('DB_NAME', 'gradproject');
define('DB_USER', 'root');
define('DB_PASS', '');
```

**بيعمل إيه بالظبط:**
- بيعرّف **بيانات الاتصال** بقاعدة بيانات MySQL على XAMPP:
  - `DB_HOST` = `localhost` (على نفس الجهاز)
  - `DB_NAME` = `gradproject` (اسم الداتابيز)
  - `DB_USER` = `root` (يوزر XAMPP الافتراضي)
  - `DB_PASS` = فاضي (XAMPP مفيهاش باسورد افتراضي)
- فيه **function واحدة** اسمها `getDB()`:
  - بتعمل اتصال بـ MySQL باستخدام **PDO**
  - لو الاتصال اتعمل قبل كده بيرجّع نفس الاتصال (static variable) عشان ميعملش اتصال جديد كل مرة
  - بيشغّل `ERRMODE_EXCEPTION` عشان لو فيه مشكلة في الداتابيز يعمل throw لـ error
  - بيشغّل `FETCH_ASSOC` عشان النتايج ترجع كـ associative array (مفتاح ← قيمة)

---

### 3. `config/setup_database.sql` (79 سطر)

**بيعمل إيه بالظبط:**

**أولاً — بيعمل الداتابيز:**
```sql
CREATE DATABASE IF NOT EXISTS `gradproject`
```
- بيعمل داتابيز اسمها `gradproject` بترميز `utf8mb4` (يدعم العربي والإيموجي)

**ثانياً — بيعمل 6 جداول:**

| الجدول | الأعمدة | الوظيفة |
|--------|---------|---------|
| `students` | `id`, `student_code`, `name`, `password`, `created_at` | بيانات الطلبة — الـ `student_code` هو اللي بيستخدمه الطالب في اللوجن |
| `instructors` | `id`, `name`, `password`, `created_at` | بيانات الدكاترة — الـ `name` هو اللي بيستخدمه الدكتور في اللوجن |
| `courses` | `id`, `course_code`, `name`, `instructor_id` | المواد — كل مادة مرتبطة بدكتور عن طريق `instructor_id` (Foreign Key) |
| `student_courses` | `student_id`, `course_id` | جدول وسيط بيربط الطالب بالمواد اللي مسجل فيها (Many-to-Many) |
| `attendance_sessions` | `id`, `session_code`, `course_id`, `instructor_id`, `is_active`, `created_at` | جلسات الحضور — كل جلسة ليها كود فريد ومرتبطة بمادة ودكتور |
| `attendance_records` | `id`, `session_id`, `student_id`, `verified_at` | سجل الحضور الفعلي — بيسجل مين حضر في أي جلسة ومتى اتحقق منه |

**العلاقات بين الجداول:**
- `courses.instructor_id` → `instructors.id` (لو الدكتور اتمسح، المادة تفضل موجودة بس من غير دكتور)
- `student_courses.student_id` → `students.id` (لو الطالب اتمسح، التسجيلات بتاعته تتمسح)
- `student_courses.course_id` → `courses.id` (لو المادة اتمسحت، التسجيلات بتاعتها تتمسح)
- `attendance_sessions.course_id` → `courses.id`
- `attendance_sessions.instructor_id` → `instructors.id`
- `attendance_records.session_id` → `attendance_sessions.id`
- `attendance_records.student_id` → `students.id`

**ثالثاً — بيضيف داتا تجريبية:**
- دكاترة: `Dr. Ahmed` و `Dr. Mohamed` (باسورد: `admin123`)
- طلبة: `20210001` (Ehab Hossam)، `20210002` (Ali Hassan)، `20210003` (Sara Ahmed) — (باسورد: `123456`)
- مواد: CS101, CS201, CS301

---

### 4. `api/auth/login.php` (47 سطر)

**بيعمل إيه بالظبط:**

ده ملف **API** — مش صفحة ويب. بيستقبل request من JavaScript وبيرجّع JSON.

**الـ Headers (سطر 5-7):**
- `Content-Type: application/json` → بيقول للبراوزر إن الرد هيكون JSON
- `Access-Control-Allow-Origin: *` → بيسمح لأي domain يبعتله requests (CORS)
- `Access-Control-Allow-Headers: Content-Type` → بيسمح بـ header اسمه Content-Type

**سطر 9:** لو الريكويست نوعه `OPTIONS` (preflight من البراوزر) بيرد بـ 204 ويقفل — ده عشان المتصفح بيبعت OPTIONS الأول قبل POST.

**سطر 10:** لو الريكويست مش `POST` بيرجّع error.

**سطر 12:** بيحمّل ملف `database.php` عشان يقدر يستخدم function الـ `getDB()`.

**سطر 14-16:** بيقرأ الـ JSON اللي جاي من الفورم:
```json
{ "username": "20210001", "password": "123456" }
```
بيفصّل منه الـ username والـ password.

**سطر 18:** لو أي واحد فيهم فاضي → بيرجّع error.

**سطر 20-31 — التشييك على الطلبة:**
1. بيعمل **prepared statement** (عشان يمنع SQL Injection)
2. بيدوّر في جدول `students` على `student_code` مطابق للـ username
3. لو لقاه:
   - بيقارن الباسورد — لو غلط بيرجّع `Wrong password`
   - لو صح بيرجّع JSON فيه:
     - `status: "success"`
     - `username`: اسم الطالب
     - `role: "student"`
     - `is_admin: false`
     - `user_id`: كود الطالب
     - `access_token`: توكن عشوائي (32 حرف hex) بيتعمل بـ `bin2hex(random_bytes(16))`

**سطر 33-41 — التشييك على الدكاترة:**
- لو ملقاش الـ username في الطلبة، بيدوّر في جدول `instructors` بالـ `name`
- نفس اللوجيك — لو الباسورد صح بيرجّع JSON بـ `role: "instructor"` و `is_admin: true`

**سطر 43:** لو ملقاش الـ username لا في الطلبة ولا الدكاترة → `User not found`

**سطر 44-46:** لو فيه أي مشكلة في الداتابيز → بيعمل catch للـ PDOException ويرجّع رسالة الخطأ

---

### 5. `api/proxy.php` (44 سطر)

**بيعمل إيه بالظبط:**

ده **وسيط (Proxy)** — بياخد أي API request من Apache ويبعته لسيرفر Python Flask اللي شغال على port 5000.

**ليه محتاجينه؟** لأن باقي فيتشرز المشروع (الشات الذكي، الحضور، الـ Prompt Generator) كلها شغالة على Python. الـ proxy ده بيخلي كل حاجة تشتغل من مكان واحد.

**سطر 3-6 — CORS Headers:** بيسمح لأي domain يبعت أي نوع request (GET, POST, PUT, DELETE). لو الريكويست `OPTIONS` بيرد بـ 204 ويقفل.

**سطر 8:** عنوان سيرفر Python: `https://127.0.0.1:5000`

**سطر 9-10:** بيقرأ الـ API path من الـ URL. مثلاً:
- `/proxy.php/api/chat` → الـ path هيكون `/api/chat`
- لو مفيش path → بيرجّع error 400

**سطر 12-14:** بيبني الـ URL الكامل لسيرفر Python وبيضيف عليه أي query parameters.

**سطر 16-23 — إعداد cURL:**
- `CURLOPT_RETURNTRANSFER` → عايز الرد كـ string مش يطبعه على طول
- `CURLOPT_FOLLOWLOCATION` → لو فيه redirect يتبعه
- `CURLOPT_TIMEOUT` → أقصى وقت 120 ثانية
- `CURLOPT_SSL_VERIFYPEER/HOST = false` → بيتجاهل شهادة SSL (لأن Flask بيستخدم self-signed certificate)
- `CURLOPT_CUSTOMREQUEST` → بيبعت نفس نوع الريكويست الأصلي (GET/POST/etc)

**سطر 26-27:** لو الريكويست POST أو PUT أو PATCH → بياخد الـ body من الريكويست الأصلي ويبعته لـ Python.

**سطر 29-32:** بيحوّل الـ headers المهمة (Content-Type و Authorization) من الريكويست الأصلي للريكويست الجديد.

**سطر 34-37:** بينفّذ الريكويست ويحفظ الرد والـ HTTP status code ونوع المحتوى.

**سطر 39:** لو الريكويست فشل (مثلاً سيرفر Python مش شغال) → بيرجّع error 502.

**سطر 41-43:** بيبعت الرد لليوزر بنفس الـ status code والـ Content-Type اللي جه من Python.

---

### 6. `index.html` (103 سطر)

**بيعمل إيه بالظبط:**

دي **صفحة اللوجن** — أول صفحة اليوزر بيشوفها. فيها 3 أجزاء:

**الجزء الأول — CSS (سطر 8-47):**
- الصفحة بتستخدم خط Google `Montserrat`
- الخلفية gradient بنفسجي غامق
- الفورم في كارد في نص الصفحة بـ border مدور وشادو
- الـ inputs بتتلون لما تركّز عليها (focus effect)
- الزرار بيطلع لفوق لما تحط الماوس عليه (hover)
- فيه badge في أعلى يمين الصفحة مكتوب "PHP + MySQL" بنقطة خضرا

**الجزء التاني — HTML (سطر 49-64):**
- شعار المشروع (Logo) من فولدر `frontend/img/`
- عنوان "Login" وتحته "PHP + MySQL Backend"
- فورم فيه:
  - حقل Username (نوعه text)
  - حقل Password (نوعه password)
  - زرار Login
  - div فاضي للـ error messages

**الجزء التالت — JavaScript (سطر 66-99):**
- بيسمع على event الـ `submit` بتاع الفورم
- لما اليوزر يدوس Login:
  1. بيعطّل الزرار ويكتب عليه "Signing in..."
  2. بيبعت **fetch POST** لـ `api/auth/login.php` بالـ username والـ password كـ JSON
  3. بيستنى الرد:
     - **لو success**: بيحفظ في **localStorage** الآتي:
       - `chatnct_username` ← اسم اليوزر
       - `chatnct_role` ← student أو instructor
       - `chatnct_is_admin` ← true أو false
       - `chatnct_access_token` ← التوكن
       - `chatnct_user_id` ← الـ ID
       - `chatnct_backend` ← "php"
     - وبعدين بيحوّل الصفحة لـ `dashboard.html`
     - **لو فشل**: بيعرض رسالة الخطأ اللي راجعة من السيرفر
  4. لو فيه **Connection error** (مثلاً XAMPP مش شغال): بيعرض "Connection error. Is XAMPP running?"
  5. في الآخر بيرجّع الزرار لحالته الطبيعية

---

### 7. `dashboard.html` (106 سطر)

**بيعمل إيه بالظبط:**

دي **صفحة الداشبورد** — الصفحة الرئيسية بعد اللوجن. فيها 3 أجزاء:

**الجزء الأول — CSS (سطر 8-51):**
- نفس ستايل اللوجن (gradient بنفسجي، خط Montserrat)
- فيه topbar ثابت فوق فيه اللوجو وزرار Logout
- الكروت بتاعت الأكشنز (120x110px) بتطلع لفوق لما تحط الماوس عليها
- بتستخدم emoji بدل أيقونات خارجية

**الجزء التاني — HTML (سطر 53-80):**
- **Topbar** فيه:
  - شعار المشروع (Logo)
  - Badge مكتوب عليه "PHP + MySQL"
  - زرار Logout
- **صورة الروبوت** من `frontend/img/Head of Charcter.png`
- **عنوان ترحيب** (h1) بيتملي بالـ JavaScript
- **وصف المشروع** في كارد
- **4 كروت أكشن:**
  - 💬 AI Chat → بتروح لـ `../frontend/chat.html?view=chat`
  - 📋 Attendance → بتروح لـ `../frontend/attendance.html` (ليها `data-role="student"` — يعني بتظهر للطلبة بس)
  - 🎓 Instructor → بتروح لـ `../frontend/instructor.html` (ليها `data-role="instructor,admin"` — يعني بتظهر للدكاترة بس)
  - ✨ Prompt Gen → بتروح لـ `../frontend/prompt.html` (بتظهر للكل)

**الجزء التالت — JavaScript (سطر 82-103):**

1. **تشييك الأوث (سطر 83-85):** بيقرأ `chatnct_username` من localStorage — لو مش موجود بيرجّع اليوزر لصفحة اللوجن فوراً.

2. **التحية (سطر 88-90):** بياخد الساعة الحالية:
   - من 5 لـ 12 الضهر → "Good Morning"
   - من 12 لـ 5 العصر → "Good Afternoon"
   - غير كده → "Good Evening"
   - بيضيف اسم اليوزر بعد التحية

3. **إخفاء الكروت حسب الرول (سطر 93-97):** بيدوّر على كل عنصر عليه `data-role` وبيتشيك:
   - بياخد الـ role من localStorage
   - بيقارنه بالـ roles المسموحة في الـ data attribute
   - لو الـ role مش مسموح → `display: none` (بيخفيه)
   - مثال: لو اليوزر "student" → كارت "Instructor" بتختفي

4. **function الـ logout (سطر 99-102):**
   - بيمسح كل الـ keys المتخزنة في localStorage (6 keys)
   - بيحوّل الصفحة لـ `index.html`

---

## 🔄 الفلو الكامل

```
اليوزر بيفتح الموقع
        ↓
   index.html (صفحة اللوجن)
        ↓
   بيكتب username + password ويدوس Login
        ↓
   JavaScript بيبعت POST لـ api/auth/login.php
        ↓
   login.php بيسأل database.php يعمل اتصال بـ MySQL
        ↓
   بيدوّر في جدول students الأول ← لو ملقاش → بيدوّر في instructors
        ↓
   لو الباسورد صح → بيرجّع JSON { status: "success", ... }
        ↓
   JavaScript بيحفظ البيانات في localStorage
        ↓
   بيحوّل لـ dashboard.html
        ↓
   الداشبورد بيعرض التحية + الكروت حسب الرول
        ↓
   اليوزر بيختار فيتشر (شات / حضور / إلخ)
        ↓
   بيروح لصفحات الـ frontend الأصلية
   (الريكويستات بتعدي من proxy.php → Python Flask Server)
```

---

## 🗄️ بيانات تجريبية جاهزة

| النوع | Username | Password |
|-------|----------|----------|
| طالب | `20210001` | `123456` |
| طالب | `20210002` | `123456` |
| طالب | `20210003` | `123456` |
| دكتور | `Dr. Ahmed` | `admin123` |
| دكتور | `Dr. Mohamed` | `admin123` |

---

## ⚙️ إزاي تشغّل

1. حط فولدر المشروع كله جوه `C:\xampp\htdocs\gradproject\`
2. شغّل **Apache** و **MySQL** من XAMPP Control Panel
3. افتح **phpMyAdmin** (`http://localhost/phpmyadmin`) وإعمل Import لـ `config/setup_database.sql`
4. افتح `http://localhost/gradproject/php_backend/`
5. سجّل دخول بأي بيانات من الجدول فوق

### لو عايز الشات والحضور يشتغلوا:
- لازم تشغّل **Python Flask Server** كمان على port 5000
- الـ `proxy.php` هيوصل الريكويستات ليه أوتوماتيك
