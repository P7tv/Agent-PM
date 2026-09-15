import React, { useState } from 'react';
import { Send, TerminalSquare, Sparkles, ChevronDown, ListTodo, BookMarked } from 'lucide-react';

const DIRECTIVE_TEMPLATES = [
  { label: 'Feature: Auth', text: 'Implement user authentication with login, registration, JWT tokens, and password hashing.' },
  { label: 'Feature: Dark Mode', text: 'Add dark/light theme switching with CSS variables and localStorage persistence.' },
  { label: 'Feature: REST API', text: 'Create CRUD REST API endpoints with input validation, error handling, and tests.' },
  { label: 'Refactor: Clean Code', text: 'Refactor core services to improve modularity, add type hints, and remove duplicated logic.' },
  { label: 'QA: Full Test Suite', text: 'Write comprehensive unit and integration tests covering all critical paths and edge cases.' },
  { label: 'Doc: API Reference', text: 'Update project documentation, API endpoints reference, and environment setup instructions.' },
  { label: 'Fix: Performance', text: 'Identify and optimize slow queries, add database indices, and reduce payload sizes.' },
  { label: 'Fix: Security Audit', text: 'Audit dependencies for vulnerabilities, sanitize all user inputs, and add rate limiting.' },
  { label: 'DevOps: Dockerize', text: 'Create optimized multi-stage Dockerfile, docker-compose.yml, and deployment healthcheck.' },
];

export default function PMCommandBar({
  projects,
  activeProjectId,
  onSelectProject,
  onDispatchDirective,
  onOpenBacklog,
  onOpenJournal,
  sprintCost = { tokens: 0, costUSD: '0.00' }
}) {
  const [directive, setDirective] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!directive.trim() || !activeProjectId) return;
    setIsSubmitting(true);
    await onDispatchDirective(activeProjectId, directive);
    setDirective('');
    setIsSubmitting(false);
  };

  const handleSelectTemplate = (templateText) => {
    setDirective(templateText);
    setShowTemplates(false);
  };

  return (
    <div className="pm-command-bar-wrapper">
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

        <div className="pm-input-wrapper">
          <input
            type="text"
            className="pm-input"
            placeholder="Enter high-level requirement... (e.g., 'Implement user authentication with JWT')"
            value={directive}
            onChange={(e) => setDirective(e.target.value)}
            disabled={isSubmitting || projects.length === 0}
          />
          <button
            type="button"
            className="template-toggle-btn"
            onClick={() => setShowTemplates(!showTemplates)}
            title="Choose from directive templates"
          >
            <Sparkles size={13} />
            <span>Templates</span>
            <ChevronDown size={11} className={showTemplates ? 'rotate-180' : ''} />
          </button>
        </div>

        {/* Quick Backlog & Journal Access */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button
            type="button"
            className="template-toggle-btn"
            onClick={() => onOpenBacklog && onOpenBacklog(activeProjectId)}
            disabled={!activeProjectId}
            title="Open Product Backlog & Story Board"
            style={{ height: '32px', padding: '0 8px' }}
          >
            <ListTodo size={13} color="var(--primary)" />
            <span>Backlog</span>
          </button>
          <button
            type="button"
            className="template-toggle-btn"
            onClick={() => onOpenJournal && onOpenJournal(activeProjectId)}
            disabled={!activeProjectId}
            title="Open Agent Memory & Project Journal"
            style={{ height: '32px', padding: '0 8px' }}
          >
            <BookMarked size={13} color="#8b5cf6" />
            <span>Journal</span>
          </button>
        </div>

        {/* Session Token & Cost Badge */}
        <div className="pm-cost-badge" title="Session token usage and estimated cost">
          <span className="font-mono text-xs text-amber-300">
            🪙 {(sprintCost?.tokens || 0).toLocaleString()} tok
          </span>
          <span className="text-xs text-slate-400 font-mono">
            (${sprintCost?.costUSD || '0.00'})
          </span>
        </div>

        <button
          type="submit"
          className="dispatch-btn"
          disabled={isSubmitting || !directive.trim() || projects.length === 0}
        >
          <Send size={14} />
          <span>{isSubmitting ? 'Dispatching...' : 'Dispatch'}</span>
        </button>
      </form>

      {/* Template Chips Dropdown */}
      {showTemplates && (
        <div className="directive-templates-drawer">
          <div className="templates-header">
            <span className="text-xs font-semibold text-slate-400">SELECT A TEMPLATE TO PREFILL DIRECTIVE:</span>
            <button className="text-xs text-slate-400 hover:text-white" onClick={() => setShowTemplates(false)}>✕ Close</button>
          </div>
          <div className="template-chips-grid">
            {DIRECTIVE_TEMPLATES.map((tmpl, idx) => (
              <button
                key={idx}
                type="button"
                className="template-chip"
                onClick={() => handleSelectTemplate(tmpl.text)}
              >
                <span className="template-chip-label">{tmpl.label}</span>
                <span className="template-chip-preview">{tmpl.text}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
