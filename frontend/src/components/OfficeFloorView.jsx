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
  FolderPlus,
  BookOpen,
  Cpu,
  BrainCircuit,
  Database,
  Bug
} from 'lucide-react';
import TechLeadCard from './TechLeadCard';

const ROLE_ICONS = {
  TechLead: <Bot size={20} />,
  Architect: <Compass size={20} />,
  Designer: <Palette size={20} />,
  FrontendDev: <Layout size={20} />,
  BackendDev: <Server size={20} />,
  QATester: <FlaskConical size={20} />,
  Reviewer: <ShieldCheck size={20} />,
  DocWriter: <FileText size={20} />,
  DevOps: <Cpu size={20} />,
  Security: <ShieldCheck size={20} />,
  MLEngineer: <BrainCircuit size={20} />,
  DataEngineer: <Database size={20} />,
  SystematicDebugger: <Bug size={20} />
};

export default function OfficeFloorView({ 
  projects = [], 
  agentStates = {}, 
  onAgentClick, 
  onFocusProject, 
  onDeleteProject,
  onRequestDelete,
  onOpenAddProject,
  onOpenStandup
}) {
  const activeCount = projects.length;

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
                    if (onRequestDelete) {
                      onRequestDelete(project);
                    } else {
                      onDeleteProject(project.project_id);
                    }
                  }}
                  title="Remove project workspace"
                  style={{ color: 'var(--accent-coral)', borderColor: 'rgba(239, 68, 68, 0.25)', padding: '6px 8px' }}
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
                    <span className="agent-role">{agent.skill_title || agent.role}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', margin: '4px 0', flexWrap: 'wrap', justifyContent: 'center' }}>
                      <span className={`agent-status-badge ${statusClass}`}>
                        {agent.status}
                      </span>
                      {agent.skill_name && (
                        <span 
                          style={{
                            fontSize: '9px',
                            fontWeight: '700',
                            padding: '1px 5px',
                            borderRadius: '6px',
                            background: agent.skill_tier === 'project' ? 'rgba(245, 158, 11, 0.15)' : 'var(--primary-subtle)',
                            color: agent.skill_tier === 'project' ? '#d97706' : 'var(--primary-text)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '3px'
                          }}
                          title={`Assigned Skill: ${agent.skill_name} (${agent.skill_tier || 'stock'})`}
                        >
                          <BookOpen size={9} />
                          {agent.skill_name}
                        </span>
                      )}
                    </div>
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

      {/* Empty slot for Project 01 when 0 projects */}
      {projects.length === 0 && (
        <div 
          className="office-room" 
          style={{ 
            border: '2px dashed var(--primary)', 
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center', 
            justifyContent: 'center', 
            minHeight: '340px',
            textAlign: 'center',
            cursor: 'pointer',
            background: 'var(--bg-canvas)'
          }}
          onClick={onOpenAddProject}
        >
          <div style={{ width: '56px', height: '56px', borderRadius: '14px', background: 'var(--primary-subtle)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '14px' }}>
            <FolderPlus size={28} />
          </div>
          <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '4px' }}>
            Connect Project 01
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '300px', marginBottom: '16px' }}>
            Connect your primary project workspace to activate your AI PM orchestrator and multi-agent team.
          </p>
          <button className="dispatch-btn" style={{ fontSize: '13px', padding: '8px 18px' }}>
            + Add Workspace
          </button>
        </div>
      )}

      {/* Empty slot for Project 02 */}
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
            cursor: 'pointer',
            opacity: projects.length === 0 ? 0.65 : 1
          }}
          onClick={onOpenAddProject}
        >
          <div style={{ width: '56px', height: '56px', borderRadius: '14px', background: 'var(--border-subtle)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '14px' }}>
            <FolderPlus size={28} />
          </div>
          <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '4px' }}>
            Connect Project 02
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', maxWidth: '280px', marginBottom: '16px' }}>
            Run a second project concurrently with an independent team of AI specialists.
          </p>
          <button className="view-btn" style={{ fontSize: '12px', padding: '6px 14px' }}>
            + Add Second Project
          </button>
        </div>
      )}
    </div>
  );
}
