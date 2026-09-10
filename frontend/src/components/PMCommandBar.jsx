import React, { useState } from 'react';
import { Send, Zap, ShieldCheck } from 'lucide-react';

export default function PMCommandBar({ projects, activeProjectId, onSelectProject, onDispatchDirective }) {
  const [directive, setDirective] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!directive.trim() || !activeProjectId) return;
    setIsSubmitting(true);
    await onDispatchDirective(activeProjectId, directive);
    setDirective('');
    setIsSubmitting(false);
  };

  return (
    <form className="pm-command-bar" onSubmit={handleSubmit}>
      <div className="pm-badge">
        <Zap size={14} />
        <span>PM DIRECTIVE</span>
      </div>

      <select
        className="pm-project-select"
        value={activeProjectId || ''}
        onChange={(e) => onSelectProject(e.target.value)}
      >
        {projects.map((p) => (
          <option key={p.project_id} value={p.project_id}>
            {p.name} ({p.auto_pilot ? '⚡ Auto-Pilot' : '🛡️ Gate Mode'})
          </option>
        ))}
      </select>

      <input
        type="text"
        className="pm-input"
        placeholder="Type high-level product requirement... (e.g., 'Add OAuth2 login flow with Google and dark mode profile page')"
        value={directive}
        onChange={(e) => setDirective(e.target.value)}
        disabled={isSubmitting || projects.length === 0}
      />

      <button
        type="submit"
        className="dispatch-btn"
        disabled={isSubmitting || !directive.trim() || projects.length === 0}
      >
        <Send size={15} />
        <span>{isSubmitting ? 'DISPATCHING...' : 'DISPATCH TEAM'}</span>
      </button>
    </form>
  );
}
