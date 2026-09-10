import React from 'react';
import { Crown, MessageSquare, Radio, Sparkles, Activity } from 'lucide-react';

export default function TechLeadCard({ agent, onOpenStandup, onOpenWhisper }) {
  if (!agent) return null;

  const isThinking = agent.status === 'THINKING';
  const isWorking = agent.status === 'WORKING';
  const isBlocked = agent.status === 'BLOCKED';

  return (
    <div 
      className={`tech-lead-card ${agent.status}`}
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-medium)',
        borderRadius: '16px',
        padding: '20px 24px',
        marginBottom: '24px',
        position: 'relative',
        boxShadow: '0 4px 20px rgba(0,0,0,0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '24px',
        overflow: 'hidden'
      }}
    >
      {/* Decorative gradient border accent on top */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '4px',
        background: 'linear-gradient(90deg, #f59e0b 0%, #ec4899 50%, #6366f1 100%)'
      }} />

      {/* Left section: Avatar & Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
        <div 
          className="agent-avatar-box"
          style={{
            width: '52px',
            height: '52px',
            borderRadius: '14px',
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(217, 119, 6, 0.25) 100%)',
            border: '2px solid rgba(245, 158, 11, 0.4)',
            color: '#f59e0b',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: isThinking || isWorking ? '0 0 16px rgba(245, 158, 11, 0.4)' : 'none'
          }}
        >
          <Crown size={28} />
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
              Project Tech Lead
            </h3>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '2px 8px',
              borderRadius: '10px',
              fontSize: '11px',
              fontWeight: '700',
              background: 'rgba(245, 158, 11, 0.15)',
              color: '#d97706'
            }}>
              <Crown size={11} /> Team Head
            </span>
            <span className={`status-badge status-${agent.status}`}>
              {agent.status}
            </span>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
            {agent.thought || "Orchestrating sprint execution, monitoring team velocity, and handling PM status briefings."}
          </p>
        </div>
      </div>

      {/* Right section: Action buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <button
          onClick={() => onOpenWhisper(agent.role)}
          className="view-btn"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            fontSize: '12px',
            fontWeight: '600',
            color: 'var(--text-secondary)'
          }}
          title="Send private whisper to Tech Lead"
        >
          <MessageSquare size={14} />
          <span>Whisper</span>
        </button>

        <button
          onClick={onOpenStandup}
          className="view-btn active"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '9px 18px',
            fontSize: '13px',
            fontWeight: '700',
            background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
            color: '#ffffff',
            border: 'none',
            boxShadow: '0 4px 12px rgba(245, 158, 11, 0.3)'
          }}
          title="Open real-time executive daily standup briefing"
        >
          <Radio size={15} className={isWorking ? "spin" : ""} />
          <span>Daily Standup</span>
        </button>
      </div>
    </div>
  );
}
