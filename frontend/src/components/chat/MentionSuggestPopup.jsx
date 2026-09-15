import React from 'react';
import { 
  Bot, Compass, Layout, Server, Palette, FlaskConical, Users 
} from 'lucide-react';

const AGENTS = [
  { role: 'TechLead', icon: Bot, label: 'Tech Lead', color: '#f59e0b' },
  { role: 'Architect', icon: Compass, label: 'Architect', color: '#8b5cf6' },
  { role: 'FrontendDev', icon: Layout, label: 'Frontend Dev', color: '#06b6d4' },
  { role: 'BackendDev', icon: Server, label: 'Backend Dev', color: '#10b981' },
  { role: 'Designer', icon: Palette, label: 'Designer', color: '#ec4899' },
  { role: 'QATester', icon: FlaskConical, label: 'QA Tester', color: '#ef4444' },
  { role: 'Team', icon: Users, label: 'Team Broadcast', color: '#3b82f6' }
];

export function MentionSuggestPopup({ x, y, onSelect }) {
  return (
    <div style={{
      position: 'absolute', bottom: y, left: x, background: 'var(--bg-canvas)',
      border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '6px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.3)', zIndex: 100, width: '220px',
      display: 'flex', flexDirection: 'column', gap: '2px'
    }}>
      {AGENTS.map(agent => {
        const IconComponent = agent.icon;
        return (
          <div key={agent.role} onClick={() => onSelect(agent.role)} style={{
            padding: '6px 10px', borderRadius: '4px', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px',
            color: 'var(--text-primary)'
          }} onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-surface)'}
             onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
            <span style={{ color: agent.color, display: 'inline-flex', alignItems: 'center' }}>
              <IconComponent size={15} />
            </span>
            <span style={{ fontWeight: 600 }}>{agent.role}</span>
          </div>
        );
      })}
    </div>
  );
}
