import React, { useState, useEffect } from 'react';
import { X, Check, FileCode2, AlertCircle, Loader2 } from 'lucide-react';

export function DiffPreviewModal({ isOpen, onClose, proposal, projectId, onConfirmApply, applying }) {
  const [originalContent, setOriginalContent] = useState('');
  const [loadingOriginal, setLoadingOriginal] = useState(true);
  const [isNewFile, setIsNewFile] = useState(false);

  useEffect(() => {
    if (!isOpen || !proposal) return;

    let isMounted = true;
    setLoadingOriginal(true);
    setIsNewFile(false);

    const fetchOriginal = async () => {
      try {
        const res = await fetch(`/api/projects/${projectId}/files/content?path=${encodeURIComponent(proposal.filepath)}`);
        if (res.ok) {
          const data = await res.json();
          if (isMounted) setOriginalContent(data.content || '');
        } else {
          if (isMounted) {
            setIsNewFile(true);
            setOriginalContent('');
          }
        }
      } catch (e) {
        if (isMounted) {
          setIsNewFile(true);
          setOriginalContent('');
        }
      } finally {
        if (isMounted) setLoadingOriginal(false);
      }
    };

    fetchOriginal();

    return () => {
      isMounted = false;
    };
  }, [isOpen, proposal, projectId]);

  if (!isOpen || !proposal) return null;

  // Simple and robust line-by-line diff computation
  const computeDiffLines = () => {
    const origLines = originalContent ? originalContent.split('\n') : [];
    const newLines = proposal.content ? proposal.content.split('\n') : [];

    if (isNewFile || origLines.length === 0) {
      return newLines.map((line, idx) => ({
        type: 'added',
        lineNum: idx + 1,
        content: line
      }));
    }

    // Line diff display
    const diff = [];
    const maxLen = Math.max(origLines.length, newLines.length);

    // Simple diff comparison
    for (let i = 0; i < maxLen; i++) {
      const orig = origLines[i];
      const nw = newLines[i];

      if (orig === nw) {
        diff.push({ type: 'unchanged', lineNum: i + 1, content: orig });
      } else {
        if (orig !== undefined) {
          diff.push({ type: 'removed', lineNum: i + 1, content: orig });
        }
        if (nw !== undefined) {
          diff.push({ type: 'added', lineNum: i + 1, content: nw });
        }
      }
    }
    return diff;
  };

  const diffLines = computeDiffLines();

  return (
    <div className="diff-modal-overlay" onClick={onClose}>
      <div className="diff-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="diff-modal-header">
          <div className="diff-modal-title">
            <FileCode2 size={18} color="var(--primary)" />
            <span>Diff Review:</span>
            <span className="diff-filepath-badge">{proposal.filepath}</span>
            {isNewFile && (
              <span style={{ fontSize: '11px', color: '#10b981', fontWeight: 600 }}>
                [New File]
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        <div className="diff-viewer-body">
          {loadingOriginal ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)' }}>
              <Loader2 size={16} className="animate-spin" /> Loading workspace file...
            </div>
          ) : (
            <div>
              {diffLines.map((line, idx) => (
                <div key={idx} className={`diff-line diff-line-${line.type}`}>
                  <span className="diff-line-number">{line.lineNum}</span>
                  <span className="diff-line-prefix">
                    {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
                  </span>
                  <span className="diff-line-content">{line.content}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="diff-modal-footer">
          <button
            onClick={onClose}
            className="secondary-btn"
            style={{ padding: '6px 14px', borderRadius: '6px', cursor: 'pointer' }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirmApply}
            disabled={applying}
            className="primary-btn"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 16px',
              borderRadius: '6px',
              cursor: applying ? 'not-allowed' : 'pointer'
            }}
          >
            {applying ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            <span>Confirm & Apply Change</span>
          </button>
        </div>
      </div>
    </div>
  );
}
