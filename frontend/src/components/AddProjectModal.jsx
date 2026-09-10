import React, { useState, useEffect } from 'react';
import { Plus, X, FolderKanban, AlertCircle, CheckCircle2, Cpu, ShieldCheck, Loader2 } from 'lucide-react';

export default function AddProjectModal({ isOpen, onClose, onAddProject }) {
  const [name, setName] = useState('');
  const [workspacePath, setWorkspacePath] = useState('');
  const [autoPilot, setAutoPilot] = useState(false);
  
  // Guardrail & Inspector state
  const [isValidating, setIsValidating] = useState(false);
  const [guardrailResult, setGuardrailResult] = useState(null); // { valid, message, metadata }
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  useEffect(() => {
    if (!workspacePath.trim()) {
      setGuardrailResult(null);
      return;
    }

    const timer = setTimeout(async () => {
      setIsValidating(true);
      try {
        const res = await fetch('/api/projects/validate-path', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: workspacePath.trim() })
        });
        const data = await res.json();
        setGuardrailResult(data);

        // Auto-fill project name if empty and suggested_name exists
        if (data.valid && data.metadata?.suggested_name && !name) {
          setName(data.metadata.suggested_name);
        }
      } catch (err) {
        setGuardrailResult({ valid: false, message: 'Inspection service error' });
      } finally {
        setIsValidating(false);
      }
    }, 350);

    return () => clearTimeout(timer);
  }, [workspacePath]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !workspacePath.trim() || !guardrailResult?.valid) return;
    setIsSubmitting(true);
    setSubmitError('');
    try {
      const projectId = name.toLowerCase().replace(/[^a-z0-9]/g, '-').slice(0, 16);
      await onAddProject({
        project_id: projectId,
        name: name.trim(),
        workspace_path: workspacePath.trim(),
        auto_pilot: autoPilot
      });
      setName('');
      setWorkspacePath('');
      setGuardrailResult(null);
      onClose();
    } catch (err) {
      setSubmitError(err.message || 'Failed to add project');
    } finally {
      setIsSubmitting(false);
    }
  };

  const meta = guardrailResult?.metadata;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="whisper-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '480px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', fontWeight: '600' }}>
            <FolderKanban size={18} color="var(--primary)" />
            <span>Connect & Analyze Project Workspace</span>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={16} />
          </button>
        </div>

        {submitError && (
          <div style={{ padding: '8px 12px', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: '6px', fontSize: '12px', marginBottom: '12px' }}>
            {submitError}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Path input with real-time Guardrail indicator */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: '500' }}>
                Local Project Directory Path
              </label>
              {isValidating && (
                <span style={{ fontSize: '11px', color: 'var(--primary-text)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Loader2 size={11} className="spin" /> Scanning codebase...
                </span>
              )}
            </div>
            <input
              type="text"
              className="pm-input"
              style={{ width: '100%', background: 'var(--bg-canvas)', padding: '9px 12px', borderRadius: '6px', border: `1px solid ${guardrailResult ? (guardrailResult.valid ? 'var(--success)' : 'var(--accent-coral)') : 'var(--border-subtle)'}`, color: 'var(--text-primary)', fontSize: '13px' }}
              placeholder="/Users/panpan/projects/my-app"
              value={workspacePath}
              onChange={(e) => setWorkspacePath(e.target.value)}
              required
              autoFocus
            />

            {/* Guardrail feedback banner */}
            {guardrailResult && !isValidating && (
              <div style={{
                marginTop: '8px',
                padding: '10px 12px',
                borderRadius: '6px',
                background: guardrailResult.valid ? 'var(--success-subtle)' : 'rgba(239, 68, 68, 0.1)',
                border: `1px solid ${guardrailResult.valid ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`,
                fontSize: '12px',
                display: 'flex',
                gap: '8px',
                alignItems: 'flex-start'
              }}>
                {guardrailResult.valid ? (
                  <CheckCircle2 size={16} color="var(--success)" style={{ marginTop: '1px', flexShrink: 0 }} />
                ) : (
                  <AlertCircle size={16} color="#ef4444" style={{ marginTop: '1px', flexShrink: 0 }} />
                )}
                <div>
                  <div style={{ fontWeight: '600', color: guardrailResult.valid ? 'var(--success-text)' : '#ef4444' }}>
                    {guardrailResult.valid ? 'Guardrail Check Passed' : 'Guardrail Alert'}
                  </div>
                  <div style={{ color: 'var(--text-secondary)', marginTop: '2px', lineHeight: '1.4' }}>
                    {guardrailResult.message}
                  </div>

                  {/* Codebase insights & dynamic agents tailored preview */}
                  {guardrailResult.valid && meta && (
                    <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(16, 185, 129, 0.15)' }}>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                        <span className="room-tag" style={{ background: 'var(--bg-surface)', fontSize: '10px' }}>
                          📦 {meta.stack_type}
                        </span>
                        {meta.frameworks?.map((fw) => (
                          <span key={fw} className="room-tag" style={{ background: 'var(--bg-surface)', fontSize: '10px' }}>
                            {fw}
                          </span>
                        ))}
                        <span className="room-tag" style={{ background: 'var(--bg-surface)', fontSize: '10px' }}>
                          📁 {meta.file_count} active files
                        </span>
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Cpu size={12} color="var(--primary)" />
                        <span>AI will tailor subagents specifically for this {meta.stack_type} codebase.</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div>
            <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px', fontWeight: '500' }}>
              Project Name
            </label>
            <input
              type="text"
              className="pm-input"
              style={{ width: '100%', background: 'var(--bg-canvas)', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
              placeholder="e.g. Core Engine"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
            <input
              type="checkbox"
              id="autoPilotCheckbox"
              checked={autoPilot}
              onChange={(e) => setAutoPilot(e.target.checked)}
              style={{ cursor: 'pointer', accentColor: 'var(--primary)' }}
            />
            <label htmlFor="autoPilotCheckbox" style={{ fontSize: '13px', color: 'var(--text-primary)', cursor: 'pointer' }}>
              Enable Auto-Pilot (Agents execute autonomously without approval stops)
            </label>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
            <button type="button" className="btn-reject" onClick={onClose}>
              Cancel
            </button>
            <button 
              type="submit" 
              className="dispatch-btn" 
              disabled={isSubmitting || isValidating || !guardrailResult?.valid || !name.trim()}
            >
              {isSubmitting ? 'Analyzing & Initializing...' : 'Connect & Tailor Team'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
