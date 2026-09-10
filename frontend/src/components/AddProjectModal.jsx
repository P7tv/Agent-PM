import React, { useState } from 'react';
import { Plus, X, FolderKanban } from 'lucide-react';

export default function AddProjectModal({ isOpen, onClose, onAddProject }) {
  const [name, setName] = useState('');
  const [workspacePath, setWorkspacePath] = useState('');
  const [autoPilot, setAutoPilot] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !workspacePath.trim()) return;
    setIsSubmitting(true);
    setError('');
    try {
      const projectId = name.toLowerCase().replace(/[^a-z0-9]/g, '-').slice(0, 16);
      await onAddProject({
        project_id: projectId,
        name: name.trim(),
        workspace_path: workspacePath.trim(),
        auto_pilot: autoPilot
      });
      setName('');
      setWorkspacePath('');
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to add project');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="whisper-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '440px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', fontWeight: '600' }}>
            <FolderKanban size={18} color="var(--primary)" />
            <span>Connect Project Workspace</span>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={16} />
          </button>
        </div>

        {error && (
          <div style={{ padding: '8px 12px', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: '6px', fontSize: '12px', marginBottom: '12px' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div>
            <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px', fontWeight: '500' }}>
              Project Name
            </label>
            <input
              type="text"
              className="pm-input"
              style={{ width: '100%', background: 'var(--bg-canvas)', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
              placeholder="e.g. Mobile Banking App"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div>
            <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px', fontWeight: '500' }}>
              Local Directory Path
            </label>
            <input
              type="text"
              className="pm-input"
              style={{ width: '100%', background: 'var(--bg-canvas)', padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
              placeholder="/Users/panpan/projects/my-app"
              value={workspacePath}
              onChange={(e) => setWorkspacePath(e.target.value)}
              required
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
            <input
              type="checkbox"
              id="autoPilotCheckbox"
              checked={autoPilot}
              onChange={(e) => setAutoPilot(e.target.checked)}
              style={{ cursor: 'pointer', accentColor: 'var(--primary)' }}
            />
            <label htmlFor="autoPilotCheckbox" style={{ fontSize: '13px', color: 'var(--text-primary)', cursor: 'pointer' }}>
              Enable Auto-Pilot (Execute without approval gates)
            </label>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '12px' }}>
            <button type="button" className="btn-reject" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="dispatch-btn" disabled={isSubmitting}>
              {isSubmitting ? 'Connecting...' : 'Add Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
