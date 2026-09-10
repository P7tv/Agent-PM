import React from 'react';
import { 
  Compass, 
  Palette, 
  Layout, 
  Server, 
  FlaskConical, 
  ShieldCheck, 
  FileText, 
  Bot,
  Eye,
  Trash2,
  FolderPlus
} from 'lucide-react';
import TechLeadCard from './TechLeadCard';

const ROLE_ICONS = {
  Architect: <Compass size={20} />,
  Designer: <Palette size={20} />,
  FrontendDev: <Layout size={20} />,
  BackendDev: <Server size={20} />,
  QATester: <FlaskConical size={20} />,
  Reviewer: <ShieldCheck size={20} />,
  DocWriter: <FileText size={20} />
};

export default function OfficeFloorView({ 
  projects, 
  agentStates, 
  onAgentClick, 
  onFocusProject, 
  onDeleteProject,
  onOpenAddProject,
  onOpenStandup
}) {
  return (
    <div className="office-floor">
      {projects.map((project, idx) => {
        const agents = agentStates[project.project_id] || [];
        const techLead = agents.find((a) => a.role === 'TechLead');
        const teamAgents = agents.filter((a) => a.role !== 'TechLead');
        const roomTag = idx === 0 ? 'PROJECT 01' : 'PROJECT 02';

        return (
          <div key={project.project_id} className="office-room">
            <div className="room-header">
              <div className="room-title-area">
                <span className="room-tag">{roomTag}</span>
                <div>
                  <h2 className="room-title">{project.name}</h2>
                  <p className="room-workspace">{project.workspace_path}</p>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  className="view-btn"
                  onClick={() => onOpenStandup(project.project_id, project.name)}
                  style={{ color: '#d97706', borderColor: 'rgba(245, 158, 11, 0.4)' }}
                  title="Daily Standup Briefing"
                >
                  <span>👑 Standup</span>
                </button>
                <button
                  className="view-btn"
                  onClick={() => onFocusProject(project.project_id)}
                  title="Enter detailed project view"
                >
                  <Eye size={14} />
                  <span>Deep Dive</span>
                </button>
                <button
                  className="view-btn"
                  onClick={() => {
                    if (window.confirm(`Disconnect and remove project "${project.name}"?`)) {
                      onDeleteProject(project.project_id);
                    }
                  }}
                  title="Remove project workspace"
                  style={{ color: 'var(--text-muted)', padding: '6px 8px' }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>

            {/* Featured Tech Lead Desk */}
            {techLead && (
              <TechLeadCard
                agent={techLead}
                onOpenStandup={() => onOpenStandup(project.project_id, project.name)}
                onOpenWhisper={(role) => onAgentClick(project.project_id, role)}
              />
            )}

            {/* Sub-Agents Grid */}
            <div className="agent-desks-grid">
              {teamAgents.map((agent) => {
                const icon = ROLE_ICONS[agent.role] || <Bot size={20} />;
                const statusClass = `status-${agent.status}`;

                return (
                  <div
                    key={agent.role}
                    className={`agent-desk-card ${agent.status}`}
                    onClick={() => onAgentClick(project.project_id, agent.role)}
                    title={`Click to whisper instructions to ${agent.role}`}
                  >
                    <div className="agent-avatar-box">
                      {icon}
                    </div>
                    <span className="agent-role">{agent.role}</span>
                    <span className={`agent-status-badge ${statusClass}`}>
                      {agent.status}
                    </span>
                    <div className="thought-bubble" title={agent.thought || 'Idle'}>
                      {agent.thought || 'Standing by'}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Empty slot when fewer than 2 projects */}
      {projects.length < 2 && (
        <div 
          className="office-room" 
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
          <div style={{ width: '56px', height: '56px', borderRadius: '14px', background: 'var(--primary-subtle)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '14px' }}>
            <FolderPlus size={28} />
          </div>
          <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '4px' }}>
            Connect Project 02
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '280px', marginBottom: '16px' }}>
            Run a second project concurrently with an independent team of 7 AI agents.
          </p>
          <button className="dispatch-btn" style={{ fontSize: '13px', padding: '8px 16px' }}>
            + Add Workspace
          </button>
        </div>
      )}
    </div>
  );
}
