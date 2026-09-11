import React from 'react';

const STATUS_BADGE = {
  COMPLETED: { text: 'Done', cls: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' },
  RUNNING: { text: 'Running', cls: 'bg-amber-500/20 text-amber-300 border-amber-500/30 animate-pulse' },
  REJECTED: { text: 'Rejected', cls: 'bg-red-500/20 text-red-300 border-red-500/30' },
  FAILED: { text: 'Failed', cls: 'bg-rose-600/20 text-rose-300 border-rose-500/30' },
};

export default function SprintHistoryPanel({ sprints = [], onRerun }) {
  if (!sprints.length) {
    return (
      <div className="sprint-history-empty">
        <div className="text-3xl mb-2">📋</div>
        <p className="text-sm text-slate-400">No sprint history recorded yet</p>
        <p className="text-xs text-slate-500 mt-1">Sprints will be recorded here when PM directives execute</p>
      </div>
    );
  }

  const formatDuration = (start, end) => {
    if (!end) return 'Running...';
    const s = Math.round(end - start);
    return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
  };

  const formatDate = (ts) => {
    return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div className="sprint-history-panel">
      <div className="sprint-history-header">
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Sprint History ({sprints.length})
        </span>
      </div>
      <div className="sprint-history-list">
        {sprints.map((sp) => {
          const badge = STATUS_BADGE[sp.status] || STATUS_BADGE.COMPLETED;
          return (
            <div key={sp.sprint_id} className="sprint-card">
              <div className="sprint-card-top">
                <span className={`sprint-status-badge ${badge.cls}`}>{badge.text}</span>
                <span className="text-xs text-slate-400">{formatDate(sp.started_at)}</span>
                <span className="text-xs text-slate-500 font-mono">
                  ⏱ {formatDuration(sp.started_at, sp.completed_at)}
                </span>
                <span className="text-xs text-slate-500 font-mono">
                  🪙 {(sp.total_tokens || 0).toLocaleString()} tok
                </span>
                <span className="text-xs text-slate-500 uppercase">{sp.backend_used || 'mock'}</span>
                {onRerun && (
                  <button
                    className="sprint-rerun-btn"
                    onClick={() => onRerun(sp.directive)}
                    title="Re-run this directive"
                  >
                    ↺ Re-run
                  </button>
                )}
              </div>
              <div className="sprint-directive-text">{sp.directive}</div>
              {sp.release_summary && (
                <div className="sprint-release-summary">
                  <span className="text-slate-400 font-semibold">Summary: </span>
                  {sp.release_summary.slice(0, 160)}
                  {sp.release_summary.length > 160 ? '...' : ''}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
