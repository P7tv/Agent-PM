import React from 'react';
import { Layers, Activity, CheckCircle2, Clock } from 'lucide-react';

export default function DualSplitView({ projects, tasksByProject, liveStreamsByProject }) {
  return (
    <div className="dual-split-view">
      {projects.map((project) => {
        const tasks = tasksByProject[project.project_id] || [];
        const stream = liveStreamsByProject[project.project_id] || [];

        const todoTasks = tasks.filter((t) => t.status === 'TODO');
        const inProgressTasks = tasks.filter((t) => t.status === 'IN_PROGRESS' || t.status === 'TESTING');
        const doneTasks = tasks.filter((t) => t.status === 'DONE');

        return (
          <div key={project.project_id} className="project-column">
            <div className="room-header">
              <div>
                <h3 className="room-title">{project.name}</h3>
                <p className="room-workspace">{project.workspace_path}</p>
              </div>
              <span className="room-tag">
                {project.auto_pilot ? 'Auto-Pilot' : 'Gate Mode'}
              </span>
            </div>

            {/* Kanban Overview */}
            <div className="kanban-section">
              <div className="kanban-col">
                <div className="kanban-header">
                  <span>To Do</span>
                  <span>{todoTasks.length}</span>
                </div>
                {todoTasks.map((t) => (
                  <div key={t.task_id} className="kanban-card">
                    <div>{t.title}</div>
                    <div className="kanban-assignee">@{t.assigned_to}</div>
                  </div>
                ))}
              </div>

              <div className="kanban-col">
                <div className="kanban-header">
                  <span>In Progress</span>
                  <span>{inProgressTasks.length}</span>
                </div>
                {inProgressTasks.map((t) => (
                  <div key={t.task_id} className="kanban-card">
                    <div>{t.title}</div>
                    <div className="kanban-assignee">@{t.assigned_to}</div>
                  </div>
                ))}
              </div>

              <div className="kanban-col">
                <div className="kanban-header">
                  <span>Done</span>
                  <span>{doneTasks.length}</span>
                </div>
                {doneTasks.map((t) => (
                  <div key={t.task_id} className="kanban-card">
                    <div>{t.title}</div>
                    <div className="kanban-assignee">@{t.assigned_to}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Live Terminal Stream */}
            <div style={{ marginTop: '10px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '500' }}>
                <Activity size={13} color="var(--primary)" />
                <span>ACTIVITY FEED</span>
              </div>
              <div className="live-stream-box">
                {stream.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Standing by for PM directives...</div>
                ) : (
                  stream.slice(-30).map((log, i) => (
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
        );
      })}
    </div>
  );
}
