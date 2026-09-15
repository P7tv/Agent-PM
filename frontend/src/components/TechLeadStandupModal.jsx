import React, { useState, useEffect } from 'react';
import { X, Crown, Activity, CheckCircle2, AlertTriangle, ArrowRight, Send, MessageSquare, Loader2, Sparkles, RotateCcw } from 'lucide-react';

export default function TechLeadStandupModal({ isOpen, onClose, projectId, projectName, theme }) {
  const [loading, setLoading] = useState(true);
  const [standup, setStandup] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [sendingChat, setSendingChat] = useState(false);

  useEffect(() => {
    if (!isOpen || !projectId) return;

    let isMounted = true;
    setLoading(true);

    const storageKey = `standup_chat_${projectId}`;
    let savedMsgs = null;
    try {
      const item = sessionStorage.getItem(storageKey);
      if (item) savedMsgs = JSON.parse(item);
    } catch (e) {}

    fetch(`/api/projects/${projectId}/standup`, { method: 'POST' })
      .then((res) => res.json())
      .then((data) => {
        if (isMounted) {
          setStandup(data);
          setLoading(false);
          if (savedMsgs && savedMsgs.length > 0) {
            setChatMessages(savedMsgs);
          } else {
            const initialGreeting = [
              {
                sender: 'lead',
                text: `Greetings! I am the Tech Lead for ${data.project_name || projectName}. Currently our project is ${data.health_status?.replace('_', ' ')} at ${data.progress_percent}% completion. Ask me anything about our tasks, architecture, or blockers!`
              }
            ];
            setChatMessages(initialGreeting);
            try { sessionStorage.setItem(storageKey, JSON.stringify(initialGreeting)); } catch (e) {}
          }
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error("Failed to load standup:", err);
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, projectId, projectName]);

  if (!isOpen) return null;

  const currentTheme = theme || (typeof document !== 'undefined' ? document.documentElement.getAttribute('data-theme') : 'light') || 'light';
  const isDark = currentTheme === 'dark';

  const handleResetChat = () => {
    const storageKey = `standup_chat_${projectId}`;
    const initialGreeting = [
      {
        sender: 'lead',
        text: `Greetings! I am the Tech Lead for ${standup?.project_name || projectName}. Currently our project is ${standup?.health_status?.replace('_', ' ')} at ${standup?.progress_percent}% completion. Ask me anything about our tasks, architecture, or blockers!`
      }
    ];
    setChatMessages(initialGreeting);
    try { sessionStorage.removeItem(storageKey); } catch (e) {}
  };

  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || sendingChat) return;

    const userMsg = chatInput.trim();
    setChatInput('');
    const newMsgs = [...chatMessages, { sender: 'user', text: userMsg }];
    setChatMessages(newMsgs);
    try { sessionStorage.setItem(`standup_chat_${projectId}`, JSON.stringify(newMsgs)); } catch (e) {}
    setSendingChat(true);

    try {
      const res = await fetch(`/api/projects/${projectId}/lead/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });
      const data = await res.json();
      const updatedMsgs = [...newMsgs, { sender: 'lead', text: data.message }];
      setChatMessages(updatedMsgs);
      try { sessionStorage.setItem(`standup_chat_${projectId}`, JSON.stringify(updatedMsgs)); } catch (e) {}
    } catch (err) {
      const fallbackMsgs = [
        ...newMsgs,
        { sender: 'lead', text: 'Sorry, I ran into an error retrieving that status. Please try again.' }
      ];
      setChatMessages(fallbackMsgs);
      try { sessionStorage.setItem(`standup_chat_${projectId}`, JSON.stringify(fallbackMsgs)); } catch (e) {}
    } finally {
      setSendingChat(false);
    }
  };

  const healthColor =
    standup?.health_status === 'ON_TRACK'
      ? (isDark ? '#34d399' : '#059669')
      : standup?.health_status === 'AT_RISK'
      ? (isDark ? '#fbbf24' : '#d97706')
      : (isDark ? '#fb7185' : '#dc2626');

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 300 }}>
      <div 
        className="standup-modal-container"
        onClick={(e) => e.stopPropagation()} 
      >
        {/* Header */}
        <div className="standup-modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 14px rgba(245, 158, 11, 0.35)',
              flexShrink: 0
            }}>
              <Crown size={24} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ fontSize: '17px', fontWeight: '700', color: isDark ? '#f8fafc' : '#0f172a', margin: 0 }}>
                  Daily Standup & Executive Briefing
                </h2>
                <span style={{
                  padding: '2px 8px',
                  borderRadius: '12px',
                  fontSize: '11px',
                  fontWeight: '700',
                  background: isDark ? 'rgba(59, 130, 246, 0.2)' : '#e0f2fe',
                  color: isDark ? '#93c5fd' : '#0284c7'
                }}>
                  {projectName}
                </span>
              </div>
              <p style={{ fontSize: '12px', color: isDark ? '#94a3b8' : '#475569', margin: '2px 0 0 0' }}>
                Synthesized live by Project Tech Lead • Team Health & Velocity
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: isDark ? '#1f293d' : '#f1f5f9',
              border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid #cbd5e1',
              color: isDark ? '#94a3b8' : '#475569',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body Content */}
        {loading ? (
          <div style={{ padding: '70px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Loader2 size={32} className="spin" style={{ margin: '0 auto 12px auto', color: 'var(--primary)' }} />
            <p style={{ fontSize: '14px', fontWeight: '500' }}>Tech Lead is compiling live sprint report...</p>
          </div>
        ) : standup ? (
          <div className="standup-modal-body">
            {/* Top Health & Progress Card */}
            <div className="standup-card" style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '20px'
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
                  <span style={{ color: isDark ? '#f8fafc' : '#0f172a', fontWeight: '600' }}>Overall Sprint Progress</span>
                  <span style={{ color: isDark ? '#f8fafc' : '#0f172a', fontWeight: '700' }}>{standup.progress_percent}%</span>
                </div>
                <div style={{ width: '100%', height: '8px', background: isDark ? 'rgba(255,255,255,0.1)' : '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${standup.progress_percent}%`,
                    height: '100%',
                    background: healthColor,
                    transition: 'width 0.5s ease',
                    borderRadius: '4px'
                  }} />
                </div>
              </div>

              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '7px 14px',
                borderRadius: '8px',
                background: isDark ? '#111827' : '#ffffff',
                border: `1.5px solid ${healthColor}`
              }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: healthColor }} />
                <span style={{ fontSize: '12px', fontWeight: '700', color: healthColor }}>
                  {standup.health_status?.replace('_', ' ')}
                </span>
              </div>
            </div>

            {/* Executive Summary Card (High Contrast) */}
            <div className="standup-summary-box">
              <div className="standup-summary-title">
                <Sparkles size={16} />
                <span>Executive Summary</span>
              </div>
              <p className="standup-summary-text">
                {standup.summary}
              </p>
            </div>

            {/* 4-Section Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '14px'
            }}>
              {/* Completed */}
              <div className="standup-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', color: isDark ? '#34d399' : '#059669', fontWeight: '700', fontSize: '13px' }}>
                  <CheckCircle2 size={16} />
                  <span>Completed ({standup.completed_items?.length || 0})</span>
                </div>
                {standup.completed_items?.length === 0 ? (
                  <p style={{ fontSize: '12px', color: isDark ? '#94a3b8' : '#64748b', fontStyle: 'italic', margin: 0 }}>No tasks completed yet.</p>
                ) : (
                  <ul className="standup-card-list" style={{ margin: 0, paddingLeft: '16px', fontSize: '12.5px', color: isDark ? '#f8fafc' : '#0f172a', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    {standup.completed_items.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* In Progress */}
              <div className="standup-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', color: isDark ? '#60a5fa' : '#2563eb', fontWeight: '700', fontSize: '13px' }}>
                  <Activity size={16} />
                  <span>Active & In-Progress ({standup.active_items?.length || 0})</span>
                </div>
                {standup.active_items?.length === 0 ? (
                  <p style={{ fontSize: '12px', color: isDark ? '#94a3b8' : '#64748b', fontStyle: 'italic', margin: 0 }}>Team standing by for directives.</p>
                ) : (
                  <ul className="standup-card-list" style={{ margin: 0, paddingLeft: '16px', fontSize: '12.5px', color: isDark ? '#f8fafc' : '#0f172a', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    {standup.active_items.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Blockers & Attention Needed */}
              <div className="standup-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', color: isDark ? '#fb7185' : '#dc2626', fontWeight: '700', fontSize: '13px' }}>
                  <AlertTriangle size={16} />
                  <span>Blockers & Attention ({standup.blockers?.length || 0})</span>
                </div>
                {standup.blockers?.length === 0 ? (
                  <p style={{ fontSize: '12px', color: isDark ? '#94a3b8' : '#64748b', fontStyle: 'italic', margin: 0 }}>Zero active blockers. All paths clear.</p>
                ) : (
                  <ul className="standup-card-list" style={{ margin: 0, paddingLeft: '16px', fontSize: '12.5px', color: isDark ? '#fb7185' : '#dc2626', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    {standup.blockers.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Next Priorities */}
              <div className="standup-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', color: isDark ? '#a78bfa' : '#7c3aed', fontWeight: '700', fontSize: '13px' }}>
                  <ArrowRight size={16} />
                  <span>Next Priorities</span>
                </div>
                <ul className="standup-card-list" style={{ margin: 0, paddingLeft: '16px', fontSize: '12.5px', color: isDark ? '#f8fafc' : '#0f172a', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  {standup.next_steps?.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Interactive Chat with Tech Lead */}
            <div className="standup-card" style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: '700', color: isDark ? '#f8fafc' : '#0f172a' }}>
                  <MessageSquare size={16} color="var(--primary)" />
                  <span>Ask Tech Lead Directly</span>
                </div>
                <button
                  type="button"
                  className="view-btn"
                  onClick={handleResetChat}
                  title="Reset conversation"
                  style={{ fontSize: '11px', padding: '2px 8px', display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <RotateCcw size={11} />
                  <span>Reset</span>
                </button>
              </div>

              {/* Chat Stream */}
              <div className="standup-chat-stream" style={{
                maxHeight: '120px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                padding: '10px 12px',
                borderRadius: '8px'
              }}>
                {chatMessages.map((msg, i) => (
                  <div 
                    key={i} 
                    className={msg.sender === 'user' ? 'standup-user-bubble' : 'standup-lead-bubble'}
                    style={{
                      alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                      maxWidth: '85%',
                      padding: '8px 12px',
                      borderRadius: '8px',
                      fontSize: '12.5px',
                      background: msg.sender === 'user' ? 'var(--primary)' : undefined,
                      color: msg.sender === 'user' ? '#ffffff' : undefined
                    }}
                  >
                    {msg.sender === 'lead' && (
                      <span style={{ fontWeight: '700', marginRight: '6px', color: isDark ? '#fbbf24' : '#d97706' }}>👑 Lead:</span>
                    )}
                    {msg.text}
                  </div>
                ))}
                {sendingChat && (
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic', paddingLeft: '8px' }}>
                    Tech Lead is thinking...
                  </div>
                )}
              </div>

              {/* Chat Input Bar */}
              <form onSubmit={handleSendChat} style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  className="pm-input"
                  style={{
                    flex: 1,
                    background: isDark ? '#0f1523' : '#ffffff',
                    border: isDark ? '1px solid rgba(255,255,255,0.15)' : '1px solid #cbd5e1',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    fontSize: '12.5px',
                    color: isDark ? '#f8fafc' : '#0f172a'
                  }}
                  placeholder="Ask about blockers, test results, architecture, or next tasks..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={sendingChat}
                />
                <button
                  type="submit"
                  className="view-btn"
                  style={{
                    background: 'var(--primary)',
                    color: '#ffffff',
                    border: 'none',
                    padding: '0 16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '12.5px',
                    fontWeight: '700',
                    cursor: 'pointer'
                  }}
                  disabled={sendingChat || !chatInput.trim()}
                >
                  <Send size={13} />
                  <span>Ask</span>
                </button>
              </form>
            </div>
          </div>
        ) : (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--accent-coral)' }}>
            Failed to load standup data.
          </div>
        )}
      </div>
    </div>
  );
}
