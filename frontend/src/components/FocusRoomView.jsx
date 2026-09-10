import React from 'react';
import { ArrowLeft, Terminal, Shield, CheckCircle, Code2, Users } from 'lucide-react';

export default function FocusRoomView({ project, agents, tasks, liveStream, onBack, onAgentClick }) {
  if (!project) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="view-btn" onClick={onBack}>
          <ArrowLeft size={16} />
          <span>Back to Overview</span>
        </button>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="room-tag">PROJECT WORKSPACE</span>
          <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)' }}>{project.name}</h2>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '20px' }}>
        {/* Left column: Active Roster & Roles */}
        <div style={{ background: 'var(--bg-surface)', borderRadius: 'var(--radius-lg)', padding: '20px', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
            <Users size={16} color="var(--primary)" />
            <span>Assigned Agents ({agents.length})</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {agents.map((ag) => (
              <div
                key={ag.role}
                style={{
                  background: 'var(--bg-canvas)',
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
                onClick={() => onAgentClick(project.project_id, ag.role)}
                title="Click to whisper"
              >
                <div>
                  <div style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>{ag.role}</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{ag.thought || 'Idle'}</div>
                </div>
                <span className={`agent-status-badge status-${ag.status}`}>
                  {ag.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Right column: Deep-Dive Live Terminal Stream & Tasks */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ background: 'var(--bg-surface)', borderRadius: 'var(--radius-lg)', padding: '20px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
              <Terminal size={16} color="var(--primary)" />
              <span>Real-time Agent Execution & Tool Logs</span>
            </div>

            <div className="live-stream-box" style={{ height: '360px' }}>
              {liveStream.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Ready for execution. Dispatch a directive above.</div>
              ) : (
                liveStream.map((log, i) => (
                  <div key={i} className="stream-entry">
                    <span className="stream-role">[{log.role || 'SYS'}]</span>
                    {log.thought && <span className="stream-thought">{log.thought}</span>}
                    {log.tool && <span className="stream-tool">[tool: {log.tool}]</span>}
                    {log.message && <span className="stream-thought">{log.message}</span>}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
