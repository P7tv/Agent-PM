import React, { useState } from 'react';
import { GitBranch, GitCommit, Copy, Check, Clock, User, ChevronDown, ChevronUp } from 'lucide-react';

export default function GitCommitGraph({ commits = [], branch = 'main' }) {
  const [copiedHash, setCopiedHash] = useState(null);
  const [expanded, setExpanded] = useState(false);

  if (!commits || commits.length === 0) {
    return (
      <div style={{
        padding: '24px',
        textAlign: 'center',
        color: 'var(--text-muted, #94a3b8)',
        fontSize: '12.5px',
        background: 'var(--bg-canvas, #090d16)',
        borderRadius: '10px',
        border: '1px solid var(--border-subtle, #334155)'
      }}>
        No commit history found on branch <code>{branch}</code>.
      </div>
    );
  }

  const handleCopyHash = (hash, e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const displayedCommits = expanded ? commits : commits.slice(0, 10);

  return (
    <div style={{
      background: 'var(--bg-card, #1e293b)',
      border: '1px solid var(--border-medium, #334155)',
      borderRadius: '12px',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      boxShadow: '0 4px 16px rgba(0, 0, 0, 0.2)'
    }}>
      {/* Header bar styled like VS Code Git Graph */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px 16px',
        background: 'var(--bg-surface, #0f172a)',
        borderBottom: '1px solid var(--border-subtle, #334155)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            background: 'rgba(56, 189, 248, 0.12)',
            border: '1px solid rgba(56, 189, 248, 0.35)',
            color: '#38bdf8',
            borderRadius: '6px',
            padding: '2px 8px',
            fontSize: '11px',
            fontWeight: '700'
          }}>
            <GitBranch size={13} />
            <span>{branch}</span>
          </div>
          <span style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-primary, #f8fafc)' }}>
            Git Commit Graph ({commits.length})
          </span>
        </div>

        {commits.length > 10 && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: 'transparent',
              border: '1px solid var(--border-subtle, #334155)',
              borderRadius: '6px',
              color: 'var(--text-muted, #94a3b8)',
              fontSize: '11px',
              padding: '3px 8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            {expanded ? (
              <>
                Show Latest 10 <ChevronUp size={13} />
              </>
            ) : (
              <>
                Show All ({commits.length}) <ChevronDown size={13} />
              </>
            )}
          </button>
        )}
      </div>

      {/* Tree Graph Container */}
      <div style={{
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: 'system-ui, -apple-system, sans-serif'
      }}>
        {displayedCommits.map((c, index) => {
          const isHead = index === 0;
          const isLast = index === displayedCommits.length - 1;

          return (
            <div
              key={c.hash || index}
              style={{
                display: 'flex',
                alignItems: 'center',
                position: 'relative',
                minHeight: '34px',
                padding: '2px 8px 2px 0',
                borderRadius: '6px',
                transition: 'background 0.15s ease'
              }}
              className="git-graph-row"
            >
              {/* Left Graph Column with Rail Track and Circular Nodes */}
              <div style={{
                position: 'relative',
                width: '32px',
                height: '34px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                {/* Vertical Rail Line */}
                <div style={{
                  position: 'absolute',
                  top: index === 0 ? '50%' : 0,
                  bottom: isLast ? '50%' : 0,
                  left: '50%',
                  width: '2px',
                  backgroundColor: '#38bdf8',
                  transform: 'translateX(-50%)',
                  zIndex: 1
                }} />

                {/* Node Dot */}
                {isHead ? (
                  /* HEAD Node: Hollow ring circle */
                  <div style={{
                    position: 'relative',
                    width: '14px',
                    height: '14px',
                    borderRadius: '50%',
                    border: '2.5px solid #38bdf8',
                    backgroundColor: 'var(--bg-card, #1e293b)',
                    zIndex: 2,
                    boxShadow: '0 0 8px rgba(56, 189, 248, 0.4)'
                  }} />
                ) : (
                  /* Regular Commit Node: Solid filled circle */
                  <div style={{
                    position: 'relative',
                    width: '9px',
                    height: '9px',
                    borderRadius: '50%',
                    backgroundColor: '#38bdf8',
                    zIndex: 2
                  }} />
                )}
              </div>

              {/* Commit Content */}
              <div style={{
                display: 'flex',
                flex: 1,
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
                overflow: 'hidden'
              }}>
                {/* Message + Branch Badge */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  minWidth: 0,
                  overflow: 'hidden'
                }}>
                  <span
                    title={c.message}
                    style={{
                      fontSize: '12px',
                      fontWeight: isHead ? '700' : '500',
                      color: isHead ? 'var(--text-primary, #f8fafc)' : 'var(--text-secondary, #cbd5e1)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis'
                    }}
                  >
                    {c.message}
                  </span>

                  {/* Branch badge for HEAD commit (matches VS Code Git Graph) */}
                  {isHead && (
                    <span style={{
                      flexShrink: 0,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      background: 'rgba(56, 189, 248, 0.18)',
                      border: '1px solid #38bdf8',
                      color: '#38bdf8',
                      borderRadius: '12px',
                      padding: '1px 8px',
                      fontSize: '10.5px',
                      fontWeight: '700'
                    }}>
                      <span style={{ fontSize: '9px' }}>◎</span>
                      {branch}
                    </span>
                  )}
                </div>

                {/* Meta details: Hash, Author, Time */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  flexShrink: 0
                }}>
                  {/* Monospace Hash Pill */}
                  <button
                    onClick={(e) => handleCopyHash(c.hash, e)}
                    title="Click to copy commit hash"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                      background: 'var(--bg-surface, #0f172a)',
                      border: '1px solid var(--border-subtle, #334155)',
                      borderRadius: '5px',
                      padding: '2px 6px',
                      fontFamily: 'ui-monospace, monospace',
                      fontSize: '11px',
                      color: '#38bdf8',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {copiedHash === c.hash ? (
                      <>
                        <Check size={11} color="#34d399" />
                        <span style={{ color: '#34d399' }}>Copied</span>
                      </>
                    ) : (
                      <>
                        <span>{c.hash}</span>
                        <Copy size={10} style={{ opacity: 0.6 }} />
                      </>
                    )}
                  </button>

                  {/* Author & Time */}
                  <span style={{
                    fontSize: '11px',
                    color: 'var(--text-muted, #94a3b8)',
                    whiteSpace: 'nowrap'
                  }}>
                    {c.author} • {c.time}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
