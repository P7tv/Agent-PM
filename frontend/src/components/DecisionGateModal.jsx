import React, { useState, useEffect } from 'react';
import { 
  AlertCircle, 
  CheckCircle2, 
  XCircle, 
  Send, 
  MessageSquare, 
  Lightbulb, 
  Bot, 
  Rocket 
} from 'lucide-react';

export function DecisionGateModal({ approval, onResolve }) {
  const [feedbackMode, setFeedbackMode] = useState(false);
  const [feedback, setFeedback] = useState('');

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (feedbackMode) {
          setFeedbackMode(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [feedbackMode]);

  if (!approval) return null;

  const handleInjectAndApprove = () => {
    onResolve(approval.request_id, 'APPROVED');
    setFeedbackMode(false);
    setFeedback('');
  };

  const handleLetAIDecide = () => {
    onResolve(approval.request_id, 'APPROVED');
  };

  return (
    <div className="modal-overlay">
      <div className="gate-modal">
        <div className="gate-title">
          <AlertCircle size={20} />
          <span>HUMAN PM APPROVAL REQUIRED</span>
        </div>
        <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: '8px' }}>
          {approval.gate_type || 'PLAN_APPROVAL'}
        </div>
        <p className="gate-body">
          {approval.summary || 'The team has produced an implementation plan and is waiting for your review.'}
        </p>

        {feedbackMode && (
          <div style={{ marginBottom: '16px' }}>
            <textarea
              style={{
                width: '100%',
                height: '80px',
                background: 'var(--bg-canvas)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
                padding: '8px 10px',
                fontFamily: 'var(--font-sans)',
                fontSize: '13px',
                outline: 'none',
                resize: 'vertical'
              }}
              placeholder="e.g. 'Use SQLite instead of PostgreSQL' or 'Make sure dark mode is default'..."
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              autoFocus
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' }}>
              <button className="btn-reject" onClick={() => { setFeedbackMode(false); setFeedback(''); }}>
                Cancel
              </button>
              <button 
                className="btn-approve" 
                onClick={handleInjectAndApprove} 
                disabled={!feedback.trim()}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                <Lightbulb size={14} />
                <span>Inject & Approve</span>
              </button>
            </div>
          </div>
        )}

        {!feedbackMode && (
          <div className="gate-actions" style={{ flexWrap: 'wrap' }}>
            <button 
              className="btn-reject" 
              onClick={() => onResolve(approval.request_id, 'REJECTED')}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              <XCircle size={14} />
              <span>Reject / Revise</span>
            </button>
            <button
              className="view-btn"
              style={{ border: '1px solid var(--border-medium)', padding: '8px 14px', fontSize: '13px', fontWeight: '600', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              onClick={() => setFeedbackMode(true)}
            >
              <Lightbulb size={14} />
              <span>Inject Feedback</span>
            </button>
            <button
              className="view-btn"
              style={{ border: '1px solid var(--border-medium)', padding: '8px 14px', fontSize: '13px', fontWeight: '600', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              onClick={handleLetAIDecide}
            >
              <Bot size={14} />
              <span>Let AI Decide</span>
            </button>
            <button 
              className="btn-approve" 
              onClick={() => onResolve(approval.request_id, 'APPROVED')}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              <Rocket size={14} />
              <span>Approve & Proceed</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export function WhisperModal({ whisperTarget, onClose, onSendWhisper }) {
  const [message, setMessage] = useState('');

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    if (whisperTarget) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [whisperTarget, onClose]);

  if (!whisperTarget) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!message.trim()) return;
    onSendWhisper(whisperTarget.projectId, whisperTarget.role, message);
    setMessage('');
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="whisper-modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-cyan)', fontWeight: '700' }}>
          <MessageSquare size={18} />
          <span>WHISPER TO {whisperTarget.role.toUpperCase()}</span>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
          Inject advice, ideas, or architectural constraints directly into this agent.
        </p>
        <form onSubmit={handleSubmit}>
          <textarea
            className="whisper-textarea"
            placeholder="e.g. 'Use SQLite and make sure dark mode is default...'"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            autoFocus
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
            <button type="button" className="btn-reject" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="dispatch-btn" style={{ padding: '8px 16px', fontSize: '13px' }}>
              <Send size={14} />
              <span>Send Whisper</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
