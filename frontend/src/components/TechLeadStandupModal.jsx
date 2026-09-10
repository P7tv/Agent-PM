import React, { useState, useEffect } from 'react';
import { X, Crown, Activity, CheckCircle2, Clock, AlertTriangle, ArrowRight, Send, MessageSquare, Loader2, Sparkles } from 'lucide-react';

export default function TechLeadStandupModal({ isOpen, onClose, projectId, projectName }) {
  const [loading, setLoading] = useState(true);
  const [standup, setStandup] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [sendingChat, setSendingChat] = useState(false);

  useEffect(() => {
    if (!isOpen || !projectId) return;

    let isMounted = true;
    setLoading(true);
    setChatMessages([]);

    fetch(`/api/projects/${projectId}/standup`, { method: 'POST' })
      .then((res) => res.json())
      .then((data) => {
        if (isMounted) {
          setStandup(data);
          setLoading(false);
          // Initial greeting from Tech Lead
          setChatMessages([
            {
              sender: 'lead',
              text: `Greetings! I am the Tech Lead for ${data.project_name || projectName}. Currently we are ${data.health_status?.replace('_', ' ')} at ${data.progress_percent}% completion. Ask me anything about our tasks, architecture, or blockers!`
            }
          ]);
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

  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || sendingChat) return;

    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages((prev) => [...prev, { sender: 'user', text: userMsg }]);
    setSendingChat(true);

    try {
      const res = await fetch(`/api/projects/${projectId}/lead/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });
      const data = await res.json();
      setChatMessages((prev) => [...prev, { sender: 'lead', text: data.message }]);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        { sender: 'lead', text: 'Sorry, I ran into an error retrieving that status. Please try again.' }
      ]);
    } finally {
      setSendingChat(false);
    }
  };

  const healthColor =
    standup?.health_status === 'ON_TRACK'
      ? 'var(--success)'
      : standup?.health_status === 'AT_RISK'
      ? 'var(--accent-amber)'
      : 'var(--accent-coral)';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className="standup-modal" 
        onClick={(e) => e.stopPropagation()} 
        style={{
          width: '100%',
          maxWidth: '820px',
          maxHeight: '90vh',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-medium)',
          borderRadius: '16px',
          boxShadow: '0 20px 50px rgba(0,0,0,0.3)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}
      >
        {/* Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--bg-panel)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(245, 158, 11, 0.3)'
            }}>
              <Crown size={22} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
                  Daily Standup & Executive Briefing
                </h2>
                <span style={{
                  padding: '2px 8px',
                  borderRadius: '12px',
                  fontSize: '11px',
                  fontWeight: '600',
                  background: 'var(--primary-subtle)',
                  color: 'var(--primary-text)'
                }}>
                  {projectName}
                </span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Conducted by Project Tech Lead • Real-time Team Synthesis
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '6px'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body Content */}
        {loading ? (
          <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Loader2 size={32} className="spin" style={{ margin: '0 auto 12px auto', color: 'var(--primary)' }} />
            <p style={{ fontSize: '14px' }}>Tech Lead is synthesizing team status...</p>
          </div>
        ) : standup ? (
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflowY: 'auto', padding: '24px', gap: '20px' }}>
            {/* Top Health & Progress Bar */}
            <div style={{
              background: 'var(--bg-canvas)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '12px',
              padding: '16px 20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '20px'
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
                  <span style={{ color: 'var(--text-secondary)', fontWeight: '500' }}>Overall Sprint Progress</span>
                  <span style={{ color: 'var(--text-primary)', fontWeight: '700' }}>{standup.progress_percent}%</span>
                </div>
                <div style={{ width: '100%', height: '8px', background: 'var(--border-subtle)', borderRadius: '4px', overflow: 'hidden' }}>
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
                padding: '8px 14px',
                borderRadius: '8px',
                background: 'var(--bg-card)',
                border: `1px solid ${healthColor}`
              }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: healthColor }} />
                <span style={{ fontSize: '12px', fontWeight: '700', color: healthColor }}>
                  {standup.health_status?.replace('_', ' ')}
                </span>
              </div>
            </div>

            {/* Executive Summary Card */}
            <div style={{
              background: 'var(--primary-subtle)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '12px',
              padding: '16px 20px',
              color: 'var(--text-primary)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: 'var(--primary-text)', fontWeight: '600', fontSize: '13px' }}>
                <Sparkles size={16} />
                <span>Executive Summary</span>
              </div>
              <p style={{ fontSize: '13px', lineHeight: '1.5', margin: 0, color: 'var(--text-secondary)' }}>
                {standup.summary}
              </p>
            </div>

            {/* 4-Section Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '16px'
            }}>
              {/* Completed */}
              <div style={{
                background: 'var(--bg-canvas)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '12px',
                padding: '16px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--success)', fontWeight: '600', fontSize: '13px' }}>
                  <CheckCircle2 size={16} />
                  <span>Completed ({standup.completed_items?.length || 0})</span>
                </div>
                {standup.completed_items?.length === 0 ? (
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>No tasks completed yet.</p>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {standup.completed_items.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* In Progress */}
              <div style={{
                background: 'var(--bg-canvas)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '12px',
                padding: '16px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--info-text)', fontWeight: '600', fontSize: '13px' }}>
                  <Activity size={16} />
                  <span>Active & In-Progress ({standup.active_items?.length || 0})</span>
                </div>
                {standup.active_items?.length === 0 ? (
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>Team standing by for directives.</p>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {standup.active_items.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Blockers & Attention Needed */}
              <div style={{
                background: 'var(--bg-canvas)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '12px',
                padding: '16px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--accent-coral)', fontWeight: '600', fontSize: '13px' }}>
                  <AlertTriangle size={16} />
                  <span>Blockers & Attention ({standup.blockers?.length || 0})</span>
                </div>
                {standup.blockers?.length === 0 ? (
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>Zero active blockers. All paths clear.</p>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: 'var(--accent-coral)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {standup.blockers.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Next Priorities */}
              <div style={{
                background: 'var(--bg-canvas)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '12px',
                padding: '16px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--accent-purple)', fontWeight: '600', fontSize: '13px' }}>
                  <ArrowRight size={16} />
                  <span>Next Priorities</span>
                </div>
                <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {standup.next_steps?.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Interactive Chat with Tech Lead */}
            <div style={{
              background: 'var(--bg-canvas)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '12px',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>
                <MessageSquare size={16} color="var(--primary)" />
                <span>Ask Tech Lead Directly</span>
              </div>

              {/* Chat Stream */}
              <div style={{
                maxHeight: '140px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                padding: '8px',
                background: 'var(--bg-card)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)'
              }}>
                {chatMessages.map((msg, i) => (
                  <div 
                    key={i} 
                    style={{
                      alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                      maxWidth: '85%',
                      padding: '6px 12px',
                      borderRadius: '8px',
                      fontSize: '12px',
                      background: msg.sender === 'user' ? 'var(--primary)' : 'var(--bg-panel)',
                      color: msg.sender === 'user' ? '#ffffff' : 'var(--text-primary)',
                      border: msg.sender === 'lead' ? '1px solid var(--border-subtle)' : 'none'
                    }}
                  >
                    {msg.sender === 'lead' && (
                      <span style={{ fontWeight: '700', marginRight: '6px', color: 'var(--accent-amber)' }}>👑 Lead:</span>
                    )}
                    {msg.text}
                  </div>
                ))}
                {sendingChat && (
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic', paddingLeft: '8px' }}>
                    Tech Lead is typing...
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
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    color: 'var(--text-primary)'
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
                    fontSize: '12px',
                    fontWeight: '600'
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
