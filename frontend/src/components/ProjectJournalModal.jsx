import React, { useState, useEffect } from 'react';
import { 
  BookMarked, 
  X, 
  Plus, 
  Trash2, 
  Brain, 
  ShieldAlert, 
  Code2, 
  FileText, 
  Loader2,
  Sparkles,
  CheckCircle2
} from 'lucide-react';
import { useToast } from './Toast';

const CATEGORIES = [
  { id: 'all', label: 'All Guidelines' },
  { id: 'architecture', label: 'Architecture', icon: Brain },
  { id: 'rules', label: 'Hard Rules', icon: ShieldAlert },
  { id: 'conventions', label: 'Conventions', icon: Code2 },
  { id: 'notes', label: 'Context Notes', icon: FileText }
];

const PRESETS = [
  {
    title: 'Frontend API Communication',
    content: 'All API requests must use relative paths `/api/...` and never hardcode localhost port numbers.',
    category: 'conventions'
  },
  {
    title: 'Database Migrations & Schema',
    content: 'SQLite migrations must always handle OperationalError when adding columns to prevent database locks.',
    category: 'architecture'
  },
  {
    title: 'Testing & Verification',
    content: 'Every newly created endpoint must be backed by an automated pytest test case verifying both 200 and error codes.',
    category: 'rules'
  }
];

