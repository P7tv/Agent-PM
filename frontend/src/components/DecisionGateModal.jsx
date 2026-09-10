import React, { useState } from 'react';
import { AlertCircle, CheckCircle2, XCircle, Send, MessageSquare } from 'lucide-react';

export function DecisionGateModal({ approval, onResolve }) {
  if (!approval) return null;

  return (
    <div className="modal-overlay">
      <div className="gate-modal">
        <div className="gate-title">
          <AlertCircle size={20} />
          <span>HUMAN PM APPROVAL REQUIRED</span>
        </div>
        <p className="gate-body">
          {approval.summary || 'The team has produced an implementation plan and is waiting for your review.'}
        </p>
        <div className="gate-actions">
          <button className="btn-reject" onClick={() => onResolve(approval.request_id, 'REJECTED')}>
            Reject / Revise
          </button>
          <button className="btn-approve" onClick={() => onResolve(approval.request_id, 'APPROVED')}>
            Approve & Proceed 🚀
          </button>
        </div>
      </div>
    </div>
  );
}

export function WhisperModal({ whisperTarget, onClose, onSendWhisper }) {
  const [message, setMessage] = useState('');
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
