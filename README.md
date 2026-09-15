# 🏢 Antigravity Virtual AI Office — PM Command Center

A modern, cyberpunk-aesthetic **Multi-Agent Orchestrator & Virtual Office Dashboard** powered by FastAPI and the **Antigravity Python SDK (`google-antigravity`)**.

Manage teams of 5–10 autonomous agents across up to 2 concurrent projects. Simply input high-level product requirements as a Product Manager (PM), while the agents autonomously decompose, build, test, self-heal, and review your code!

---

## ✨ Key Features

1. **🏢 Virtual Office Floor**:
   - Visual department rooms for **Project Alpha** and **Project Beta**.
   - Interactive agent desks with animated avatars for:
     - 📐 **Product Architect**: Decomposes requirements into user stories and task trees.
     - 🎨 **UI/UX Designer**: Designs responsive layout and styling tokens.
     - 💻 **Frontend Dev**: Builds components, client state, and views.
     - ⚙️ **Backend Dev**: Implements endpoints, server logic, and database layer.
     - 🧪 **QA Tester**: Executes automated test suites and regression checks.
     - 🛡️ **Code Reviewer**: Audits security, diff quality, and writes PM release notes.
     - 📝 **Doc Writer**: Updates documentation and guides.
   - Live thought bubbles and glowing pulse rings indicating active thoughts/actions.

2. **⚡ Dual-Split Screen (Multitasking)**:
   - 50/50 two-column interface for simultaneous management of 2 projects.
   - Real-time mini Kanban boards (To Do, In Progress, Done).
   - Real-time terminal feeds displaying thoughts, tool calls, and test results.

3. **🔍 Focus War Room**:
   - Deep dive into a single project with full agent rosters and extended thought logs.

4. **🎯 PM Command Desk & Hybrid Controls**:
   - **PM Directive Box**: Enter high-level requests (e.g. *"Add Google OAuth2 and profile dashboard"*).
   - **Auto-Pilot vs Gate Mode**: Toggle between 100% autonomous execution or human-in-the-loop approval checkpoints.
   - **Agent Whisper**: Click any agent at their desk to whisper direct constraints mid-sprint without starting over.
   - **Self-Healing Loop**: If the QA tester catches failures, logs are automatically fed back to Dev agents to self-heal and retry (capped at 3 iterations).

---

## 🚀 Quickstart & Setup

### 1. Install Dependencies

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install frontend dependencies and build production assets:

```bash
cd frontend
npm install
npm run build
cd ..
```

### 2. Configure Environment (Optional)

Copy `.env.example` to `.env` if you wish to configure your Gemini API Key or custom Antigravity Skills directory:

```bash
cp .env.example .env
```

### 3. Launch the Dashboard

Run the startup script:

**On Windows:**
Double-click `start.bat` or run:

```powershell
python start_dashboard.py
```

**On Linux / macOS:**

```bash
python3 start_dashboard.py
```

### 4. Open Your Browser

Navigate to:

```
http://127.0.0.1:8000
```

---

## 🧪 Running Automated Tests

Run the full pytest suite:

```bash
# Windows (PowerShell)
$env:PYTHONPATH="backend;.backend"; python -m pytest backend/tests/ -v

# Linux / macOS
PYTHONPATH=backend python3 -m pytest backend/tests/ -v
```

## การใช้งานและติดตามงาน

1. เพิ่มโปรเจกต์และเลือกโฟลเดอร์งาน ดูแถบ **AI** ด้านบนว่าพบ runtime หรือไม่ (การเข้าสู่ระบบจะตรวจเมื่อเรียกใช้งาน)
2. **คุยปรึกษา** ใช้ถามและรับข้อเสนอโค้ด ส่วน **สั่งงานทีม / รัน Sprint** จะเริ่ม pipeline ที่ลงมือทำงาน
3. ระบุผู้ใช้ เป้าหมาย ฟีเจอร์สำคัญ รูปแบบหน้าตา และเกณฑ์สำเร็จ เช่น “สร้างหน้ารายการสินค้า มีค้นหา เพิ่ม/แก้ไขสินค้า ใช้ React เดิม รองรับมือถือ และมี test สำหรับการค้นหา”
4. ใน **Gate Mode** ทีมวางแผนก่อนและรออนุมัติ อ่านแผนในหน้าต่างก่อนเลือกทำต่อ หากไม่ตอบภายในเวลาที่กำหนด pipeline จะหยุด
5. หน้าจอโปรเจกต์แสดงขั้นตอนปัจจุบัน ผู้รับผิดชอบ เวลารอ AI และผลลัพธ์แต่ละขั้นในแชต ประวัติขั้นตอนและคำตอบถูกบันทึกใน SQLite และอ่านได้หลัง reload
6. ตรวจไฟล์ใน **Code & Changes** และตรวจผลทดสอบใน **Sprints & QA** หากสั่งไม่สำเร็จ ข้อความที่พิมพ์จะยังอยู่ให้แก้และส่งใหม่

