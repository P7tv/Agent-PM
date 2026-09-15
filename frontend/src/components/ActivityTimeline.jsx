import React, { useRef, useEffect } from 'react';

const EVENT_CONFIG = {
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
  QUEUE_ITEM_STARTED:   { icon: '⏳', badgeCls: 'badge-cyan',   label: 'Queue' },
};

function getEventDescription(ev) {
  const d = ev.data || {};
  if (ev.type === 'AGENT_RESPONSE') {
    const preview = d.response ? d.response.slice(0, 100) + (d.response.length > 100 ? '…' : '') : '(no preview)';
    return `[${d.step_label || 'Task'}] ${preview}`;
  }
  return d.thought || d.summary || d.directive || d.tool || JSON.stringify(d);
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
                {getEventDescription(ev)}
              </span>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
    </div>
  );
}

