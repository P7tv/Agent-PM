import React from 'react';
import { AlertTriangle, Trash2, X } from 'lucide-react';

export default function DeleteProjectModal({ isOpen, project, onConfirm, onCancel }) {
  if (!isOpen || !project) return null;

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div 
        className="gate-modal" 
        style={{ borderColor: 'rgba(239, 68, 68, 0.4)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
          <div className="gate-title" style={{ color: 'var(--accent-coral)' }}>
            <AlertTriangle size={20} />
            <span>CONFIRM PROJECT DELETION</span>
          </div>
          <button 
            onClick={onCancel}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '4px' }}
          >
            <X size={18} />
          </button>
        </div>

        <p className="gate-body" style={{ marginBottom: '16px' }}>
          Are you sure you want to disconnect and remove project <strong>"{project.name}"</strong>?
        </p>

        {project.workspace_path && (
          <div style={{
            background: 'var(--bg-canvas)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 12px',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-secondary)',
            marginBottom: '20px',
            wordBreak: 'break-all'
          }}>
            📁 {project.workspace_path}
          </div>
        )}

        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '20px' }}>
          ℹ️ This will remove the project from the PM Command Center dashboard. Your local source code files on disk will remain untouched.
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
          <button 
            className="view-btn" 
            onClick={onCancel}
            style={{ padding: '8px 16px' }}
          >
            Cancel
          </button>
          <button 
            className="btn-reject" 
            onClick={() => onConfirm(project.project_id)}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '6px', 
              padding: '8px 16px',
              fontWeight: '600' 
            }}
          >
            <Trash2 size={15} />
            <span>Yes, Delete Project</span>
          </button>
        </div>
      </div>
    </div>
  );
}
