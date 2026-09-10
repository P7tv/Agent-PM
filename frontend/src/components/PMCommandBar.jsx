import React, { useState } from 'react';
import { Send, TerminalSquare } from 'lucide-react';

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
        <TerminalSquare size={14} />
        <span>DIRECTIVE</span>
      </div>

      <select
        className="pm-project-select"
        value={activeProjectId || ''}
        onChange={(e) => onSelectProject(e.target.value)}
      >
        {projects.map((p) => (
          <option key={p.project_id} value={p.project_id}>
            {p.name} ({p.auto_pilot ? 'Auto-Pilot' : 'Gate Mode'})
          </option>
        ))}
      </select>

      <input
        type="text"
        className="pm-input"
        placeholder="Enter high-level requirement... (e.g., 'Implement user authentication with JWT and email verification')"
        value={directive}
        onChange={(e) => setDirective(e.target.value)}
        disabled={isSubmitting || projects.length === 0}
      />

      <button
        type="submit"
        className="dispatch-btn"
        disabled={isSubmitting || !directive.trim() || projects.length === 0}
      >
        <Send size={14} />
        <span>{isSubmitting ? 'Dispatching...' : 'Dispatch'}</span>
      </button>
    </form>
  );
}
