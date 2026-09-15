import React from 'react';
import { Compass, Server, FlaskConical, ShieldCheck, FileText, CheckCircle2, Loader2 } from 'lucide-react';
const BUSY = new Set(['THINKING', 'WORKING', 'TESTING', 'REVIEWING']);

export default function SprintPipelineStepper({ agents = [], tasks = [], sprints = [], events = [] }) {
  const latest = [...sprints].sort((a, b) => b.started_at - a.started_at)[0];
  const sprintTasks = latest ? tasks.filter(task => task.sprint_id === latest.sprint_id) : [];
  const selectedRoles = [...new Set(sprintTasks.map(task => task.assigned_to))];
  const implementers = selectedRoles.filter(role => !['QATester', 'Reviewer', 'DocWriter'].includes(role));
  const stages = [
    { label: 'วางแผน', sub: 'TechLead & Architect', icon: Compass, roles: ['TechLead', 'Architect'] },
    ...(implementers.length ? [{ label: 'ลงมือทำ', sub: implementers.join(', '), icon: Server, roles: implementers }] : []),
    ...(selectedRoles.includes('DocWriter') ? [{ label: 'เอกสาร', sub: 'DocWriter', icon: FileText, roles: ['DocWriter'] }] : []),
    { label: 'ตรวจด้วยระบบ', sub: 'Tests, lint, build', icon: FlaskConical, roles: ['QATester'] },
    { label: 'อนุมัติคุณภาพ', sub: 'Reviewer', icon: ShieldCheck, roles: ['Reviewer'] },
  ].map((item, index) => ({ ...item, id: index + 1 }));
  const running = latest?.status === 'RUNNING';
  const complete = latest?.status === 'COMPLETED';
  const stopped = latest && !running && !complete;
  const activeAgents = running ? agents.filter(a => BUSY.has(a.status)) : [];
  const recent = events.filter(e => latest && e.timestamp >= latest.started_at);
  const gateEvent = [...recent].reverse().find(e => ['DECISION_GATE_OPEN', 'DECISION_GATE_RESOLVED'].includes(e.type));
  const waiting = running && gateEvent?.type === 'DECISION_GATE_OPEN';
  const activeRole = activeAgents[activeAgents.length - 1]?.role;
  const stage = complete ? stages.length + 1 : running ? stages.find(s => s.roles.includes(activeRole))?.id || 1 : 0;
  const progress = [...recent].reverse().find(e => e.type === 'AGENT_PROGRESS' && activeAgents.some(a => a.role === e.data?.role));
  const badge = waiting ? 'รอคุณอนุมัติ' : running ? 'กำลังทำงาน' : complete ? 'เสร็จสิ้น' : stopped ? 'หยุดแล้ว' : 'พร้อมรับงาน';

  return (
    <section className="sprint-pipeline-stepper" aria-label="ขั้นตอนการทำงาน">
      <div className="stepper-header">
        <div className="stepper-title-wrap">
          <span className={`stepper-badge ${running ? 'is-running' : ''}`}>{badge}</span>
          <span className="stepper-directive-text" title={latest?.directive}>{latest?.directive || 'บอกเป้าหมาย แล้วเลือก “สั่งงานทีม” เพื่อเริ่ม Sprint'}</span>
        </div>
        {latest && <span className="stepper-sprint-id">{latest.sprint_id}</span>}
      </div>
      <div className="stepper-track">
        {stages.map((item, index) => {
          const Icon = item.icon;
          const done = complete || (running && stage > item.id);
          const active = running && !waiting && stage === item.id;
          return <React.Fragment key={item.id}>
            <div className={`stepper-node ${done ? 'is-done' : active ? 'is-active' : 'is-pending'}`}>
              <div className="stepper-icon-circle">{done ? <CheckCircle2 size={15} /> : active ? <Loader2 size={15} className="spin" /> : <Icon size={14} />}</div>
              <div className="stepper-node-text"><span className="stepper-node-label">{item.label}</span><span className="stepper-node-sub">{item.sub}</span></div>
            </div>
            {index < stages.length - 1 && <div className={`stepper-connector ${done ? 'is-done' : ''}`} />}
          </React.Fragment>;
        })}
      </div>
      <div className="pipeline-current-work" role="status">
        {waiting ? 'เปิดหน้าต่างอนุมัติเพื่ออ่านแผน แล้วเลือกอนุมัติหรือปฏิเสธ' : stopped ? latest.release_summary : running ? <>
          {activeAgents.map(a => <div key={a.role}><strong>{a.role}</strong> · {a.thought || 'กำลังทำงาน…'}</div>)}
          {progress && !activeAgents.some(a => a.thought === progress.data.message) && <div>{progress.data.message}</div>}
          {!activeAgents.length && 'กำลังเตรียมขั้นตอนถัดไป…'}
        </> : complete ? 'อ่านสรุปในแชต ดูไฟล์ที่ Code & Changes และผลทดสอบที่ Sprints & QA' : '1. เลือกโปรเจกต์  2. ระบุสิ่งที่ต้องการและเกณฑ์สำเร็จ  3. ติดตามขั้นตอนและผลลัพธ์ที่นี่'}
      </div>
    </section>
  );
}
