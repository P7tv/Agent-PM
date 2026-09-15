import React, { useState, useEffect } from 'react';
import { 
  ListTodo, 
  X, 
  Plus, 
  Trash2, 
  Rocket, 
  Tag, 
  Filter, 
  CheckCircle2, 
  Clock, 
  AlertCircle,
  Loader2,
  Sparkles,
  Bug,
  RefreshCw,
  Wrench
} from 'lucide-react';
import { useToast } from './Toast';

const CATEGORIES = [
  { id: 'all', label: 'All Categories' },
  { id: 'feature', label: 'Feature', icon: Sparkles },
  { id: 'bug', label: 'Bug', icon: Bug },
  { id: 'refactor', label: 'Refactor', icon: RefreshCw },
  { id: 'chore', label: 'Chore', icon: Wrench }
];

const CATEGORY_META = {
  feature: { label: 'Feature', icon: Sparkles, color: '#3b82f6' },
  bug: { label: 'Bug', icon: Bug, color: '#ef4444' },
  refactor: { label: 'Refactor', icon: RefreshCw, color: '#8b5cf6' },
  chore: { label: 'Chore', icon: Wrench, color: '#f59e0b' },
};

const PRIORITIES = ['URGENT', 'HIGH', 'NORMAL', 'LOW'];

