import React from 'react';
import { ExternalLink, MessageSquare, Terminal, Eye } from 'lucide-react';

const ROLE_AVATARS = {
  Architect: '📐',
  Designer: '🎨',
  FrontendDev: '💻',
  BackendDev: '⚙️',
  QATester: '🧪',
  Reviewer: '🛡️',
  DocWriter: '📝'
};

export default function OfficeFloorView({ projects, agentStates, onAgentClick, onFocusProject }) {
  return (
    <div className="office-floor">
      {projects.map((project, idx) => {
        const agents = agentStates[project.project_id] || [];
        const roomName = idx === 0 ? 'DEPARTMENT ALPHA' : 'DEPARTMENT BETA';

        return (
          <div key={project.project_id} className="office-room">
            <div className="room-header">
              <div className="room-title-area">
                <span className="room-tag">{roomName}</span>
                <div>
                  <h2 className="room-title">{project.name}</h2>
                  <p className="room-workspace">{project.workspace_path}</p>
                </div>
              </div>
              <button
                className="view-btn"
                onClick={() => onFocusProject(project.project_id)}
                title="Enter Focus War Room"
              >
                <Eye size={14} />
                <span>ENTER ROOM</span>
              </button>
            </div>

            <div className="agent-desks-grid">
              {agents.map((agent) => {
                const avatar = ROLE_AVATARS[agent.role] || '🤖';
                const statusClass = `status-${agent.status}`;

                return (
                  <div
                    key={agent.role}
                    className={`agent-desk-card ${agent.status}`}
                    onClick={() => onAgentClick(project.project_id, agent.role)}
                    title={`Click to whisper instructions to ${agent.role}`}
                  >
                    <div className="agent-avatar">
                      {avatar}
                    </div>
                    <span className="agent-role">{agent.role}</span>
                    <span className={`agent-status-badge ${statusClass}`}>
                      {agent.status}
                    </span>
                    <div className="thought-bubble" title={agent.thought || 'Idle'}>
                      {agent.thought || 'Waiting at desk...'}
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
