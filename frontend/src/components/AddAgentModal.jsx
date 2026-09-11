import React, { useState } from 'react';
import { Bot, X, Sparkles, AlertCircle, BookOpen, ShieldCheck, Bug, Cpu, Zap } from 'lucide-react';

const ROLE_TEMPLATES = [
  {
    role: 'SecurityAuditor',
    title: 'Security & Vulnerability Auditor',
    description: 'Audits authentication flows, dependency vulnerabilities, and API access boundaries.',
    skill: 'security-auditor'
  },
  {
    role: 'PerformanceEngineer',
    title: 'Latency & Core Web Vitals Specialist',
    description: 'Profiles render bottlenecks, memory leaks, query performance, and frame rates.',
    skill: 'performance-optimization'
  },
  {
    role: 'GamePhysicsDev',
    title: 'Physics & Simulation Engineer',
    description: 'Implements collision dynamics, movement equations, vehicle physics, and telemetry.',
    skill: 'systematic-debugger'
  },
  {
    role: 'DataSystemsDev',
    title: 'Data Pipelines & ETL Specialist',
    description: 'Builds batch processing, data normalization, database indexes, and cache layers.',
    skill: 'backend-dev'
  }
];

export default function AddAgentModal({ isOpen, project, onClose, onAddAgent }) {
  const [role, setRole] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [skillName, setSkillName] = useState('systematic-debugger');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen || !project) return null;

  const handleSelectTemplate = (tpl) => {
    setRole(tpl.role);
    setTitle(tpl.title);
    setDescription(tpl.description);
    setSkillName(tpl.skill);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!role.trim()) {
      setError('Please provide a Role identifier (e.g. SecurityAuditor)');
      return;
    }
    if (!title.trim()) {
      setError('Please provide a descriptive title');
      return;
    }
    if (!description.trim()) {
      setError('Please provide the specialist responsibility/description');
      return;
    }

    const cleanRole = role.replace(/[^a-zA-Z0-9_-]/g, '');
    if (!cleanRole) {
      setError('Role identifier must contain letters or numbers');
      return;
    }

    try {
      setIsSubmitting(true);
      setError('');
      await onAddAgent({
        role: cleanRole,
        title: title.trim(),
        description: description.trim(),
        skill_name: skillName || null,
        skill_tier: 'stock'
      });
      onClose();
      // Reset form
      setRole('');
      setTitle('');
      setDescription('');
    } catch (err) {
      setError(err.message || 'Failed to add custom agent');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className="gate-modal" 
        style={{ maxWidth: '540px', width: '90%' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div className="gate-title" style={{ color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Bot size={20} />
            <span>RECRUIT SPECIALIST AGENT</span>
          </div>
          <button 
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}
          >
            <X size={18} />
          </button>
        </div>

        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
          Add a custom specialist to <strong>{project.name}</strong>. The agent will execute tasks with this persona and automatically activate relevant playbooks.
        </p>

        {/* Quick Suggestion Chips */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px' }}>
            💡 Quick Templates
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {ROLE_TEMPLATES.map((tpl) => (
              <button
                key={tpl.role}
                type="button"
                className="view-btn"
                onClick={() => handleSelectTemplate(tpl)}
                style={{ fontSize: '11px', padding: '4px 10px', borderRadius: '12px' }}
              >
                + {tpl.title.split(' ')[0]} {tpl.title.split(' ')[1]}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px', 
            padding: '8px 12px', 
            borderRadius: '6px', 
            background: 'rgba(239, 68, 68, 0.15)', 
            color: 'var(--accent-coral)', 
            fontSize: '12px', 
            marginBottom: '14px' 
          }}>
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Role Identifier (PascalCase / Alphanumeric)
            </label>
            <input
              type="text"
              className="search-input"
              style={{ width: '100%', boxSizing: 'border-box' }}
              placeholder="e.g. GamePhysicsDev, SecurityAuditor"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              required
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Specialist Title
            </label>
            <input
              type="text"
              className="search-input"
              style={{ width: '100%', boxSizing: 'border-box' }}
              placeholder="e.g. Physics & Vehicle Dynamics Engineer"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Specialty Responsibility & Persona
            </label>
            <textarea
              className="search-input"
              style={{ width: '100%', minHeight: '64px', resize: 'vertical', boxSizing: 'border-box' }}
              placeholder="Describe what this agent specializes in (e.g. Simulates aerodynamic downforce, suspension dynamics, and tire grip telemetry)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: '4px' }}>
              Initial Assigned Skill Playbook
            </label>
            <select
              className="search-input"
              style={{ width: '100%', boxSizing: 'border-box' }}
              value={skillName}
              onChange={(e) => setSkillName(e.target.value)}
            >
              <option value="systematic-debugger">🐞 systematic-debugger (Systematic Root Cause Debugging)</option>
              <option value="security-auditor">🛡️ security-auditor (Vulnerability & Auth Auditor)</option>
              <option value="performance-optimization">⚡ performance-optimization (Web Vitals & Profiling)</option>
              <option value="frontend-dev">⚛️ frontend-dev (Modern UI & Component Logic)</option>
              <option value="backend-dev">⚙️ backend-dev (API & Core Systems)</option>
              <option value="qa-engineer">🧪 qa-engineer (Automated Testing & Pytest/Vitest)</option>
              <option value="devops-engineer">🚀 devops-engineer (Docker & CI/CD Pipelines)</option>
            </select>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button 
              type="button" 
              className="view-btn" 
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="dispatch-btn"
              style={{ fontSize: '13px', padding: '8px 18px', display: 'flex', alignItems: 'center', gap: '6px' }}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Recruiting...' : 'Recruit Specialist'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