### Workflow ของ Sprint

1. **TechLead + Architect** อ่าน workspace, จำกัด scope และสร้าง execution plan พร้อม acceptance criteria
2. ระบบเลือกเฉพาะ **Designer / Frontend / Backend / specialist / DocWriter** ที่เกี่ยวข้องกับคำสั่งนั้น
3. Agent ลงมือใน **staged workspace** และรายงานหลักฐานเป็นรายชื่อไฟล์ที่เพิ่ม แก้ หรือลบ
4. เอกสารที่เกี่ยวข้องจะอัปเดตก่อนตรวจคุณภาพ
5. **QA แบบ read-only** รัน test, typecheck/check, lint และ build ที่ตรวจพบ หากล้มเหลวจะส่งผลพร้อม path กลับไปยังเจ้าของงานและลองแก้ได้สูงสุด 3 รอบ
6. **Reviewer แบบ read-only** ตรวจ acceptance criteria, ไฟล์ที่เปลี่ยน และผล QA โดยต้องคืน verdict ที่ระบบอ่านได้ งานจะถูก block หากไม่อนุมัติ
7. ระบบรัน verification รอบสุดท้าย แล้วจึงนำไฟล์จาก staged workspace กลับเข้าโปรเจกต์พร้อมกัน หาก sprint ล้มเหลวไฟล์ครึ่งงานจะไม่ถูกนำมาใช้

### Runtime และคุณภาพงาน

- ต้องมี `agy` ที่เข้าสู่ระบบแล้ว หรือ SDK ที่เข้ากันได้พร้อม API key; การติดตั้ง Python dependencies อย่างเดียวไม่ได้ติดตั้ง AI runtime
- ระบบ production จะรายงานข้อผิดพลาดเมื่อ AI ใช้งานไม่ได้ ไม่มีการจำลองงานแล้วแสดงว่าสร้างเสร็จ
- `AGENT_EFFORT=high` และ `AGENT_TIMEOUT_SECONDS=600` เป็นค่าเริ่มต้น ปรับได้ใน `.env` แล้ว restart backend
- CLI ส่งอัปเดตเวลารอทุกประมาณ 10 วินาที การรายงานนี้หมายถึง process ยังรอผล ไม่ใช่หลักฐานว่าเขียนไฟล์หรือทดสอบผ่านแล้ว
- Agent ที่แก้ไฟล์ทำงานตามลำดับใน staged workspace; ระบบตรวจ conflict ก่อนนำผลกลับเข้า workspace หลัก
- QA ตรวจ process exit code รองรับ npm scripts (`test`, `typecheck`, `check`, `lint`, `build`), pytest, Go และ Cargo ทั้งที่ root และ package ชั้นแรกของ monorepo หากไม่พบ check จะแจ้ง `NOT_RUN` และไม่ถือว่าผ่าน
- Auto-Pilot จะหยุดทันทีเมื่อ QA ยังไม่ผ่านหลังครบจำนวนครั้ง ส่วน Gate Mode จะเปิดให้ PM ตัดสินใจรับความเสี่ยง ผลทดสอบอัตโนมัติยังไม่แทนการตรวจ UX ด้วยมนุษย์
- Directive ที่ค้างใน queue จะกลับมาทำต่ออัตโนมัติหลัง backend restart ส่วน sprint ที่กำลังรันตอน process หยุดจะถูกปิดเป็น failed เพื่อไม่รายงานสถานะค้าง
- CLI ลงมือทำงานด้วยสิทธิ์ของผู้ใช้ในเครื่องตามการตั้งค่าเดิมของแอป ใช้กับ workspace ที่ตั้งใจให้ agent แก้ไข

หลังแก้ frontend ให้รัน `cd frontend && npm run build` แล้ว restart `python start_dashboard.py` เพื่อใช้ backend เวอร์ชันใหม่ด้วย
