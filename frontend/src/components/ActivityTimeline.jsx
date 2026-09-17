import React, { useRef, useEffect } from 'react';

const EVENT_CONFIG = {
  RUNTIME_STEP: { icon: '🔧', badgeCls: 'badge-sky', label: 'ขั้นตอน AI' },
  AGENT_PROGRESS: { icon: '⏳', badgeCls: 'badge-sky', label: 'ความคืบหน้า' },
  AGENT_PROMPT_READY: { icon: '📖', badgeCls: 'badge-sky', label: 'Prompt พร้อม' },
  AGENT_ERROR: { icon: '⚠️', badgeCls: 'badge-red', label: 'ข้อผิดพลาด' },
  AGENT_THOUGHT_DELTA: { icon: '💬', badgeCls: 'badge-sky', label: 'อัปเดต' },
  AGENT_STATUS_CHANGE:  { icon: '⚡', badgeCls: 'badge-indigo', label: 'Status' },
  AGENT_STATE_UPDATE:   { icon: '🤖', badgeCls: 'badge-sky',    label: 'State' },
  AGENT_RESPONSE:       { icon: '💬', badgeCls: 'badge-teal',   label: 'Response' },
  TOOL_EXECUTION_START: { icon: '🔧', badgeCls: 'badge-amber',  label: 'Tool' },
  TOOL_EXECUTION_FINISH:{ icon: '✅', badgeCls: 'badge-emerald',label: 'Tool Done' },
  DECISION_GATE_OPEN:   { icon: '🚪', badgeCls: 'badge-orange', label: 'Gate' },
  DECISION_GATE_RESOLVED:{ icon: '🔓', badgeCls: 'badge-green', label: 'Gate Resolved' },
  PIPELINE_COMPLETED:   { icon: '🎉', badgeCls: 'badge-purple', label: 'Completed' },
  PIPELINE_REJECTED:    { icon: '🛑', badgeCls: 'badge-rose',   label: 'Rejected' },
  PIPELINE_HALTED:      { icon: '⚠️', badgeCls: 'badge-red',    label: 'Halted' },
  SPRINT_STARTED:       { icon: '🚀', badgeCls: 'badge-blue',   label: 'Sprint Start' },
  EXECUTION_PLAN_READY: { icon: '🗺️', badgeCls: 'badge-indigo', label: 'Execution Plan' },
  AGENT_EVIDENCE:       { icon: '📁', badgeCls: 'badge-emerald', label: 'File Evidence' },
  WORKSPACE_COMMITTED:  { icon: '📦', badgeCls: 'badge-green', label: 'Applied' },
  AGENT_WHISPER_RECEIVED: { icon: '💬', badgeCls: 'badge-blue', label: 'ข้อกำหนดรอใช้' },
  AGENT_INSTRUCTIONS_APPLIED: { icon: '✓', badgeCls: 'badge-green', label: 'ใช้ข้อกำหนดในขั้นตอนแล้ว' },
  QUEUE_ITEM_STARTED:   { icon: '⏳', badgeCls: 'badge-cyan',   label: 'Queue' },
  QUEUE_ITEM_FINISHED:  { icon: '🏁', badgeCls: 'badge-slate',  label: 'Queue Done' },
};

function getEventDescription(ev) {
  const d = ev.data || {};
  if (ev.type === 'AGENT_WHISPER_RECEIVED') return `[${d.role}] เก็บข้อกำหนด รอขั้นถัดไป: ${d.message}`;
  if (ev.type === 'AGENT_PROMPT_READY') {
    return `${d.trace?.execution_mode || 'Agent'} · skills: ${(d.trace?.selected_skills || []).join(', ') || 'core only'}`;
  }
  if (ev.type === 'AGENT_RESPONSE') {
    const preview = d.response || '(no preview)';
    return `[${d.step_label || 'Task'}] ${preview}`;
  }
  return d.message || d.result || d.thought || d.summary || d.directive || d.tool || JSON.stringify(d);
}

function EventDetails({ event }) {
  const data = event.data || {};
  if (event.type === 'AGENT_PROMPT_READY') {
    return <details><summary>{getEventDescription(event)} — คลิกดูแหล่งข้อมูล</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(data.trace, null, 2)}</pre></details>;
  }
  if (event.type === 'AGENT_RESPONSE') {
    return <details><summary>{data.step_label || 'ผลการทำงาน'} — คลิกอ่าน</summary><div style={{ whiteSpace: 'pre-wrap' }}>{data.response}</div></details>;
  }
  if (event.type === 'EXECUTION_PLAN_READY') {
    return <details><summary>{data.summary}</summary><div>Agents: {(data.roles || []).join(', ')}</div><div style={{ whiteSpace: 'pre-wrap' }}>{(data.acceptance_criteria || []).map(item => `• ${item}`).join('\n')}</div></details>;
  }
  if (['AGENT_EVIDENCE', 'WORKSPACE_COMMITTED'].includes(event.type)) {
    return <details><summary>{data.summary}</summary><div style={{ whiteSpace: 'pre-wrap' }}>{(data.changed_files || []).map(path => `• ${path}`).join('\n') || 'ไม่มีไฟล์เปลี่ยน'}</div></details>;
  }
  return getEventDescription(event);
}

export default function ActivityTimeline({ events = [] }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  if (!events.length) {
    return (
      <div className="activity-timeline-empty">
        <div className="empty-icon">⏱</div>
        <p className="empty-title">Waiting for agent activity...</p>
        <p className="empty-subtitle">Events stream here in real-time as agents think, coordinate, and execute tools</p>
      </div>
    );
  }

  return (
    <div className="activity-timeline">
      <div className="timeline-header">
        <span className="timeline-header-title">
          Live Activity Feed ({events.length})
        </span>
      </div>
      <div className="timeline-items">
        {events.map((ev, idx) => {
          const cfg = EVENT_CONFIG[ev.type] || { icon: '•', badgeCls: 'badge-slate', label: ev.type };
          const timeStr = ev.timestamp
            ? new Date(ev.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            : '';
          return (
            <div key={idx} className="timeline-row">
              <span className="timeline-time">{timeStr}</span>
              <span className="timeline-icon">{cfg.icon}</span>
              <span className={`timeline-badge ${cfg.badgeCls}`}>{cfg.label}</span>
              {ev.data?.role && (
                <span className="timeline-role">
                  [{ev.data.role}]
                </span>
              )}
              <span className="timeline-desc">
                <EventDetails event={ev} />
              </span>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
    </div>
  );
}
