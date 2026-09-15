import React, { useState } from 'react';
import { Copy, Check, FileCode2, Play, Loader2 } from 'lucide-react';
import { useToast } from '../Toast';

export function RichCodeBlock({ language, code, filepath, onApply, applying }) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    toast.info('Code copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ margin: '12px 0', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border-medium)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 12px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '11px' }}>
          {filepath ? <FileCode2 size={12} /> : null}
          <span style={{ fontWeight: 600 }}>{filepath || language || 'text'}</span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {filepath && onApply && (
            <button onClick={() => onApply(filepath, code)} disabled={applying} style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: '#3b82f6', color: '#fff', border: 'none', cursor: applying ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
              {applying ? <Loader2 size={11} className="spin" /> : <Play size={11} />} Apply
            </button>
          )}
          <button 
            onClick={handleCopy} 
            title="Copy code"
            style={{ fontSize: '11px', padding: '2px 6px', background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
            {copied ? <Check size={12} color="#22c55e" /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>
      <pre style={{ margin: 0, padding: '12px', background: '#0a0d14', color: '#e2e8f0', fontSize: '13px', overflowX: 'auto', fontFamily: 'var(--font-mono)' }}>
        <code>{code}</code>
      </pre>
    </div>
  );
}
