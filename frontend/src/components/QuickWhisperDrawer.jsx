import React, { useState, useEffect } from 'react';
import { 
  X, 
  Send, 
  Bot, 
  ExternalLink, 
  Loader2, 
  BookOpen, 
  Sparkles,
  MessageSquare,
  Copy,
  Check
} from 'lucide-react';
import { useToast } from './Toast';

export default function QuickWhisperDrawer({
  isOpen,
  onClose,
  project,
  agent,
  onSendWhisper,
  onDeepDive
}) {
  const toast = useToast();
  const [whisperText, setWhisperText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, onClose]);

  if (!isOpen || !agent || !project) return null;

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    if (!whisperText.trim() || isSending) return;
    setIsSending(true);
    try {
      if (onSendWhisper) {
        await onSendWhisper(project.project_id, agent.role, whisperText);
      }
      toast.success(`Whisper sent to ${agent.skill_title || agent.role}`);
      setWhisperText('');
    } catch (err) {
      console.error('Failed to send whisper:', err);
      toast.error('Failed to send whisper');
    } finally {
      setIsSending(false);
    }
  };

  const handleCopyThought = () => {
    if (agent.thought) {
      navigator.clipboard.writeText(agent.thought);
      setCopied(true);
      toast.info('Agent thought copied to clipboard');
      setTimeout(() => setCopied(false), 1800);
    }
  };

  const QUICK_PROMPTS = [
    "What is your current status and focus?",
    "Review latest changes for potential errors.",
    "Stand by for next sprint directive."
  ];

  const statusClass = `status-${agent.status}`;

  return (
    <div className="whisper-drawer-backdrop" onClick={onClose}>
      <div className="whisper-drawer-panel" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="whisper-drawer-header">
          <div className="whisper-drawer-title-row">
            <div className="whisper-avatar-wrap">
              <Bot size={22} color="var(--primary)" />
            </div>
            <div>
              <div className="whisper-agent-title">
                {agent.skill_title || agent.role}
              </div>
              <div className="whisper-project-sub">
                {project.name} · <span style={{ color: 'var(--text-muted)' }}>{project.workspace_path}</span>
              </div>
            </div>
          </div>
          <button 
            className="whisper-drawer-close-btn"
            onClick={onClose}
            title="Close Drawer (Esc)"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body Content */}
        <div className="whisper-drawer-body">
          {/* Status & Skill Bar */}
          <div className="whisper-meta-card">
            <div className="whisper-meta-item">
              <span className="whisper-meta-label">Status</span>
              <span className={`agent-status-badge ${statusClass}`}>
                {agent.status}
              </span>
            </div>
            {agent.skill_name && (
              <div className="whisper-meta-item">
                <span className="whisper-meta-label">Active Skill</span>
                <span className="whisper-skill-pill" title={`Tier: ${agent.skill_tier || 'stock'}`}>
                  <BookOpen size={11} />
                  <span>{agent.skill_name}</span>
                </span>
              </div>
            )}
          </div>

          {/* Current Thought / Persona Card */}
          <div className="whisper-thought-section">
            <div className="whisper-section-header">
              <span className="whisper-section-title">Current Thought & Reasoning</span>
              {agent.thought && (
                <button 
                  className="whisper-copy-btn" 
                  onClick={handleCopyThought}
                  title="Copy thought text"
                >
                  {copied ? <Check size={12} color="var(--success)" /> : <Copy size={12} />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              )}
            </div>
            <div className="whisper-thought-box">
              <div className="thought-quote-mark">“</div>
              <p className="thought-body-text">
                {agent.thought || 'Agent is idle and standing by for PM instructions.'}
              </p>
            </div>
          </div>

          {/* Quick Whisper Input Form */}
          <div className="whisper-input-section">
            <label className="whisper-section-title">
              <MessageSquare size={13} style={{ marginRight: '6px', verticalAlign: 'middle' }} />
              Whisper Direct Instruction
            </label>
            <form onSubmit={handleSend} className="whisper-form">
              <textarea
                className="whisper-textarea"
                rows={3}
                placeholder={`Type a private message or instruction to ${agent.role}...`}
                value={whisperText}
                onChange={(e) => setWhisperText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    handleSend(e);
                  }
                }}
              />
              
              {/* Quick Prompts */}
              <div className="whisper-quick-prompts">
                {QUICK_PROMPTS.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="whisper-quick-chip"
                    onClick={() => setWhisperText(p)}
                  >
                    <Sparkles size={10} />
                    <span>{p}</span>
                  </button>
                ))}
              </div>

              <div className="whisper-form-actions">
                <span className="whisper-shortcut-hint">Press Ctrl+Enter to send</span>
                <button
                  type="submit"
                  className="dispatch-btn"
                  disabled={isSending || !whisperText.trim()}
                  style={{ padding: '7px 16px', fontSize: '12px' }}
                >
                  {isSending ? <Loader2 size={13} className="spin" /> : <Send size={13} />}
                  <span>{isSending ? 'Sending...' : 'Send Whisper'}</span>
                </button>
              </div>
            </form>
          </div>

          {/* Deep Dive Action */}
          <div className="whisper-footer-action">
            <button
              type="button"
              className="view-btn whisper-deep-dive-btn"
              onClick={() => {
                onClose();
                if (onDeepDive) onDeepDive(project.project_id);
              }}
            >
              <span>Open Full Project Workspace ({project.name})</span>
              <ExternalLink size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