export default function BacklogBoardModal({ isOpen, onClose, projectId, projectName }) {
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterStatus, setFilterStatus] = useState('ALL');
  
  // New story form state
  const [isAdding, setIsAdding] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newCategory, setNewCategory] = useState('feature');
  const [newPriority, setNewPriority] = useState('NORMAL');
  const [submitting, setSubmitting] = useState(false);
  const [promotingId, setPromotingId] = useState(null);

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

  const fetchBacklog = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/projects/${projectId}/backlog`);
      const data = await res.json();
      setItems(data || []);
    } catch (err) {
      console.error('Failed to fetch backlog:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && projectId) {
      fetchBacklog();
    }
  }, [isOpen, projectId]);

  if (!isOpen) return null;

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newTitle.trim() || submitting) return;
    setSubmitting(true);
    try {
      const res = await fetch(`/api/projects/${projectId}/backlog`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newTitle.trim(),
          description: newDesc.trim(),
          category: newCategory,
          priority: newPriority
        })
      });
      if (res.ok) {
        setNewTitle('');
        setNewDesc('');
        setIsAdding(false);
        toast.success('User story added to backlog');
        await fetchBacklog();
      } else {
        toast.error('Failed to create backlog item');
      }
    } catch (err) {
      console.error('Failed to create backlog item:', err);
      toast.error('Error creating backlog item');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (itemId) => {
    try {
      await fetch(`/api/projects/${projectId}/backlog/${itemId}`, { method: 'DELETE' });
      setItems(prev => prev.filter(i => i.item_id !== itemId));
      toast.info('Story removed from backlog');
    } catch (err) {
      console.error('Failed to delete backlog item:', err);
      toast.error('Failed to delete backlog item');
    }
  };

  const handlePromoteToSprint = async (itemId) => {
    if (promotingId) return;
    setPromotingId(itemId);
    try {
      const res = await fetch(`/api/projects/${projectId}/backlog/${itemId}/promote`, {
        method: 'POST'
      });
      if (res.ok) {
        setItems(prev => prev.map(i => i.item_id === itemId ? { ...i, status: 'QUEUED' } : i));
        toast.success('Story promoted to active sprint queue!');
      } else {
        toast.error('Failed to promote story');
      }
    } catch (err) {
      console.error('Failed to promote backlog item:', err);
      toast.error('Error promoting story');
    } finally {
      setPromotingId(null);
    }
  };

  const filteredItems = items.filter(item => {
    const matchesCat = filterCategory === 'all' || item.category === filterCategory;
    const matchesStat = filterStatus === 'ALL' || item.status === filterStatus;
    return matchesCat && matchesStat;
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className="backlog-modal-content"
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
              background: 'var(--primary-subtle)', color: 'var(--primary)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <ListTodo size={18} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
                  Product Backlog & Sprint Planning
                </h3>
                <span style={{
                  fontSize: '11px', padding: '2px 8px', borderRadius: '10px',
                  background: 'var(--bg-canvas)', border: '1px solid var(--border-subtle)',
                  color: 'var(--text-secondary)', fontWeight: '600'
                }}>
                  {items.length} Stories
                </span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Project: <strong style={{ color: 'var(--text-secondary)' }}>{projectName || projectId}</strong>
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
              <span>{isAdding ? 'Close Form' : 'New Story'}</span>
            </button>
            <button 
              onClick={onClose}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '6px' }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Collapsible New Story Form */}
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
                placeholder="User story title (e.g. As a user, I want OAuth Google login...)"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
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
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                style={{
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-medium)',
                  background: 'var(--bg-input)',
                  color: 'var(--text-primary)',
                  fontSize: '12px'
                }}
              >
                <option value="feature">Feature</option>
                <option value="bug">Bug</option>
                <option value="refactor">Refactor</option>
                <option value="chore">Chore</option>
              </select>
              <select
                value={newPriority}
                onChange={(e) => setNewPriority(e.target.value)}
                style={{
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-medium)',
                  background: 'var(--bg-input)',
                  color: 'var(--text-primary)',
                  fontSize: '12px'
                }}
              >
                <option value="URGENT">Urgent</option>
                <option value="HIGH">High</option>
                <option value="NORMAL">Normal</option>
                <option value="LOW">Low</option>
              </select>
            </div>
            
            <textarea
              placeholder="Acceptance criteria or implementation details..."
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              rows={2}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-medium)',
                background: 'var(--bg-input)',
                color: 'var(--text-primary)',
                fontSize: '12.5px',
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
                disabled={submitting || !newTitle.trim()}
                className="view-btn active"
                style={{
                  fontSize: '12px', padding: '5px 14px', fontWeight: '600',
                  background: 'var(--primary)', color: '#fff', border: 'none'
                }}
              >
                {submitting ? 'Saving...' : 'Add to Backlog'}
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
          flexWrap: 'wrap',
          gap: '10px',
          background: 'var(--bg-surface)'
        }}>
          {/* Category Filter Pills */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflowX: 'auto' }}>
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

          {/* Status Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Status:</span>
            {['ALL', 'OPEN', 'QUEUED', 'DONE'].map(st => (
              <button
                key={st}
                onClick={() => setFilterStatus(st)}
                className={`view-btn ${filterStatus === st ? 'active' : ''}`}
                style={{ fontSize: '10.5px', padding: '2px 8px', height: 'auto' }}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        {/* Stories List Body */}
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
              <p style={{ fontSize: '13px' }}>Loading product backlog...</p>
            </div>
          ) : filteredItems.length === 0 ? (
            <div style={{
              padding: '48px 20px', textAlign: 'center',
              background: 'var(--bg-canvas)', borderRadius: '12px',
              border: '1px dashed var(--border-medium)'
            }}>
              <ListTodo size={36} color="var(--text-muted)" style={{ margin: '0 auto 10px auto', opacity: 0.5 }} />
              <h4 style={{ fontSize: '14px', color: 'var(--text-primary)', marginBottom: '4px' }}>
                No User Stories Found
              </h4>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '340px', margin: '0 auto 14px auto' }}>
                {items.length === 0 
                  ? 'Plan upcoming sprints by defining user stories and tasks in your backlog.'
                  : 'No stories match your current filters.'}
              </p>
              {items.length === 0 && (
                <button
                  onClick={() => setIsAdding(true)}
                  className="view-btn active"
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                    fontSize: '12px', padding: '6px 14px', background: 'var(--primary)', color: '#fff', border: 'none'
                  }}
                >
                  <Plus size={13} />
                  <span>Create First User Story</span>
                </button>
              )}
            </div>
          ) : (
            filteredItems.map(item => {
              const priorityClass = `priority-${(item.priority || 'normal').toLowerCase()}`;
              const isPromoting = promotingId === item.item_id;

              return (
                <div key={item.item_id} className="backlog-item-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span className={`priority-badge ${priorityClass}`}>
                          {item.priority}
                        </span>
                        {(() => {
                          const catMeta = CATEGORY_META[item.category] || { label: item.category, icon: Tag, color: 'var(--text-muted)' };
                          const CatIcon = catMeta.icon;
                          return (
                            <span style={{
                              fontSize: '11px', fontWeight: '600', color: catMeta.color,
                              display: 'inline-flex', alignItems: 'center', gap: '4px'
                            }}>
                              <CatIcon size={12} />
                              <span>{catMeta.label}</span>
                            </span>
                          );
                        })()}
                        <span style={{
                          fontSize: '10.5px', padding: '1px 6px', borderRadius: '4px',
                          background: item.status === 'DONE' ? 'var(--success-subtle)' : item.status === 'QUEUED' ? 'rgba(245, 158, 11, 0.15)' : 'var(--bg-surface-elevated)',
                          color: item.status === 'DONE' ? 'var(--success-text)' : item.status === 'QUEUED' ? '#d97706' : 'var(--text-secondary)',
                          fontWeight: '600'
                        }}>
                          {item.status}
                        </span>
                      </div>

                      <h4 style={{ fontSize: '13.5px', fontWeight: '600', color: 'var(--text-primary)', margin: 0 }}>
                        {item.title}
                      </h4>

                      {item.description && (
                        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '2px 0 0 0', lineHeight: '1.4' }}>
                          {item.description}
                        </p>
                      )}
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                      {item.status === 'OPEN' && (
                        <button
                          onClick={() => handlePromoteToSprint(item.item_id)}
                          disabled={isPromoting}
                          title="Queue as active sprint directive"
                          style={{
                            display: 'flex', alignItems: 'center', gap: '5px',
                            padding: '5px 10px', borderRadius: '6px',
                            background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                            color: '#fff', border: 'none', fontSize: '11px', fontWeight: '600',
                            cursor: isPromoting ? 'wait' : 'pointer'
                          }}
                        >
                          {isPromoting ? <Loader2 size={12} className="spin" /> : <Rocket size={12} />}
                          <span>Launch Sprint</span>
                        </button>
                      )}

                      {item.status === 'QUEUED' && (
                        <span style={{ fontSize: '11px', color: 'var(--warning-text)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <Clock size={12} />
                          <span>In Queue</span>
                        </span>
                      )}

                      <button
                        onClick={() => handleDelete(item.item_id)}
                        title="Delete story"
                        style={{
                          background: 'none', border: 'none', color: 'var(--text-muted)',
                          cursor: 'pointer', padding: '4px', borderRadius: '4px'
                        }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
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
            💡 Clicking "Launch Sprint" enqueues the user story directly to autonomous agents.
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
