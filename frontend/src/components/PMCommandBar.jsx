import React, { useState } from 'react';
import { useToast } from './Toast';
import { Send, TerminalSquare, Sparkles, ChevronDown, ListTodo, BookMarked, SlidersHorizontal } from 'lucide-react';

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
  const toast = useToast();
  const [directive, setDirective] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showCriteria, setShowCriteria] = useState(false);
  const [criteriaText, setCriteriaText] = useState('');
  const [protectedText, setProtectedText] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!directive.trim() || !activeProjectId) return;
    setIsSubmitting(true);
    try {
      const lines = value => value.split('\n').map(item => item.trim()).filter(Boolean);
      await onDispatchDirective(activeProjectId, directive, {
        acceptance_criteria: lines(criteriaText),
        protected_paths: lines(protectedText),
      });
      setDirective('');
      setCriteriaText('');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsSubmitting(false);
    }
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
          <span>สั่งสร้างงาน</span>
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
            placeholder="อยากสร้างอะไร • ใครใช้ • ต้องทำอะไรได้ • หน้าตาแบบไหน"
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
        <div className="pm-quick-actions">
          <button
            type="button"
            className={`pm-quick-btn ${showCriteria ? 'active' : ''}`}
            onClick={() => setShowCriteria(!showCriteria)}
            title="Define acceptance criteria and protected files"
          >
            <SlidersHorizontal size={14} />
            <span>Criteria</span>
          </button>
          <button
            type="button"
            className="pm-quick-btn backlog-btn"
            onClick={() => onOpenBacklog && onOpenBacklog(activeProjectId)}
            disabled={!activeProjectId}
            title="Open Product Backlog & Story Board"
          >
            <ListTodo size={14} color="var(--primary)" />
            <span>Backlog</span>
          </button>
          <button
            type="button"
            className="pm-quick-btn journal-btn"
            onClick={() => onOpenJournal && onOpenJournal(activeProjectId)}
            disabled={!activeProjectId}
            title="Open Agent Memory & Project Journal"
          >
            <BookMarked size={14} color="#8b5cf6" />
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
      {showCriteria && (
        <div className="directive-criteria-drawer">
          <label>
            <strong>Acceptance criteria</strong>
            <span>หนึ่งเงื่อนไขต่อบรรทัด ระบบจะส่งให้ Architect, QA และ Reviewer ตรวจร่วมกัน</span>
            <textarea value={criteriaText} onChange={e => setCriteriaText(e.target.value)} placeholder={'ผู้ใช้เห็นสถานะของทุกขั้นตอน\nทดสอบ backend และ frontend ผ่านทั้งหมด'} />
          </label>
          <label>
            <strong>Protected paths</strong>
            <span>หนึ่ง path ต่อบรรทัด Agent จะแก้ไฟล์เหล่านี้ไม่ได้</span>
            <textarea value={protectedText} onChange={e => setProtectedText(e.target.value)} placeholder={'.env\ninfra/production'} />
          </label>
        </div>
      )}
    </div>
  );
}
