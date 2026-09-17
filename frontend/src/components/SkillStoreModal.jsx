import React, { useState, useEffect } from 'react';
import {
  X,
  Search,
  Download,
  Sparkles,
  Check,
  AlertCircle,
  ExternalLink,
  Layers,
  Cpu,
  RefreshCw,
  BookOpen,
  ArrowRight,
  ShieldCheck
} from 'lucide-react';
import { useToast } from './Toast';

export default function SkillStoreModal({
  isOpen,
  onClose,
  projectId,
  projectPath,
  agents = [],
  onSkillAssigned
}) {
  const toast = useToast();

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);
  const [activeTab, setActiveTab] = useState('installed'); // 'installed' | 'download'
  const [skills, setSkills] = useState([]);
  const [loadingSkills, setLoadingSkills] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [tierFilter, setTierFilter] = useState('all'); // 'all' | 'agy' | 'stock' | 'project'

  // Download form state
  const [downloadUrl, setDownloadUrl] = useState('');
  const [customName, setCustomName] = useState('');
  const [downloadTarget, setDownloadTarget] = useState('project'); // 'project' | 'stock'
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadStatus, setDownloadStatus] = useState(null); // { type: 'success' | 'error', message: '' }

  // Assigning state
  const [assigningSkillName, setAssigningSkillName] = useState(null);
  const [assignSuccessRole, setAssignSuccessRole] = useState(null);
  const [enablingAuto, setEnablingAuto] = useState(false);
  const enableTeamAuto = async () => {
    if (!projectId || enablingAuto) return;
    setEnablingAuto(true);
    const results = await Promise.allSettled(agents.map(async agent => {
      const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/agents/${encodeURIComponent(agent.role)}/skills/set-mode`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'AUTO' })
      });
      if (!response.ok) throw new Error(`เปลี่ยนโหมด ${agent.role} ไม่สำเร็จ`);
    }));
    const failed = results.filter(result => result.status === 'rejected').length;
    if (onSkillAssigned) onSkillAssigned();
    if (failed) toast.error(`เปลี่ยนเป็น Auto ไม่สำเร็จ ${failed} agents กรุณาลองใหม่`);
    else toast.success('เปิด Auto ทั้งทีมแล้ว ระบบเลือก skill ตามงานพร้อม skill ที่ปักไว้');
    setEnablingAuto(false);
  };

  useEffect(() => {
    if (isOpen) {
      fetchAvailableSkills();
      setDownloadStatus(null);
      setAssignSuccessRole(null);
    }
  }, [isOpen, projectId]);

  const fetchAvailableSkills = async () => {
    setLoadingSkills(true);
    try {
      const res = await fetch(projectId ? `/api/skills?project_id=${encodeURIComponent(projectId)}` : '/api/skills');
      if (res.ok) {
        const data = await res.json();
        setSkills(data);
      }
    } catch (err) {
      console.error('Failed to load skills:', err);
    } finally {
      setLoadingSkills(false);
    }
  };

  const handleAssignSkill = async (skillName, role) => {
    setAssigningSkillName(skillName);
    try {
      const res = await fetch(`/api/projects/${projectId}/agents/${role}/assign-skill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_name: skillName })
      });
      if (res.ok) {
        const data = await res.json();
        setAssignSuccessRole({ role, skillName });
        toast.success(`Assigned ${skillName} to ${role}`);
        setTimeout(() => setAssignSuccessRole(null), 3000);
        if (onSkillAssigned) onSkillAssigned(role, skillName);
      } else {
        const err = await res.json();
        toast.error(`Failed to assign skill: ${err.detail || 'Unknown error'}`);
      }
    } catch (err) {
      toast.error(`Network error: ${err.message}`);
    } finally {
      setAssigningSkillName(null);
    }
  };

  const handleDownloadSkill = async (e) => {
    e.preventDefault();
    if (!downloadUrl.trim()) return;

    setIsDownloading(true);
    setDownloadStatus(null);

    try {
      const res = await fetch('/api/skills/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: downloadUrl.trim(),
          skill_name: customName.trim() || undefined,
          target: downloadTarget,
          project_id: projectId
        })
      });

      const data = await res.json();
      if (res.ok) {
        setDownloadStatus({
          type: 'success',
          message: `Skill '${data.skill?.name || customName}' successfully installed (${data.skill?.tier || downloadTarget})!`
        });
        setDownloadUrl('');
        setCustomName('');
        // Refresh catalog and switch to installed view
        await fetchAvailableSkills();
      } else {
        setDownloadStatus({
          type: 'error',
          message: data.detail || 'Failed to download skill.'
        });
      }
    } catch (err) {
      setDownloadStatus({
        type: 'error',
        message: `Network error: ${err.message}`
      });
    } finally {
      setIsDownloading(false);
    }
  };

  if (!isOpen) return null;

  // Filter skills
  const filteredSkills = skills.filter((s) => {
    const matchesSearch =
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.title && s.title.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (s.description && s.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (s.allowed_tools && s.allowed_tools.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase())));

    if (!matchesSearch) return false;
    if (tierFilter === 'all') return true;
    return (s.tier || 'stock').toLowerCase() === tierFilter;
  });

  const agyCount = skills.filter((s) => s.tier === 'agy').length;
  const stockCount = skills.filter((s) => (s.tier || 'stock') === 'stock').length;
  const projCount = skills.filter((s) => s.tier === 'project').length;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.72)',
        backdropFilter: 'blur(5px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '18px'
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--bg-card, #1e293b)',
          border: '1px solid var(--border-medium, #334155)',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '860px',
          maxHeight: '88vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: '1px solid var(--border-medium, #334155)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--bg-surface, #0f172a)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #10b981 0%, #3b82f6 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff'
              }}
            >
              <Sparkles size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '700', color: 'var(--text-primary, #f8fafc)' }}>
                Skill Hub & AGY Playbook Store
              </h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: 'var(--text-muted, #94a3b8)' }}>
                Auto เลือก skill ตามงานจากคลังที่ติดตั้ง ไม่จำเป็นต้อง Equip ทุกตัว
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted, #94a3b8)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background 0.15s ease'
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            display: 'flex',
            gap: '8px',
            padding: '12px 24px 0 24px',
            borderBottom: '1px solid var(--border-subtle, #334155)',
            background: 'var(--bg-surface, #0f172a)'
          }}
        >
          <button
            onClick={() => setActiveTab('installed')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              border: 'none',
              background: 'transparent',
              borderBottom: activeTab === 'installed' ? '2px solid var(--primary, #3b82f6)' : '2px solid transparent',
              color: activeTab === 'installed' ? 'var(--primary, #3b82f6)' : 'var(--text-muted, #94a3b8)',
              fontWeight: activeTab === 'installed' ? '700' : '500',
              fontSize: '13px',
              cursor: 'pointer'
            }}
          >
            <BookOpen size={16} />
            Browse Skills ({skills.length})
          </button>
          {projectId && agents.length > 0 && <button onClick={enableTeamAuto} disabled={enablingAuto}
            style={{ color: 'var(--primary-text)', background: 'var(--primary-subtle)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '8px 12px', cursor: 'pointer' }}>
            {enablingAuto ? 'กำลังเปิด Auto…' : 'เปิด Auto ทั้งทีม'}
          </button>}
          <button
            onClick={() => setActiveTab('download')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              border: 'none',
              background: 'transparent',
              borderBottom: activeTab === 'download' ? '2px solid var(--primary, #3b82f6)' : '2px solid transparent',
              color: activeTab === 'download' ? 'var(--primary, #3b82f6)' : 'var(--text-muted, #94a3b8)',
              fontWeight: activeTab === 'download' ? '700' : '500',
              fontSize: '13px',
              cursor: 'pointer'
            }}
          >
            <Download size={16} />
            Download from URL / GitHub
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '18px 24px', overflowY: 'auto', flex: 1 }}>
          {activeTab === 'installed' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Filter & Search Bar */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ position: 'relative', flex: '1 1 260px' }}>
                  <Search
                    size={15}
                    style={{
                      position: 'absolute',
                      left: '12px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      color: 'var(--text-muted, #94a3b8)'
                    }}
                  />
                  <input
                    type="text"
                    placeholder="Search by role, title, or keywords..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 12px 8px 36px',
                      background: 'var(--bg-canvas, #090d16)',
                      border: '1px solid var(--border-medium, #334155)',
                      borderRadius: '8px',
                      color: 'var(--text-primary, #f8fafc)',
                      fontSize: '12.5px',
                      outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                {/* Tier Filter Pills */}
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button
                    onClick={() => setTierFilter('all')}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: '600',
                      border: tierFilter === 'all' ? '1px solid var(--primary, #3b82f6)' : '1px solid var(--border-subtle, #334155)',
                      background: tierFilter === 'all' ? 'var(--primary, #3b82f6)' : 'var(--bg-surface, #1e293b)',
                      color: tierFilter === 'all' ? '#ffffff' : 'var(--text-muted, #94a3b8)',
                      cursor: 'pointer'
                    }}
                  >
                    All ({skills.length})
                  </button>
                  <button
                    onClick={() => setTierFilter('agy')}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: '600',
                      border: tierFilter === 'agy' ? '1px solid #10b981' : '1px solid var(--border-subtle, #334155)',
                      background: tierFilter === 'agy' ? '#10b981' : 'var(--bg-surface, #1e293b)',
                      color: tierFilter === 'agy' ? '#ffffff' : '#34d399',
                      cursor: 'pointer'
                    }}
                  >
                    🟢 AGY ({agyCount})
                  </button>
                  <button
                    onClick={() => setTierFilter('stock')}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      fontWeight: '600',
                      border: tierFilter === 'stock' ? '1px solid #3b82f6' : '1px solid var(--border-subtle, #334155)',
                      background: tierFilter === 'stock' ? '#3b82f6' : 'var(--bg-surface, #1e293b)',
                      color: tierFilter === 'stock' ? '#ffffff' : '#60a5fa',
                      cursor: 'pointer'
                    }}
                  >
                    🔵 Stock ({stockCount})
                  </button>
                  {projCount > 0 && (
                    <button
                      onClick={() => setTierFilter('project')}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '6px',
                        fontSize: '11px',
                        fontWeight: '600',
                        border: tierFilter === 'project' ? '1px solid #f59e0b' : '1px solid var(--border-subtle, #334155)',
                        background: tierFilter === 'project' ? '#f59e0b' : 'var(--bg-surface, #1e293b)',
                        color: tierFilter === 'project' ? '#ffffff' : '#fbbf24',
                        cursor: 'pointer'
                      }}
                    >
                      🟣 Project ({projCount})
                    </button>
                  )}
                </div>
              </div>

              {/* Assignment Success Alert */}
              {assignSuccessRole && (
                <div
                  style={{
                    padding: '8px 14px',
                    borderRadius: '8px',
                    background: 'rgba(16, 185, 129, 0.15)',
                    border: '1px solid #10b981',
                    color: '#34d399',
                    fontSize: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  <Check size={16} />
                  <span>
                    Successfully equipped <strong>{assignSuccessRole.skillName}</strong> to specialist{' '}
                    <strong>{assignSuccessRole.role}</strong>!
                  </span>
                </div>
              )}

              {/* Skills Grid */}
              {loadingSkills ? (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted, #94a3b8)' }}>
                  <RefreshCw size={24} className="spin" style={{ margin: '0 auto 8px auto' }} />
                  <p style={{ fontSize: '13px' }}>Discovering installed playbooks...</p>
                </div>
              ) : filteredSkills.length === 0 ? (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '36px',
                    border: '1px dashed var(--border-medium, #334155)',
                    borderRadius: '12px',
                    color: 'var(--text-muted, #94a3b8)'
                  }}
                >
                  <BookOpen size={28} style={{ margin: '0 auto 8px auto', opacity: 0.5 }} />
                  <p style={{ fontSize: '13px', margin: 0 }}>No skills matched your search criteria.</p>
                </div>
              ) : (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
                    gap: '12px'
                  }}
                >
                  {filteredSkills.map((s) => {
                    const tier = (s.tier || 'stock').toLowerCase();
                    const tierBadgeStyle =
                      tier === 'agy'
                        ? { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981', text: '#34d399', label: 'AGY' }
                        : tier === 'project'
                        ? { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b', text: '#fbbf24', label: 'PROJECT' }
                        : { bg: 'rgba(59, 130, 246, 0.15)', border: '#3b82f6', text: '#60a5fa', label: 'STOCK' };

                    return (
                      <div
                        key={s.name}
                        style={{
                          background: 'var(--bg-surface, #0f172a)',
                          border: '1px solid var(--border-medium, #334155)',
                          borderRadius: '12px',
                          padding: '14px',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          gap: '10px'
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                            <div>
                              <h4 style={{ margin: 0, fontSize: '13.5px', fontWeight: '700', color: 'var(--text-primary, #f8fafc)' }}>
                                {s.title || s.name}
                              </h4>
                              <span style={{ fontSize: '10.5px', color: 'var(--text-muted, #94a3b8)', fontFamily: 'monospace' }}>
                                📖 {s.name}
                              </span>
                            </div>
                            <span
                              style={{
                                fontSize: '9px',
                                fontWeight: '700',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                background: tierBadgeStyle.bg,
                                border: `1px solid ${tierBadgeStyle.border}`,
                                color: tierBadgeStyle.text
                              }}
                            >
                              {tierBadgeStyle.label}
                            </span>
                          </div>

                          <p
                            style={{
                              margin: '8px 0 0 0',
                              fontSize: '11.5px',
                              lineHeight: '1.45',
                              color: 'var(--text-muted, #94a3b8)',
                              display: '-webkit-box',
                              WebkitLineClamp: 3,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden'
                            }}
                          >
                            {s.description || 'Specialized operational instructions and guidelines.'}
                          </p>
                        </div>

                        {/* Allowed Tools & Assign Action */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid var(--border-subtle, #334155)' }}>
                          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', maxWidth: '180px' }}>
                            {(s.allowed_tools || []).slice(0, 3).map((tool) => (
                              <span
                                key={tool}
                                style={{
                                  fontSize: '9.5px',
                                  padding: '1px 5px',
                                  borderRadius: '4px',
                                  background: 'var(--bg-canvas, #090d16)',
                                  color: 'var(--text-muted, #94a3b8)',
                                  border: '1px solid var(--border-subtle, #334155)'
                                }}
                              >
                                {tool}
                              </span>
                            ))}
                            {(s.allowed_tools || []).length > 3 && (
                              <span style={{ fontSize: '9.5px', color: 'var(--text-muted, #94a3b8)' }}>
                                +{(s.allowed_tools || []).length - 3}
                              </span>
                            )}
                          </div>

                          {/* Assign dropdown */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <select
                              disabled={assigningSkillName === s.name}
                              onChange={(e) => {
                                if (e.target.value) {
                                  handleAssignSkill(s.name, e.target.value);
                                  e.target.value = '';
                                }
                              }}
                              defaultValue=""
                              style={{
                                background: 'var(--bg-canvas, #090d16)',
                                color: 'var(--text-primary, #f8fafc)',
                                border: '1px solid var(--border-medium, #334155)',
                                borderRadius: '6px',
                                padding: '4px 8px',
                                fontSize: '11px',
                                fontWeight: '600',
                                cursor: 'pointer',
                                outline: 'none'
                              }}
                            >
                              <option value="" disabled>
                                + Equip to Agent
                              </option>
                              {agents.map((ag) => (
                                <option key={ag.role} value={ag.role}>
                                  {ag.role}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            /* Tab 2: Download from URL / GitHub */
            <form onSubmit={handleDownloadSkill} style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '580px', margin: '0 auto' }}>
              <div
                style={{
                  background: 'rgba(59, 130, 246, 0.08)',
                  border: '1px solid rgba(59, 130, 246, 0.25)',
                  borderRadius: '10px',
                  padding: '12px 16px',
                  display: 'flex',
                  gap: '10px',
                  alignItems: 'flex-start'
                }}
              >
                <ShieldCheck size={20} style={{ color: '#3b82f6', flexShrink: 0, marginTop: '2px' }} />
                <div style={{ fontSize: '12px', lineHeight: '1.5', color: 'var(--text-primary, #f8fafc)' }}>
                  <strong>Verified Downloader Guardrails:</strong> Supports raw URLs and GitHub blob links (e.g.{' '}
                  <code>https://github.com/.../blob/.../SKILL.md</code>). All inputs are sanitized, bounded to &lt;512 KB, and validated for YAML frontmatter.
                </div>
              </div>

              {downloadStatus && (
                <div
                  style={{
                    padding: '10px 14px',
                    borderRadius: '8px',
                    fontSize: '12.5px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    background: downloadStatus.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                    border: `1px solid ${downloadStatus.type === 'success' ? '#10b981' : '#ef4444'}`,
                    color: downloadStatus.type === 'success' ? '#34d399' : '#f87171'
                  }}
                >
                  {downloadStatus.type === 'success' ? <Check size={18} /> : <AlertCircle size={18} />}
                  <span>{downloadStatus.message}</span>
                </div>
              )}

              {/* URL Input */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12.5px', fontWeight: '600', color: 'var(--text-primary, #f8fafc)' }}>
                  GitHub or Markdown URL *
                </label>
                <input
                  type="url"
                  required
                  placeholder="https://raw.githubusercontent.com/user/repo/main/skills/custom-skill/SKILL.md"
                  value={downloadUrl}
                  onChange={(e) => setDownloadUrl(e.target.value)}
                  style={{
                    padding: '10px 12px',
                    background: 'var(--bg-canvas, #090d16)',
                    border: '1px solid var(--border-medium, #334155)',
                    borderRadius: '8px',
                    color: 'var(--text-primary, #f8fafc)',
                    fontSize: '12.5px',
                    outline: 'none'
                  }}
                />
              </div>

              {/* Custom Name */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12.5px', fontWeight: '600', color: 'var(--text-primary, #f8fafc)' }}>
                  Custom Skill Identifier (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. fastapi-pro, flutter-expert"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  style={{
                    padding: '10px 12px',
                    background: 'var(--bg-canvas, #090d16)',
                    border: '1px solid var(--border-medium, #334155)',
                    borderRadius: '8px',
                    color: 'var(--text-primary, #f8fafc)',
                    fontSize: '12.5px',
                    outline: 'none'
                  }}
                />
                <span style={{ fontSize: '11px', color: 'var(--text-muted, #94a3b8)' }}>
                  Leave blank to auto-detect from the markdown frontmatter or URL path.
                </span>
              </div>

              {/* Target Location */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <label style={{ fontSize: '12.5px', fontWeight: '600', color: 'var(--text-primary, #f8fafc)' }}>
                  Installation Scope
                </label>
                <div style={{ display: 'flex', gap: '14px' }}>
                  <label
                    style={{
                      flex: 1,
                      padding: '10px 14px',
                      borderRadius: '8px',
                      background: downloadTarget === 'project' ? 'rgba(59, 130, 246, 0.12)' : 'var(--bg-surface, #0f172a)',
                      border: downloadTarget === 'project' ? '1px solid #3b82f6' : '1px solid var(--border-medium, #334155)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <input
                      type="radio"
                      name="target"
                      value="project"
                      checked={downloadTarget === 'project'}
                      onChange={() => setDownloadTarget('project')}
                    />
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-primary, #f8fafc)' }}>
                        Current Project (.agents/skills/)
                      </div>
                      <div style={{ fontSize: '10.5px', color: 'var(--text-muted, #94a3b8)' }}>
                        Saved inside workspace, portable via Git
                      </div>
                    </div>
                  </label>

                  <label
                    style={{
                      flex: 1,
                      padding: '10px 14px',
                      borderRadius: '8px',
                      background: downloadTarget === 'stock' ? 'rgba(59, 130, 246, 0.12)' : 'var(--bg-surface, #0f172a)',
                      border: downloadTarget === 'stock' ? '1px solid #3b82f6' : '1px solid var(--border-medium, #334155)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <input
                      type="radio"
                      name="target"
                      value="stock"
                      checked={downloadTarget === 'stock'}
                      onChange={() => setDownloadTarget('stock')}
                    />
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-primary, #f8fafc)' }}>
                        Global Stock (backend/skills/)
                      </div>
                      <div style={{ fontSize: '10.5px', color: 'var(--text-muted, #94a3b8)' }}>
                        Available across all projects on this machine
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isDownloading || !downloadUrl.trim()}
                style={{
                  marginTop: '8px',
                  padding: '11px',
                  borderRadius: '8px',
                  border: 'none',
                  background: 'var(--primary, #3b82f6)',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: '700',
                  cursor: isDownloading || !downloadUrl.trim() ? 'not-allowed' : 'pointer',
                  opacity: isDownloading || !downloadUrl.trim() ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)'
                }}
              >
                {isDownloading ? (
                  <>
                    <RefreshCw size={16} className="spin" />
                    Fetching & Sanitizing Skill...
                  </>
                ) : (
                  <>
                    <Download size={16} />
                    Download & Install Playbook
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