export default function ProjectJournalModal({ isOpen, onClose, projectId, projectName }) {
  const toast = useToast();
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filterCategory, setFilterCategory] = useState('all');
  
  // Add memory form state
  const [isAdding, setIsAdding] = useState(false);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('architecture');
  const [submitting, setSubmitting] = useState(false);

  // Escape key handler
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, onClose]);

  const fetchMemories = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/projects/${projectId}/memories`);
      const data = await res.json();
      setMemories(data || []);
    } catch (err) {
      console.error('Failed to fetch project memories:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && projectId) {
      fetchMemories();
    }
  }, [isOpen, projectId]);

  if (!isOpen) return null;

  const handleCreate = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!title.trim() || !content.trim() || submitting) return;
    setSubmitting(true);
    try {
      const res = await fetch(`/api/projects/${projectId}/memories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          content: content.trim(),
          category
        })
      });
      if (res.ok) {
        setTitle('');
        setContent('');
        setIsAdding(false);
        toast.success('Guideline saved to project memory');
        await fetchMemories();
      } else {
        toast.error('Failed to save guideline');
      }
    } catch (err) {
      console.error('Failed to add memory:', err);
      toast.error('Error saving guideline');
    } finally {
      setSubmitting(false);
    }
  };

  const handleApplyPreset = async (preset) => {
    try {
      const res = await fetch(`/api/projects/${projectId}/memories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preset)
      });
      if (res.ok) {
        toast.success(`Preset "${preset.title}" added to memory`);
        await fetchMemories();
      } else {
        toast.error('Failed to add preset');
      }
    } catch (err) {
      console.error('Failed to add preset memory:', err);
      toast.error('Error adding preset');
    }
  };

  const handleDelete = async (memoryId) => {
    try {
      await fetch(`/api/projects/${projectId}/memories/${memoryId}`, { method: 'DELETE' });
      setMemories(prev => prev.filter(m => m.memory_id !== memoryId));
      toast.info('Rule removed from memory');
    } catch (err) {
      console.error('Failed to delete memory:', err);
      toast.error('Failed to delete memory');
    }
  };

  const filteredMemories = memories.filter(m => {
    return filterCategory === 'all' || m.category === filterCategory;
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className="journal-modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--bg-surface-elevated)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px', height: '32px', borderRadius: '8px',
              background: 'rgba(139, 92, 246, 0.15)', color: '#8b5cf6',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <BookMarked size={18} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
                  Agent Memory & Project Journal
                </h3>
                <span style={{
                  fontSize: '11px', padding: '2px 8px', borderRadius: '10px',
                  background: 'var(--bg-canvas)', border: '1px solid var(--border-subtle)',
                  color: 'var(--text-secondary)', fontWeight: '600'
                }}>
                  {memories.length} Injected Rules
                </span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Persistent architectural guidelines automatically provided to all agents in this project.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => setIsAdding(!isAdding)}
              className="view-btn active"
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                fontSize: '12px', padding: '6px 14px', fontWeight: '600',
                background: 'var(--primary)', color: '#fff', border: 'none'
              }}
            >
              <Plus size={14} />
              <span>{isAdding ? 'Close Form' : 'Add Rule'}</span>
            </button>
            <button 
              onClick={onClose}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '6px' }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Collapsible New Rule Form */}
        {isAdding && (
          <form onSubmit={handleCreate} style={{
            padding: '16px 20px',
            background: 'var(--bg-canvas)',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', gap: '10px' }}>
              <input
                type="text"
                placeholder="Rule title (e.g. Always use JWT Bearer tokens...)"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-medium)',
                  background: 'var(--bg-input)',
                  color: 'var(--text-primary)',
                  fontSize: '13px'
                }}
              />
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                style={{
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-medium)',
                  background: 'var(--bg-input)',
                  color: 'var(--text-primary)',
                  fontSize: '12px'
                }}
              >
                <option value="architecture">Architecture</option>
                <option value="rules">Hard Rules</option>
                <option value="conventions">Conventions</option>
                <option value="notes">Context Notes</option>
              </select>
            </div>
            
            <textarea
              placeholder="Detailed rule instruction or architectural constraint..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              required
              rows={3}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-medium)',
                background: 'var(--bg-input)',
                color: 'var(--text-primary)',
                fontSize: '12.5px',
                fontFamily: 'var(--font-mono)',
                resize: 'vertical'
              }}
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                type="button"
                className="view-btn"
                onClick={() => setIsAdding(false)}
                style={{ fontSize: '12px', padding: '5px 12px' }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !title.trim() || !content.trim()}
                className="view-btn active"
                style={{
                  fontSize: '12px', padding: '5px 14px', fontWeight: '600',
                  background: 'var(--primary)', color: '#fff', border: 'none'
                }}
              >
                {submitting ? 'Saving...' : 'Save Rule to Memory'}
              </button>
            </div>
          </form>
        )}

        {/* Filters Toolbar */}
        <div style={{
          padding: '10px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--bg-surface)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {CATEGORIES.map(cat => {
              const IconComp = cat.icon;
              return (
                <button
                  key={cat.id}
                  onClick={() => setFilterCategory(cat.id)}
                  className={`view-btn ${filterCategory === cat.id ? 'active' : ''}`}
                  style={{ fontSize: '11.5px', padding: '3px 10px', height: 'auto', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
                >
                  {IconComp && <IconComp size={12} />}
                  <span>{cat.label}</span>
                </button>
              );
            })}
          </div>

          <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
            Total: {filteredMemories.length} rule{filteredMemories.length === 1 ? '' : 's'}
          </span>
        </div>

        {/* Memories List */}
        <div style={{
          padding: '16px 20px',
          overflowY: 'auto',
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          minHeight: '300px'
        }}>
          {loading ? (
            <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
              <Loader2 size={24} className="spin" style={{ margin: '0 auto 8px auto', color: 'var(--primary)' }} />
              <p style={{ fontSize: '13px' }}>Loading project memories...</p>
            </div>
          ) : filteredMemories.length === 0 ? (
            <div style={{
              padding: '36px 20px', textAlign: 'center',
              background: 'var(--bg-canvas)', borderRadius: '12px',
              border: '1px dashed var(--border-medium)'
            }}>
              <Brain size={36} color="var(--text-muted)" style={{ margin: '0 auto 10px auto', opacity: 0.5 }} />
              <h4 style={{ fontSize: '14px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                No Memory Rules Defined Yet
              </h4>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '400px', margin: '0 auto 16px auto' }}>
                Memories are injected into the prompt of every agent in this project, ensuring they follow your design patterns and don't make the same mistakes twice.
              </p>

              {/* Quick Presets */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '480px', margin: '0 auto' }}>
                <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-secondary)' }}>
                  QUICK PRESETS (CLICK TO ADD):
                </span>
                {PRESETS.map((p, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleApplyPreset(p)}
                    style={{
                      padding: '8px 12px', borderRadius: '8px',
                      background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
                      textAlign: 'left', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '2px'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-primary)' }}>+ {p.title}</span>
                      <span style={{ fontSize: '10px', color: 'var(--primary)', fontWeight: '700' }}>{p.category.toUpperCase()}</span>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{p.content}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            filteredMemories.map(m => {
              const catColors = {
                architecture: '#8b5cf6',
                rules: '#ef4444',
                conventions: '#06b6d4',
                notes: '#64748b'
              };
              const color = catColors[m.category] || '#3b82f6';

              return (
                <div key={m.memory_id} className="memory-item-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{
                        fontSize: '9.5px', fontWeight: '700', textTransform: 'uppercase',
                        padding: '1px 6px', borderRadius: '4px',
                        background: `${color}22`, color: color
                      }}>
                        {m.category}
                      </span>
                      <h4 style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
                        {m.title}
                      </h4>
                    </div>

                    <button
                      onClick={() => handleDelete(m.memory_id)}
                      title="Delete rule from memory"
                      style={{
                        background: 'none', border: 'none', color: 'var(--text-muted)',
                        cursor: 'pointer', padding: '4px'
                      }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>

                  <div style={{
                    fontSize: '12px', color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-mono)', background: 'var(--bg-surface)',
                    padding: '8px 10px', borderRadius: '6px', border: '1px solid var(--border-subtle)',
                    whiteSpace: 'pre-wrap', lineHeight: '1.5'
                  }}>
                    {m.content}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 20px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--bg-surface)'
        }}>
          <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
            🧠 Active in all sprints: TechLead, Frontend, Backend, QA, and Custom agents read these rules before writing code.
          </span>
          <button
            className="view-btn"
            onClick={onClose}
            style={{ fontSize: '12px', padding: '5px 14px' }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
