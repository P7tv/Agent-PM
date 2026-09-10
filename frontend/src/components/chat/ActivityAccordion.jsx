import React, { useState } from 'react';
import { ChevronRight, ChevronDown, CheckCircle2, Loader2, Terminal } from 'lucide-react';

export function ActivityAccordion({ title, status, logs }) {
  const [isOpen, setIsOpen] = useState(status === 'running');
  const isRunning = status === 'running';

  return (
    <div style={{ margin: '8px 0', border: '1px solid var(--border-subtle)', borderRadius: '8px', overflow: 'hidden' }}>
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{ 
          display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', 
          background: 'var(--bg-surface)', cursor: 'pointer', fontSize: '12px', color: 'var(--text-muted)' 
        }}
      >
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {isRunning ? <Loader2 size={14} className="spin" color="#3b82f6" /> : <CheckCircle2 size={14} color="#22c55e" />}
        <span style={{ fontWeight: 600 }}>{title}</span>
      </div>
      {isOpen && logs && (
        <pre style={{ margin: 0, padding: '12px', background: '#0a0d14', color: '#e2e8f0', fontSize: '11px', overflowX: 'auto', fontFamily: 'var(--font-mono)' }}>
          {logs}
        </pre>
      )}
    </div>
  );
}
