let activeCode = null;
let timerInterval = null;
let pollInterval = null;

// Load courses on page load
window.addEventListener("DOMContentLoaded", loadCourses);

async function loadCourses() {
    try {
        const res = await fetch("/api/courses");
        const courses = await res.json();
        const sel = document.getElementById("courseSelect");
        sel.innerHTML = '<option value="">— Select a course —</option>';
        courses.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.course_id;
            opt.dataset.instructor = c.instructor_id || 1;
            const codePrint = c.course_code ? `${c.course_code} — ` : "";
            opt.textContent = `${codePrint}${c.course_name}`;
            sel.appendChild(opt);
        });
    } catch (e) {
        console.error("Failed to load courses", e);
    }
}

async function createSession() {
    const courseId = document.getElementById("courseSelect").value;
    const duration = document.getElementById("durationInput").value;
    const instructorId = document.getElementById("instructorInput").value;
    const msgEl = document.getElementById("createMsg");

    if (!courseId) {
        msgEl.className = "msg error";
        msgEl.textContent = "Please select a course.";
        return;
    }

    document.getElementById("startBtn").disabled = true;

    try {
        const res = await fetch("/api/session/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                course_id: courseId,
                instructor_id: instructorId,
                duration_minutes: parseInt(duration),
            }),
        });
        const data = await res.json();

        if (data.status !== "success") {
            msgEl.className = "msg error";
            msgEl.textContent = data.message;
            document.getElementById("startBtn").disabled = false;
            return;
        }

        activeCode = data.session_code;

        // Show session card
        document.getElementById("createCard").style.display = "none";
        document.getElementById("sessionCard").style.display = "block";
        document.getElementById("sessionCode").textContent = data.session_code;
        const codePrint = data.course.course_code ? `${data.course.course_code} — ` : "";
        document.getElementById("courseName").textContent = codePrint + data.course.course_name;

        const exp = new Date(data.expires_at);
        document.getElementById("expiresAt").textContent = exp.toLocaleTimeString();

        // Student URL
        const studentLink = `${window.location.origin}/student?code=${data.session_code}`;
        document.getElementById("studentUrl").innerHTML =
            `Student link: <a href="${studentLink}" target="_blank">${studentLink}</a>`;

        // Generate QR Code
        const qrEl = document.getElementById("qrCode");
        qrEl.innerHTML = "";
        new QRCode(qrEl, {
            text: studentLink,
            width: 220,
            height: 220,
            colorDark: "#1a1a3e",
            colorLight: "#ffffff",
        });

        // Start countdown timer
        startTimer(exp);

        // Poll for attendance updates
        pollInterval = setInterval(() => pollAttendance(data.session_code), 3000);

    } catch (e) {
        msgEl.className = "msg error";
        msgEl.textContent = "Server error: " + e.message;
        document.getElementById("startBtn").disabled = false;
    }
}

function startTimer(expiresAt) {
    const timerEl = document.getElementById("timer");
    timerInterval = setInterval(() => {
        const now = new Date();
        const diff = expiresAt - now;
        if (diff <= 0) {
            timerEl.textContent = "⏰ Session Expired";
            timerEl.className = "timer expired";
            clearInterval(timerInterval);
            return;
        }
        const mins = Math.floor(diff / 60000);
        const secs = Math.floor((diff % 60000) / 1000);
        timerEl.textContent = `⏱ ${mins}:${secs.toString().padStart(2, "0")} remaining`;
    }, 1000);
}

async function pollAttendance(code) {
    try {
        const res = await fetch(`/api/session/${code}/report`);
        const data = await res.json();
        if (data.status !== "success") return;

        document.getElementById("totalCount").textContent = data.total_present;
        const list = document.getElementById("studentsList");

        // Only add new items
        const existing = list.querySelectorAll(".student-item").length;
        if (data.records.length > existing) {
            data.records.slice(existing).forEach(r => {
                const div = document.createElement("div");
                div.className = "student-item";
                div.innerHTML = `
                    <div>
                        <div class="name">${r.student_name}</div>
                        <div class="time">ID: ${r.student_id} • ${r.verified_by}</div>
                    </div>
                    <span class="badge">✓ Present</span>
                `;
                list.appendChild(div);
            });
        }
    } catch (e) { /* silent */ }
}

async function closeSession() {
    if (!activeCode) return;
    try {
        await fetch(`/api/session/${activeCode}/close`, { method: "POST" });
    } catch (e) { /* ignore */ }

    clearInterval(timerInterval);
    clearInterval(pollInterval);

    // Reset UI
    document.getElementById("sessionCard").style.display = "none";
    document.getElementById("createCard").style.display = "block";
    document.getElementById("startBtn").disabled = false;
    document.getElementById("studentsList").innerHTML = "";
    document.getElementById("totalCount").textContent = "0";
    document.getElementById("createMsg").textContent = "";
    activeCode = null;
}
