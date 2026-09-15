import React, { useState, useEffect } from 'react';
import {
  X, CheckCircle2, Zap, Clock, Users, FileText,
  ChevronDown, ChevronRight, Award, Bot,
  BarChart2, Copy, Check, Sparkles,
  Compass, Palette, Layout, Server, FlaskConical, ShieldCheck
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const ROLE_META = {
  TechLead:   { color: '#f59e0b', icon: Bot, label: 'Tech Lead' },
  Architect:  { color: '#8b5cf6', icon: Compass, label: 'Architect' },
  Designer:   { color: '#ec4899', icon: Palette, label: 'Designer' },
  FrontendDev:{ color: '#06b6d4', icon: Layout, label: 'Frontend Dev' },
  BackendDev: { color: '#10b981', icon: Server, label: 'Backend Dev' },
  QATester:   { color: '#ef4444', icon: FlaskConical, label: 'QA Tester' },
  Reviewer:   { color: '#6366f1', icon: ShieldCheck, label: 'Reviewer' },
  DocWriter:  { color: '#14b8a6', icon: FileText, label: 'Doc Writer' },
};

function AgentLogEntry({ log }) {
  const [expanded, setExpanded] = useState(false);
  const meta = ROLE_META[log.role] || { color: '#64748b', icon: Bot, label: log.role };
  const RoleIcon = meta.icon || Bot;

  return (
    <div style={{
      border: `1px solid ${meta.color}30`,
      borderRadius: 8,
      marginBottom: 8,
      overflow: 'hidden',
      background: `${meta.color}08`
    }}>
      <button
        onClick={() => setExpanded(e => !e)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 14px', background: 'none', border: 'none',
          cursor: 'pointer', textAlign: 'left'
        }}
      >
        <span style={{ color: meta.color, display: 'inline-flex', alignItems: 'center' }}>
          <RoleIcon size={16} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, color: meta.color, fontSize: 13 }}>{meta.label}</span>
            <span style={{
              background: `${meta.color}20`, color: meta.color,
              borderRadius: 4, padding: '1px 6px', fontSize: 11
            }}>{log.step_label}</span>
            {log.tokens_used > 0 && (
              <span style={{ color: '#64748b', fontSize: 11, marginLeft: 'auto' }}>
                <Zap size={10} style={{ display: 'inline', marginRight: 3 }} />
                {log.tokens_used.toLocaleString()} tokens
              </span>
            )}
          </div>
          {!expanded && log.response_text && (
            <div style={{ color: '#94a3b8', fontSize: 12, marginTop: 2,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 500 }}>
              {log.response_text.slice(0, 120)}{log.response_text.length > 120 ? '…' : ''}
            </div>
          )}
        </div>
        {expanded
          ? <ChevronDown size={14} style={{ color: '#64748b', flexShrink: 0 }} />
          : <ChevronRight size={14} style={{ color: '#64748b', flexShrink: 0 }} />}
      </button>
      {expanded && (
        <div style={{ padding: '0 14px 14px', borderTop: `1px solid ${meta.color}20` }}>
          <div style={{
            background: '#0f172a', borderRadius: 6, padding: '12px 14px',
            maxHeight: 280, overflowY: 'auto', marginTop: 10,
            fontFamily: 'monospace', fontSize: 12, lineHeight: 1.6,
            color: '#e2e8f0', whiteSpace: 'pre-wrap', wordBreak: 'break-word'
          }}>
            {log.response_text || '(no output recorded)'}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SprintCompletionModal({ sprint, projectId, onClose, onViewHistory }) {
  const [agentLogs, setAgentLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('summary');
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!sprint?.sprint_id || !projectId) return;
    setLoading(true);
    fetch(`/api/projects/${projectId}/sprints/${sprint.sprint_id}/agent-logs`)
      .then(r => r.json())
      .then(data => setAgentLogs(Array.isArray(data) ? data : []))
      .catch(() => setAgentLogs([]))
      .finally(() => setLoading(false));
  }, [sprint?.sprint_id, projectId]);

  if (!sprint) return null;

  const duration = sprint.completed_at && sprint.started_at
    ? Math.round(sprint.completed_at - sprint.started_at)
    : null;

  const uniqueAgents = [...new Set(agentLogs.map(l => l.role))];
  const totalTokens = sprint.total_tokens || agentLogs.reduce((s, l) => s + (l.tokens_used || 0), 0);

  const handleCopy = () => {
    navigator.clipboard.writeText(sprint.release_summary || '').then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div 
      onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 9000,
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20
      }}>
      <div style={{
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        border: '1px solid #334155',
        borderRadius: 16, width: '100%', maxWidth: 700,
        maxHeight: '90vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 24px 16px',
          borderBottom: '1px solid #1e293b',
          background: 'linear-gradient(135deg, rgba(16,185,129,0.08), rgba(99,102,241,0.08))',
          flexShrink: 0
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12,
                background: 'linear-gradient(135deg, #10b981, #059669)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0
              }}>
                <Sparkles size={22} color="#ffffff" />
              </div>
              <div>
                <span style={{
                  background: 'rgba(16,185,129,0.15)', color: '#10b981',
                  borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 700,
                  letterSpacing: 1, textTransform: 'uppercase'
                }}>Sprint Complete</span>
                <h2 style={{ margin: '4px 0 0', fontSize: 16, fontWeight: 700, color: '#f1f5f9', lineHeight: 1.3 }}>
                  {sprint.directive?.length > 80
                    ? sprint.directive.slice(0, 80) + '…'
                    : sprint.directive}
                </h2>
              </div>
            </div>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b', padding: 4, flexShrink: 0 }}>
              <X size={20} />
            </button>
          </div>

          {/* Stats */}
          <div style={{ display: 'flex', gap: 20, marginTop: 14, flexWrap: 'wrap' }}>
            {totalTokens > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                <Zap size={13} color="#f59e0b" />
                <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{totalTokens.toLocaleString()}</span>
                <span style={{ color: '#94a3b8' }}>tokens</span>
              </div>
            )}
            {duration !== null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                <Clock size={13} color="#06b6d4" />
                <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{duration}s</span>
                <span style={{ color: '#94a3b8' }}>duration</span>
              </div>
            )}
            {sprint.tasks_count > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                <CheckCircle2 size={13} color="#10b981" />
                <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{sprint.tasks_count}</span>
                <span style={{ color: '#94a3b8' }}>tasks</span>
              </div>
            )}
            {uniqueAgents.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                <Users size={13} color="#8b5cf6" />
                <span style={{ color: '#f1f5f9', fontWeight: 600 }}>{uniqueAgents.length}</span>
                <span style={{ color: '#94a3b8' }}>agents active</span>
              </div>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid #1e293b', flexShrink: 0 }}>
          {[
            { id: 'summary', label: 'Release Notes', icon: FileText },
            { id: 'agents', label: `Agent Logs${agentLogs.length ? ` (${agentLogs.length})` : ''}`, icon: Bot }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '11px 20px', background: 'none', border: 'none',
                cursor: 'pointer', fontSize: 13, fontWeight: 500,
                color: activeTab === tab.id ? '#6366f1' : '#64748b',
                borderBottom: activeTab === tab.id ? '2px solid #6366f1' : '2px solid transparent',
                transition: 'all 0.15s'
              }}
            >
              <tab.icon size={14} />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
          {activeTab === 'summary' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <Award size={14} color="#6366f1" />
                  <span style={{ color: '#94a3b8', fontSize: 13 }}>Reviewer's Release Notes</span>
                </div>
                <button
                  onClick={handleCopy}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    background: '#1e293b', border: '1px solid #334155',
                    borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
                    color: '#94a3b8', fontSize: 12
                  }}
                >
                  {copied ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <div style={{
                background: '#0f172a', borderRadius: 10, padding: '16px 18px',
                border: '1px solid #1e293b', minHeight: 80,
                color: '#cbd5e1', fontSize: 13.5, lineHeight: 1.8
              }}>
                {sprint.release_summary ? (
                  <div style={{ color: '#cbd5e1' }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {sprint.release_summary}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div style={{ color: '#475569', fontStyle: 'italic', textAlign: 'center', paddingTop: 20 }}>
                    No release notes available for this sprint.
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'agents' && (
            <div>
              {loading ? (
                <div style={{ textAlign: 'center', color: '#64748b', padding: '40px 0' }}>
                  <div style={{ fontSize: 13, marginTop: 8 }}>Loading agent logs…</div>
                </div>
              ) : agentLogs.length === 0 ? (
                <div style={{ textAlign: 'center', color: '#475569', padding: '40px 0' }}>
                  <Bot size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
                  <div style={{ fontSize: 14 }}>Agent logs will appear here on the next sprint.</div>
                  <div style={{ fontSize: 12, marginTop: 6, color: '#334155' }}>
                    Historical sprints run before this feature are not logged.
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ color: '#64748b', fontSize: 12, marginBottom: 14 }}>
                    Click any agent row to expand and see their full response for this sprint.
                  </div>
                  {agentLogs.map(log => (
                    <AgentLogEntry key={log.log_id} log={log} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '14px 24px', borderTop: '1px solid #1e293b',
          display: 'flex', gap: 10, justifyContent: 'flex-end',
          background: '#0a1020', flexShrink: 0
        }}>
          {onViewHistory && (
            <button
              onClick={() => { onViewHistory(); onClose(); }}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: '#1e293b', border: '1px solid #334155',
                borderRadius: 8, padding: '8px 16px', cursor: 'pointer',
                color: '#94a3b8', fontSize: 13
              }}
            >
              <BarChart2 size={14} />
              View Sprint History
            </button>
          )}
          <button
            onClick={onClose}
            style={{
              background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
              border: 'none', borderRadius: 8, padding: '8px 20px',
              cursor: 'pointer', color: '#fff', fontSize: 13, fontWeight: 600
            }}
          >
            Got it 👍
          </button>
        </div>
      </div>
    </div>
  );
}
