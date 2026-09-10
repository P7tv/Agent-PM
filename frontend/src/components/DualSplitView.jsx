import React from 'react';
import { Layers, Activity, CheckCircle2, Clock, Trash2, FolderPlus } from 'lucide-react';

export default function DualSplitView({ 
  projects, 
  tasksByProject, 
  liveStreamsByProject, 
  onDeleteProject,
  onOpenAddProject 
}) {
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
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="room-tag">
                  {project.auto_pilot ? 'Auto-Pilot' : 'Gate Mode'}
                </span>
                <button
                  className="view-btn"
                  onClick={() => {
                    if (window.confirm(`Disconnect and remove project "${project.name}"?`)) {
                      onDeleteProject(project.project_id);
                    }
                  }}
                  title="Remove project"
                  style={{ color: 'var(--text-muted)', padding: '4px 6px' }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
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

      {/* Empty column if fewer than 2 projects */}
      {projects.length < 2 && (
        <div 
          className="project-column" 
          style={{ 
            border: '2px dashed var(--border-medium)', 
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center', 
            justifyContent: 'center', 
            minHeight: '340px',
            textAlign: 'center',
            cursor: 'pointer'
          }}
          onClick={onOpenAddProject}
        >
          <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'var(--primary-subtle)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
            <FolderPlus size={24} />
          </div>
          <h4 style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
            Connect Project 02
          </h4>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '240px', marginBottom: '14px' }}>
            Split screen will display both projects side-by-side.
          </p>
          <button className="dispatch-btn" style={{ fontSize: '12px', padding: '6px 14px' }}>
            + Add Project
          </button>
        </div>
      )}
    </div>
  );
}
