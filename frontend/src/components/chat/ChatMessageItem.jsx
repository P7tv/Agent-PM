import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { RichCodeBlock } from './RichCodeBlock';
import { ActivityAccordion } from './ActivityAccordion';
import { User, Paperclip, FileCode2, CheckCircle2, Loader2, Play, XCircle } from 'lucide-react';

const ROLE_META = {
  TechLead: { color: '#f59e0b', emoji: '👑', label: 'Tech Lead' },
  Architect: { color: '#8b5cf6', emoji: '🏛️', label: 'Architect' },
  FrontendDev: { color: '#06b6d4', emoji: '⚛️', label: 'Frontend Dev' },
  BackendDev: { color: '#10b981', emoji: '⚙️', label: 'Backend Dev' },
  Designer: { color: '#ec4899', emoji: '🎨', label: 'Designer' },
  QATester: { color: '#ef4444', emoji: '🧪', label: 'QA Tester' },
  system: { color: '#64748b', emoji: '🔔', label: 'System' },
  user: { color: '#3b82f6', emoji: '👤', label: 'You' },
};

export function ChatMessageItem({ msg, onApply }) {
  const isUser = msg.sender === 'user';
  const meta = ROLE_META[msg.sender] || ROLE_META.system;

  return (
    <div style={{
      marginBottom: '24px', paddingBottom: '24px', borderBottom: '1px solid var(--border-subtle)',
      display: 'flex', flexDirection: 'column', gap: '8px'
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{
          width: '24px', height: '24px', borderRadius: '6px',
          background: isUser ? '#3b82f6' : `linear-gradient(135deg, ${meta.color}44, ${meta.color}22)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px',
          color: isUser ? '#fff' : meta.color, border: isUser ? 'none' : `1px solid ${meta.color}55`
        }}>
          {isUser ? <User size={14} /> : meta.emoji}
        </div>
        <span style={{ fontSize: '13px', fontWeight: 600, color: isUser ? 'var(--text-primary)' : meta.color }}>
          {isUser ? 'You' : meta.label}
        </span>
        {msg.created_at && (
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {new Date(msg.created_at).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Content */}
      <div style={{
        paddingLeft: '32px', fontSize: '13.5px', lineHeight: '1.65', color: 'var(--text-primary)',
        wordBreak: 'break-word',
        ...(isUser ? {
          background: 'rgba(59, 130, 246, 0.05)', borderLeft: '3px solid #3b82f6',
          padding: '12px 16px', borderRadius: '0 8px 8px 0', marginLeft: '32px'
        } : {})
      }}>
        {isUser ? (
          <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code: ({node, inline, className, children, ...props}) => {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <RichCodeBlock language={match[1]} code={String(children).replace(/\n$/, '')} onApply={onApply} />
                ) : (
                  <code style={{background: 'rgba(0,0,0,0.2)', padding: '2px 4px', borderRadius: '4px', fontFamily: 'var(--font-mono)'}} {...props}>
                    {children}
                  </code>
                )
              }
            }}
          >
            {msg.content}
          </ReactMarkdown>
        )}

        {/* Attachments */}
        {msg.attachments && msg.attachments.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
            {msg.attachments.map((att, idx) => (
              att.url.match(/\.(jpeg|jpg|gif|png|webp)$/i) ? (
                <img key={idx} src={att.url} alt={att.filename} style={{ maxHeight: '150px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }} />
              ) : (
                <a key={idx} href={att.url} target="_blank" rel="noopener noreferrer" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', padding: '6px 12px', background: 'var(--bg-surface)', borderRadius: '6px', color: 'var(--text-primary)', textDecoration: 'none', border: '1px solid var(--border-subtle)' }}>
                  <Paperclip size={12} /> {att.filename}
                </a>
              )
            ))}
          </div>
        )}
        {/* Code Proposals */}
        {msg.code_proposals && msg.code_proposals.length > 0 && (
          <div style={{ marginTop: '12px' }}>
            {msg.code_proposals.map((proposal, idx) => (
              <CodeProposalCard
                key={idx}
                proposal={proposal}
                projectId={msg.project_id}
                onApplied={onApply}
              />
            ))}
          </div>
        )}

        {/* QA Results */}
        {msg.qa_results && <QAResultCard qaResults={msg.qa_results} />}
      </div>
    </div>
  );
}

// ─── Code Proposal Card ──────────────────────────────────────
function CodeProposalCard({ proposal, projectId, onApplied }) {
  const [applying, setApplying] = React.useState(false);
  const [applied, setApplied] = React.useState(proposal.status === 'applied');
  const [rejected, setRejected] = React.useState(false);

  const handleApply = async () => {
    setApplying(true);
    try {
      const res = await fetch(`/api/projects/${projectId}/apply-change`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filepath: proposal.filepath,
          content: proposal.content,
          commit_message: `Agent applied: ${proposal.filepath}`
        })
      });
      if (res.ok) {
        setApplied(true);
        if (onApplied) onApplied(proposal.filepath);
      }
    } catch (err) {
      console.error('Apply failed:', err);
    } finally {
      setApplying(false);
    }
  };

  if (rejected) return null;

  return (
    <div style={{
      margin: '8px 0',
      border: applied ? '1px solid rgba(34, 197, 94, 0.4)' : '1px solid var(--border-medium)',
      borderRadius: '10px',
      background: applied ? 'rgba(34, 197, 94, 0.06)' : 'var(--bg-canvas)',
      overflow: 'hidden'
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '8px 12px',
        borderBottom: '1px solid var(--border-subtle)',
        background: applied ? 'rgba(34, 197, 94, 0.08)' : 'rgba(59, 130, 246, 0.06)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <FileCode2 size={13} color={applied ? '#22c55e' : '#3b82f6'} />
          <code style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-primary)' }}>
            {proposal.filepath}
          </code>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          {applied ? (
            <span style={{
              fontSize: '11px', fontWeight: '700', color: '#22c55e',
              display: 'flex', alignItems: 'center', gap: '4px'
            }}>
              <CheckCircle2 size={13} /> Applied & Committed
            </span>
          ) : (
            <>
              <button
                onClick={() => setRejected(true)}
                style={{
                  fontSize: '11px', padding: '3px 10px', borderRadius: '6px',
                  border: '1px solid rgba(239, 68, 68, 0.3)', background: 'transparent',
                  color: 'var(--accent-coral)', cursor: 'pointer', fontWeight: '600'
                }}
              >
                Skip
              </button>
              <button
                onClick={handleApply}
                disabled={applying}
                style={{
                  fontSize: '11px', padding: '3px 12px', borderRadius: '6px',
                  border: 'none', background: '#3b82f6', color: '#fff',
                  cursor: applying ? 'wait' : 'pointer', fontWeight: '700',
                  display: 'flex', alignItems: 'center', gap: '4px'
                }}
              >
                {applying ? <Loader2 size={11} className="spin" /> : <Play size={11} />}
                {applying ? 'Applying...' : 'Apply to File'}
              </button>
            </>
          )}
        </div>
      </div>
      {/* Code Preview */}
      <pre style={{
        margin: 0,
        padding: '10px 14px',
        fontSize: '11px',
        lineHeight: '1.5',
        fontFamily: 'var(--font-mono)',
        color: '#e2e8f0',
        background: '#0a0d14',
        maxHeight: '180px',
        overflowY: 'auto',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all'
      }}>
        {proposal.content}
      </pre>
    </div>
  );
}

// ─── QA Result Card ──────────────────────────────────────────
function QAResultCard({ qaResults }) {
  if (!qaResults) return null;
  const passed = qaResults.status === 'PASSED';
  return (
    <div style={{
      margin: '8px 0',
      border: `1px solid ${passed ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)'}`,
      borderRadius: '10px',
      background: passed ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
      overflow: 'hidden'
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '10px 14px',
        borderBottom: `1px solid ${passed ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`
      }}>
        {passed ? <CheckCircle2 size={16} color="#22c55e" /> : <XCircle size={16} color="#ef4444" />}
        <span style={{ fontSize: '13px', fontWeight: '700', color: passed ? '#22c55e' : '#ef4444' }}>
          Tests {qaResults.status} ({qaResults.command})
        </span>
      </div>
      {qaResults.stdout && (
        <pre style={{
          margin: 0, padding: '10px 14px', fontSize: '10.5px',
          fontFamily: 'var(--font-mono)', color: '#94a3b8',
          background: '#0a0d14', maxHeight: '200px', overflowY: 'auto',
          whiteSpace: 'pre-wrap'
        }}>
          {qaResults.stdout}
        </pre>
      )}
    </div>
  );
}
