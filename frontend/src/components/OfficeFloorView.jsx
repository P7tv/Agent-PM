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
  Eye 
} from 'lucide-react';

const ROLE_ICONS = {
  Architect: <Compass size={20} />,
  Designer: <Palette size={20} />,
  FrontendDev: <Layout size={20} />,
  BackendDev: <Server size={20} />,
  QATester: <FlaskConical size={20} />,
  Reviewer: <ShieldCheck size={20} />,
  DocWriter: <FileText size={20} />
};

export default function OfficeFloorView({ projects, agentStates, onAgentClick, onFocusProject }) {
  return (
    <div className="office-floor">
      {projects.map((project, idx) => {
        const agents = agentStates[project.project_id] || [];
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
              <button
                className="view-btn"
                onClick={() => onFocusProject(project.project_id)}
                title="Enter detailed project view"
              >
                <Eye size={14} />
                <span>Deep Dive</span>
              </button>
            </div>

            <div className="agent-desks-grid">
              {agents.map((agent) => {
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
    </div>
  );
}
