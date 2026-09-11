import React, { useRef, useEffect } from 'react';

const EVENT_CONFIG = {
  AGENT_STATUS_CHANGE: { icon: '⚡', color: 'text-indigo-400', label: 'Status' },
  AGENT_STATE_UPDATE:  { icon: '🤖', color: 'text-sky-400',    label: 'State' },
  TOOL_EXECUTION_START:{ icon: '🔧', color: 'text-amber-400',  label: 'Tool' },
  TOOL_EXECUTION_FINISH:{ icon: '✅', color: 'text-emerald-400',label: 'Tool Done' },
  DECISION_GATE_OPEN:  { icon: '🚪', color: 'text-orange-400', label: 'Gate' },
  DECISION_GATE_RESOLVED:{ icon: '🔓', color: 'text-green-400',label: 'Gate Resolved' },
  PIPELINE_COMPLETED:  { icon: '🎉', color: 'text-purple-400', label: 'Completed' },
  PIPELINE_REJECTED:   { icon: '🛑', color: 'text-rose-400',   label: 'Rejected' },
  PIPELINE_HALTED:     { icon: '⚠️', color: 'text-red-400',    label: 'Halted' },
  SPRINT_STARTED:      { icon: '🚀', color: 'text-blue-400',   label: 'Sprint Start' },
  QUEUE_ITEM_STARTED:  { icon: '⏳', color: 'text-cyan-400',   label: 'Queue' },
};

export default function ActivityTimeline({ events = [] }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  if (!events.length) {
    return (
      <div className="activity-timeline-empty">
        <div className="text-3xl mb-2">⏱</div>
        <p className="text-sm text-slate-400">Waiting for agent activity...</p>
        <p className="text-xs text-slate-500 mt-1">Events stream here in real-time as agents think and execute</p>
      </div>
    );
  }

  return (
    <div className="activity-timeline">
      <div className="timeline-header">
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Live Activity Feed ({events.length})
        </span>
      </div>
      <div className="timeline-items">
        {events.map((ev, idx) => {
          const cfg = EVENT_CONFIG[ev.type] || { icon: '•', color: 'text-slate-400', label: ev.type };
          const timeStr = ev.timestamp
            ? new Date(ev.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            : '';
          return (
            <div key={idx} className="timeline-row">
              <span className="timeline-time">{timeStr}</span>
              <span className="timeline-icon">{cfg.icon}</span>
              <span className={`timeline-badge ${cfg.color}`}>{cfg.label}</span>
              <span className="timeline-role font-mono text-xs text-slate-300">
                {ev.data?.role ? `[${ev.data.role}]` : ''}
              </span>
              <span className="timeline-desc text-xs text-slate-400">
                {ev.data?.thought || ev.data?.summary || ev.data?.directive || ev.data?.tool || JSON.stringify(ev.data || {})}
              </span>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
    </div>
  );
}
