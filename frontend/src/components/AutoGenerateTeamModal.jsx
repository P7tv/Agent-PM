import React, { useState } from 'react';
import { Sparkles, Bot, X, Check, Loader2, BookOpen, AlertCircle, RefreshCw } from 'lucide-react';

export default function AutoGenerateTeamModal({ 
  isOpen, 
  project, 
  onClose, 
  onConfirmTeam 
}) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [replaceExisting, setReplaceExisting] = useState(true);
  const [generatedResult, setGeneratedResult] = useState(null);
  const [error, setError] = useState('');

  if (!isOpen || !project) return null;

  const handleGenerate = async () => {
    try {
      setIsGenerating(true);
      setError('');
      const res = await fetch(`/api/projects/${project.project_id}/agents/auto-generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ replace_existing: replaceExisting })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to generate team');
      }
      const data = await res.json();
      setGeneratedResult(data);
      if (onConfirmTeam) {
        onConfirmTeam(data);
      }
    } catch (err) {
      setError(err.message || 'Error generating roster');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDone = () => {
    onClose();
    setGeneratedResult(null);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className="gate-modal" 
        style={{ maxWidth: '620px', width: '92%' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div className="gate-title" style={{ color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={20} />
            <span>AI-ALIGNED TEAM GENERATOR</span>
          </div>
          <button 
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Project Context Summary */}
        <div style={{
          background: 'var(--bg-canvas)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          padding: '12px 14px',
          marginBottom: '16px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>{project.name}</strong>
            <span style={{ 
              fontSize: '11px', 
              fontWeight: '700', 
              padding: '2px 8px', 
              borderRadius: '10px', 
              background: 'var(--primary-subtle)', 
              color: 'var(--primary)' 
            }}>
              Active Workspace
            </span>
          </div>
          <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', wordBreak: 'break-all' }}>
            📁 {project.workspace_path}
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

        {!generatedResult ? (
          <div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5', marginBottom: '16px' }}>
              Your AI Tech Lead will inspect the workspace's <strong>README</strong>, <strong>package dependencies</strong>, <strong>file topology</strong>, and <strong>domain modules</strong> to compose a specialized team of 3 to 5 sub-agents tailored specifically to this project's technical requirements.
            </p>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
              <input
                type="checkbox"
                id="replaceExistingCheck"
                checked={replaceExisting}
                onChange={(e) => setReplaceExisting(e.target.checked)}
                style={{ cursor: 'pointer', accentColor: 'var(--primary)' }}
              />
              <label htmlFor="replaceExistingCheck" style={{ fontSize: '13px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Replace current sub-agents with newly generated specialists (preserves Tech Lead)
              </label>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button className="view-btn" onClick={onClose} disabled={isGenerating}>
                Cancel
              </button>
              <button 
                className="dispatch-btn" 
                onClick={handleGenerate}
                disabled={isGenerating}
                style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 18px', fontSize: '13px' }}
              >
                {isGenerating ? (
                  <>
                    <Loader2 size={15} className="spin" />
                    <span>Analyzing Codebase & Synthesizing Team...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={15} />
                    <span>Generate AI Team</span>
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          <div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 14px',
              borderRadius: '6px',
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#10b981',
              fontSize: '13px',
              fontWeight: '600',
              marginBottom: '16px'
            }}>
              <Check size={16} />
              <span>{generatedResult.summary || 'Tailored team generated and deployed!'}</span>
            </div>

            <div style={{ maxHeight: '280px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px', paddingRight: '4px' }}>
              {generatedResult.agents?.map((agent) => (
                <div 
                  key={agent.role}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    background: 'var(--bg-canvas)',
                    border: '1px solid var(--border-subtle)'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: '700', fontSize: '13px', color: 'var(--text-primary)' }}>
                      {agent.skill_title || agent.role}
                    </span>
                    <span style={{
                      fontSize: '10px',
                      fontWeight: '700',
                      padding: '2px 6px',
                      borderRadius: '6px',
                      background: 'var(--primary-subtle)',
                      color: 'var(--primary)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}>
                      <BookOpen size={10} />
                      {agent.skill_name || 'custom'}
                    </span>
                  </div>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
                    {agent.thought || 'Ready to execute project tasks'}
                  </p>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button 
                className="dispatch-btn" 
                onClick={handleDone}
                style={{ fontSize: '13px', padding: '8px 20px' }}
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
