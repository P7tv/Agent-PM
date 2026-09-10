import React, { useState, useEffect } from 'react';
import { 
  ArrowLeft, 
  Terminal, 
  Shield, 
  CheckCircle, 
  Code2, 
  Users, 
  MessageSquare, 
  GitBranch, 
  Activity, 
  RefreshCw, 
  FileCode2, 
  GitCommit, 
  Check, 
  FolderPlus,
  Loader2,
  BookOpen,
  Edit3,
  Save,
  Sparkles
} from 'lucide-react';
import SkillStoreModal from './SkillStoreModal';

const TABS = [
  { id: 'war-room', label: 'War Room', icon: Activity },
  { id: 'terminal', label: 'Terminal & Tests', icon: Terminal },
  { id: 'git-diff', label: 'File Changes', icon: GitBranch },
  { id: 'skills', label: 'Playbooks & Skills', icon: BookOpen },
  { id: 'whisper', label: '1-on-1 Whisper', icon: MessageSquare },
];

export default function FocusRoomView({ project, agents, tasks, liveStream, onBack, onAgentClick, onSendWhisper }) {
  const [activeTab, setActiveTab] = useState('war-room');
  const [whisperRole, setWhisperRole] = useState(agents[0]?.role || 'Architect');
  const [whisperText, setWhisperText] = useState('');

  // Git live data state
  const [gitData, setGitData] = useState(null);
  const [gitLoading, setGitLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState('ALL');

  // Skills & Playbooks state
  const [projectSkills, setProjectSkills] = useState([]);
  const [selectedSkillRole, setSelectedSkillRole] = useState(agents[0]?.role || 'TechLead');
  const [skillDetail, setSkillDetail] = useState(null);
  const [skillLoading, setSkillLoading] = useState(false);
  const [isEditingSkill, setIsEditingSkill] = useState(false);
  const [skillEditText, setSkillEditText] = useState('');
  const [savingSkill, setSavingSkill] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState(null);
  const [isSkillStoreOpen, setIsSkillStoreOpen] = useState(false);

  const fetchProjectSkills = async () => {
    if (!project?.project_id) return;
    try {
      const res = await fetch(`/api/projects/${project.project_id}/skills`);
      const data = await res.json();
      setProjectSkills(data);
      if (data.length > 0 && !data.some(s => s.role === selectedSkillRole)) {
        setSelectedSkillRole(data[0].role);
      }
    } catch (err) {
      console.error('Failed to fetch project skills:', err);
    }
  };

  const fetchSkillDetail = async (role) => {
    if (!project?.project_id || !role) return;
    setSkillLoading(true);
    setIsEditingSkill(false);
    setSaveSuccessMsg(null);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/skills/${role}`);
      const data = await res.json();
      setSkillDetail(data);
      setSkillEditText(data.raw_content || data.instructions || '');
    } catch (err) {
      console.error('Failed to fetch skill detail:', err);
    } finally {
      setSkillLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'skills') {
      fetchProjectSkills();
    }
  }, [activeTab, project?.project_id]);

  useEffect(() => {
    if (activeTab === 'skills' && selectedSkillRole) {
      fetchSkillDetail(selectedSkillRole);
    }
  }, [activeTab, selectedSkillRole]);

  const handleSaveSkill = async () => {
    if (!project?.project_id || !selectedSkillRole || savingSkill) return;
    setSavingSkill(true);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/skills/${selectedSkillRole}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: skillEditText })
      });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        setSaveSuccessMsg('Playbook saved & applied to agent! Changes take effect immediately.');
        setIsEditingSkill(false);
        fetchProjectSkills();
        fetchSkillDetail(selectedSkillRole);
      }
    } catch (err) {
      console.error('Failed to save skill:', err);
    } finally {
      setSavingSkill(false);
    }
  };

  const fetchGitStatus = async () => {
    if (!project?.project_id) return;
    setGitLoading(true);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/git`);
      const data = await res.json();
      setGitData(data);
    } catch (err) {
      console.error('Failed to fetch git status:', err);
    } finally {
      setGitLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'git-diff') {
      fetchGitStatus();
    }
  }, [activeTab, project?.project_id]);

  if (!project) return null;

  const handleInitGit = async () => {
    setGitLoading(true);
    try {
      await fetch(`/api/projects/${project.project_id}/git/init`, { method: 'POST' });
      await fetchGitStatus();
    } catch (err) {
      console.error('Failed to init git:', err);
      setGitLoading(false);
    }
  };

  const handleWhisperSubmit = (e) => {
    e.preventDefault();
    if (!whisperText.trim() || !onSendWhisper) return;
    onSendWhisper(project.project_id, whisperRole, whisperText);
    setWhisperText('');
  };

  // Filter stream by type for tabs
  const thoughtStream = liveStream.filter(l => l.thought || l.status);
  const toolStream = liveStream.filter(l => l.tool);

  // Filter diff by selected file
  const renderDiffContent = () => {
    if (!gitData?.diff) {
      return (
        <div style={{ color: 'var(--text-muted)', fontStyle: 'italic', padding: '16px' }}>
          No modified code changes in working tree.
        </div>
      );
    }

    let diffText = gitData.diff;
    if (selectedFile !== 'ALL') {
      // Extract diff section for selected file
      const parts = diffText.split('diff --git ');
      const matchingPart = parts.find(p => p.includes(`b/${selectedFile}`) || p.includes(selectedFile));
      if (matchingPart) {
        diffText = 'diff --git ' + matchingPart;
      }
    }

    const lines = diffText.split('\n');
    return (
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', lineHeight: '1.6' }}>
        {lines.map((line, idx) => {
          let style = { padding: '1px 8px', display: 'block', color: 'var(--text-secondary)' };

          if (line.startsWith('+') && !line.startsWith('+++')) {
            style.color = 'var(--success-text)';
            style.background = 'rgba(34, 197, 94, 0.12)';
          } else if (line.startsWith('-') && !line.startsWith('---')) {
            style.color = 'var(--accent-coral)';
            style.background = 'rgba(239, 68, 68, 0.12)';
          } else if (line.startsWith('@@')) {
            style.color = '#38bdf8';
            style.background = 'rgba(56, 189, 248, 0.1)';
            style.fontWeight = '600';
          } else if (line.startsWith('diff --git')) {
            style.color = '#fbbf24';
            style.fontWeight = '700';
            style.borderTop = idx > 0 ? '1px solid var(--border-subtle)' : 'none';
            style.marginTop = idx > 0 ? '8px' : '0';
            style.paddingTop = idx > 0 ? '6px' : '1px';
          }

          return (
            <div key={idx} style={style}>
              {line || ' '}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="view-btn" onClick={onBack}>
          <ArrowLeft size={16} />
          <span>Back to Overview</span>
        </button>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="room-tag">PROJECT WORKSPACE</span>
          <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)' }}>{project.name}</h2>
        </div>
      </div>

      {/* Main Focus Room Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '20px' }}>
        {/* Left column: Agent roster */}
        <div style={{
          background: 'var(--bg-surface)',
          borderRadius: 'var(--radius-lg)',
          padding: '16px',
          border: '1px solid var(--border-subtle)',
          height: 'fit-content'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
            <Users size={16} color="var(--primary)" />
            <span>Agent Team</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {agents.map((ag) => (
              <div
                key={ag.role}
                onClick={() => onAgentClick && onAgentClick(project.project_id, ag.role)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-canvas)',
                  cursor: 'pointer',
                  border: '1px solid var(--border-subtle)',
                  transition: 'border-color 0.15s'
                }}
                title={`Click to whisper to ${ag.role}`}
              >
                <div>
                  <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-primary)' }}>{ag.role}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{ag.current_task_id || 'Standing by'}</div>
                </div>
                <span className={`agent-status-badge status-${ag.status}`}>
                  {ag.status}
                </span>
              </div>
            ))}
          </div>

          {/* Task summary below agents */}
          {tasks.length > 0 && (
            <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-muted)', marginBottom: '8px' }}>
                TASKS ({tasks.filter(t => t.status === 'DONE').length}/{tasks.length})
              </div>
              {tasks.map((t) => (
                <div key={t.task_id} style={{
                  fontSize: '11px', padding: '4px 0',
                  display: 'flex', justifyContent: 'space-between',
                  color: t.status === 'DONE' ? 'var(--success-text)' : 'var(--text-secondary)'
                }}>
                  <span style={{ textDecoration: t.status === 'DONE' ? 'line-through' : 'none' }}>{t.title}</span>
                  <span className={`agent-status-badge status-${t.status}`} style={{ fontSize: '9px', padding: '1px 5px' }}>
                    {t.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right column: Tabbed Deep-Dive Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
          {/* Tab Bar */}
          <div style={{
            display: 'flex', gap: '2px',
            background: 'var(--bg-canvas)', padding: '3px',
            borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
            border: '1px solid var(--border-subtle)', borderBottom: 'none'
          }}>
            {TABS.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  className={`view-btn ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                  style={{ fontSize: '12px', padding: '6px 12px' }}
                >
                  <Icon size={13} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Tab Content */}
          <div style={{
            background: 'var(--bg-surface)',
            borderRadius: '0 0 var(--radius-lg) var(--radius-lg)',
            padding: '20px',
            border: '1px solid var(--border-subtle)',
            minHeight: '420px',
            flex: 1
          }}>

            {/* War Room */}
            {activeTab === 'war-room' && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
                  <Activity size={16} color="var(--primary)" />
                  <span>Team Activity Stream</span>
                </div>
                <div className="live-stream-box" style={{ height: '380px' }}>
                  {liveStream.length === 0 ? (
                    <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No activity logged yet. Dispatch a directive to begin.</div>
                  ) : (
                    liveStream.map((log, i) => (
                      <div key={i} className="stream-entry">
                        <span className="stream-time">{log.timestamp ? new Date(log.timestamp * 1000).toLocaleTimeString() : ''}</span>
                        <span className="stream-role">[{log.role || 'SYS'}]</span>
                        {log.thought && <span className="stream-thought">{log.thought}</span>}
                        {log.tool && <span className="stream-tool">[tool: {log.tool}]</span>}
                        {log.message && <span className="stream-thought">{log.message}</span>}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Terminal & Tests */}
            {activeTab === 'terminal' && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
                  <Terminal size={16} color="var(--accent-amber)" />
                  <span>Tool Execution & Test Output</span>
                </div>
                <div className="live-stream-box" style={{ height: '380px', background: '#0a0d14' }}>
                  {toolStream.length === 0 ? (
                    <div style={{ color: '#4a5568', fontStyle: 'italic' }}>No tools executed yet. Automated test outputs will stream here.</div>
                  ) : (
                    toolStream.map((log, i) => (
                      <div key={i} className="stream-entry" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                        <span style={{ color: '#fbbf24' }}>$ [{log.role}] {log.tool}</span>
                        {log.args && <div style={{ color: '#94a3b8', paddingLeft: '12px' }}>args: {JSON.stringify(log.args)}</div>}
                        {log.result && <div style={{ color: '#34d399', paddingLeft: '12px' }}>→ {log.result}</div>}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {/* Git Diff / File Changes — Real Live Git View */}
            {activeTab === 'git-diff' && (
              <div>
                {/* Header Bar */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-primary)', fontWeight: '700', fontSize: '14px' }}>
                      <GitBranch size={16} color="var(--primary)" />
                      <span>Live Git Workspace</span>
                    </div>

                    {gitData?.has_git && (
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '2px 8px',
                        borderRadius: '10px',
                        fontSize: '11px',
                        fontWeight: '600',
                        background: 'var(--primary-subtle)',
                        color: 'var(--primary-text)'
                      }}>
                        🌿 {gitData.branch || 'main'}
                      </span>
                    )}

                    {gitData?.has_git && (
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '2px 8px',
                        borderRadius: '10px',
                        fontSize: '11px',
                        fontWeight: '600',
                        background: gitData.clean ? 'rgba(34, 197, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                        color: gitData.clean ? 'var(--success)' : '#d97706'
                      }}>
                        {gitData.clean ? '✅ Clean Working Tree' : `⚠️ ${gitData.files?.length || 0} Modified`}
                      </span>
                    )}
                  </div>

                  <button
                    className="view-btn"
                    onClick={fetchGitStatus}
                    disabled={gitLoading}
                    style={{ fontSize: '11px', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
                    title="Refresh live git status"
                  >
                    <RefreshCw size={12} className={gitLoading ? "spin" : ""} />
                    <span>Refresh Git</span>
                  </button>
                </div>

                {gitLoading && !gitData ? (
                  <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    <Loader2 size={24} className="spin" style={{ margin: '0 auto 8px auto', color: 'var(--primary)' }} />
                    <p style={{ fontSize: '13px' }}>Reading Git status from workspace...</p>
                  </div>
                ) : !gitData?.has_git ? (
                  /* No Git Repo Alert */
                  <div style={{
                    padding: '28px',
                    background: 'var(--bg-canvas)',
                    border: '1px dashed var(--border-medium)',
                    borderRadius: '12px',
                    textAlign: 'center'
                  }}>
                    <GitBranch size={32} color="var(--text-muted)" style={{ margin: '0 auto 12px auto' }} />
                    <h4 style={{ fontSize: '15px', color: 'var(--text-primary)', marginBottom: '6px' }}>
                      No Git Repository Detected
                    </h4>
                    <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '16px', maxWidth: '400px', margin: '0 auto 16px auto' }}>
                      Workspace <code>{project.workspace_path}</code> does not currently have Git initialized.
                    </p>
                    <button
                      className="view-btn active"
                      onClick={handleInitGit}
                      style={{
                        background: 'var(--primary)',
                        color: '#fff',
                        border: 'none',
                        padding: '8px 16px',
                        fontSize: '12px',
                        fontWeight: '600'
                      }}
                    >
                      <FolderPlus size={14} style={{ marginRight: '6px', verticalAlign: 'middle' }} />
                      Initialize Git Repository
                    </button>
                  </div>
                ) : (
                  /* Live Git View */
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {/* Changed Files Selector */}
                    {gitData.files?.length > 0 && (
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        overflowX: 'auto',
                        paddingBottom: '4px'
                      }}>
                        <button
                          className={`view-btn ${selectedFile === 'ALL' ? 'active' : ''}`}
                          onClick={() => setSelectedFile('ALL')}
                          style={{ fontSize: '11px', padding: '3px 8px', whiteSpace: 'nowrap' }}
                        >
                          All Changed Files ({gitData.files.length})
                        </button>
                        {gitData.files.map((f, i) => (
                          <button
                            key={i}
                            className={`view-btn ${selectedFile === f.file ? 'active' : ''}`}
                            onClick={() => setSelectedFile(f.file)}
                            style={{
                              fontSize: '11px',
                              padding: '3px 8px',
                              whiteSpace: 'nowrap',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px'
                            }}
                          >
                            <span style={{
                              fontSize: '9px',
                              fontWeight: '700',
                              color: f.status === 'ADDED' ? 'var(--success)' : f.status === 'DELETED' ? 'var(--accent-coral)' : '#f59e0b'
                            }}>
                              [{f.code}]
                            </span>
                            <span>{f.file}</span>
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Diff Code Container */}
                    <div style={{
                      background: '#090d16',
                      border: '1px solid var(--border-medium)',
                      borderRadius: '10px',
                      height: '260px',
                      overflowY: 'auto',
                      padding: '12px'
                    }}>
                      {renderDiffContent()}
                    </div>

                    {/* Recent Commits Log */}
                    {gitData.commits?.length > 0 && (
                      <div style={{
                        background: 'var(--bg-canvas)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '10px',
                        padding: '12px 16px'
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '8px' }}>
                          <GitCommit size={14} color="var(--accent-purple)" />
                          <span>Recent Commit History ({gitData.commits.length})</span>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          {gitData.commits.slice(0, 5).map((c, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <code style={{ color: 'var(--accent-cyan)', background: 'var(--bg-surface)', padding: '1px 4px', borderRadius: '4px' }}>
                                  {c.hash}
                                </code>
                                <span style={{ color: 'var(--text-primary)', fontWeight: '500' }}>{c.message}</span>
                              </div>
                              <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
                                {c.author} • {c.time}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Playbooks & Skills Tab */}
            {activeTab === 'skills' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h4 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
                      Agent Playbooks & Operational Skills (SKILL.md)
                    </h4>
                    <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                      80% Curated Stock Engineering Standards + 20% Injected Project Context
                    </p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                      onClick={() => setIsSkillStoreOpen(true)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '6px 14px',
                        background: 'linear-gradient(135deg, #10b981 0%, #3b82f6 100%)',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '8px',
                        fontSize: '12px',
                        fontWeight: '700',
                        cursor: 'pointer',
                        boxShadow: '0 2px 8px rgba(16, 185, 129, 0.25)'
                      }}
                    >
                      <Sparkles size={14} />
                      Skill Hub & AGY Sync
                    </button>
                    {saveSuccessMsg && (
                      <span style={{ fontSize: '11px', color: 'var(--success-text)', fontWeight: '600', background: 'var(--success-subtle)', padding: '4px 10px', borderRadius: '6px' }}>
                        ✓ {saveSuccessMsg}
                      </span>
                    )}
                  </div>
                </div>

                {/* 2-Column Split: Agent Roster List on Left, Skill Markdown Editor on Right */}
                <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '14px', minHeight: '380px' }}>
                  {/* Left Column: Team Specialists */}
                  <div style={{
                    background: 'var(--bg-canvas)',
                    border: '1px solid var(--border-medium)',
                    borderRadius: '12px',
                    padding: '12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px'
                  }}>
                    <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                      Team Specialists ({projectSkills.length || agents.length})
                    </span>
                    {(projectSkills.length > 0 ? projectSkills : agents).map((ag) => {
                      const isSelected = selectedSkillRole === ag.role;
                      const tier = ag.skill_tier || 'stock';
                      return (
                        <button
                          key={ag.role}
                          onClick={() => setSelectedSkillRole(ag.role)}
                          style={{
                            background: isSelected ? 'var(--primary)' : 'var(--bg-surface)',
                            color: isSelected ? '#ffffff' : 'var(--text-primary)',
                            border: isSelected ? '1px solid var(--primary)' : '1px solid var(--border-subtle)',
                            borderRadius: '8px',
                            padding: '8px 10px',
                            textAlign: 'left',
                            cursor: 'pointer',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '2px',
                            transition: 'all 0.15s ease'
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '12px', fontWeight: '700' }}>{ag.role}</span>
                            <span style={{
                              fontSize: '8.5px',
                              fontWeight: '700',
                              padding: '1px 4px',
                              borderRadius: '4px',
                              background: isSelected
                                ? 'rgba(255,255,255,0.25)'
                                : (tier === 'project'
                                  ? 'rgba(245,158,11,0.2)'
                                  : tier === 'agy'
                                  ? 'rgba(16,185,129,0.2)'
                                  : 'var(--border-subtle)'),
                              color: isSelected
                                ? '#ffffff'
                                : (tier === 'project'
                                  ? '#d97706'
                                  : tier === 'agy'
                                  ? '#10b981'
                                  : 'var(--text-muted)')
                            }}>
                              {tier.toUpperCase()}
                            </span>
                          </div>
                          <span style={{ fontSize: '10.5px', opacity: isSelected ? 0.9 : 0.7 }}>
                            {ag.skill_title || ag.skill_name || 'Specialist'}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Right Column: Skill Detail & Playbook Editor */}
                  <div style={{
                    background: 'var(--bg-canvas)',
                    border: '1px solid var(--border-medium)',
                    borderRadius: '12px',
                    padding: '16px 18px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px'
                  }}>
                    {skillLoading ? (
                      <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
                        <Loader2 size={28} className="spin" style={{ margin: '0 auto 10px auto', color: 'var(--primary)' }} />
                        <p style={{ fontSize: '13px' }}>Loading agent playbook...</p>
                      </div>
                    ) : skillDetail ? (
                      <>
                        {/* Header with Title and Edit/Save Actions */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px' }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
                                {skillDetail.title || skillDetail.name}
                              </h3>
                              <span style={{
                                fontSize: '10px',
                                fontWeight: '700',
                                padding: '2px 7px',
                                borderRadius: '8px',
                                background: skillDetail.tier === 'project'
                                  ? 'rgba(245, 158, 11, 0.15)'
                                  : skillDetail.tier === 'agy'
                                  ? 'rgba(16, 185, 129, 0.15)'
                                  : 'var(--primary-subtle)',
                                color: skillDetail.tier === 'project'
                                  ? '#d97706'
                                  : skillDetail.tier === 'agy'
                                  ? '#10b981'
                                  : 'var(--primary-text)'
                              }}>
                                {skillDetail.tier === 'project'
                                  ? '⭐ Project Custom Playbook'
                                  : skillDetail.tier === 'agy'
                                  ? '🟢 AGY Antigravity Skill'
                                  : '📦 Stock Library'}
                              </span>
                            </div>
                            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                              {skillDetail.description}
                            </p>
                            {skillDetail.allowed_tools?.length > 0 && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Allowed Tools:</span>
                                {skillDetail.allowed_tools.map((t, idx) => (
                                  <code key={idx} style={{ fontSize: '10px', background: 'var(--bg-surface)', padding: '1px 5px', borderRadius: '4px', border: '1px solid var(--border-subtle)', color: 'var(--accent-cyan)' }}>
                                    {t}
                                  </code>
                                ))}
                              </div>
                            )}
                          </div>

                          <div style={{ display: 'flex', gap: '8px' }}>
                            {isEditingSkill ? (
                              <>
                                <button
                                  className="view-btn"
                                  onClick={() => {
                                    setIsEditingSkill(false);
                                    setSkillEditText(skillDetail.raw_content || skillDetail.instructions || '');
                                  }}
                                  style={{ fontSize: '12px' }}
                                >
                                  Cancel
                                </button>
                                <button
                                  className="view-btn active"
                                  onClick={handleSaveSkill}
                                  disabled={savingSkill}
                                  style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px' }}
                                >
                                  <Save size={13} />
                                  <span>{savingSkill ? 'Saving...' : 'Save & Apply'}</span>
                                </button>
                              </>
                            ) : (
                              <button
                                className="view-btn"
                                onClick={() => setIsEditingSkill(true)}
                                style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px' }}
                              >
                                <Edit3 size={13} />
                                <span>Edit Playbook</span>
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Body: Markdown View or Code Textarea Edit */}
                        {isEditingSkill ? (
                          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, gap: '8px' }}>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                              Edit Markdown & Frontmatter below. Click "Save & Apply" to write this to `.agents/skills/{selectedSkillRole}/SKILL.md`.
                            </span>
                            <textarea
                              value={skillEditText}
                              onChange={(e) => setSkillEditText(e.target.value)}
                              style={{
                                width: '100%',
                                minHeight: '260px',
                                background: 'var(--bg-input)',
                                color: 'var(--text-primary)',
                                fontFamily: 'var(--font-mono)',
                                fontSize: '12px',
                                lineHeight: '1.5',
                                padding: '12px',
                                border: '1px solid var(--border-medium)',
                                borderRadius: '8px',
                                outline: 'none',
                                resize: 'vertical'
                              }}
                            />
                          </div>
                        ) : (
                          <div style={{
                            maxHeight: '290px',
                            overflowY: 'auto',
                            background: 'var(--bg-surface)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '8px',
                            padding: '14px 16px',
                            fontSize: '12px',
                            lineHeight: '1.6',
                            color: 'var(--text-primary)',
                            fontFamily: 'var(--font-mono)',
                            whiteSpace: 'pre-wrap'
                          }}>
                            {skillDetail.instructions || skillDetail.raw_content || 'No instructions specified.'}
                          </div>
                        )}
                      </>
                    ) : (
                      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                        Select an agent specialist on the left to view their operational playbook.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* 1-on-1 Whisper */}
            {activeTab === 'whisper' && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
                  <MessageSquare size={16} color="var(--accent-cyan)" />
                  <span>Direct Agent Whisper Channel</span>
                </div>

                <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
                  {agents.map((ag) => (
                    <button
                      key={ag.role}
                      className={`view-btn ${whisperRole === ag.role ? 'active' : ''}`}
                      onClick={() => setWhisperRole(ag.role)}
                      style={{ fontSize: '11px', padding: '4px 10px' }}
                    >
                      {ag.role}
                    </button>
                  ))}
                </div>

                <form onSubmit={handleWhisperSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <textarea
                    className="whisper-textarea"
                    style={{ height: '120px' }}
                    placeholder={`Whisper directly to ${whisperRole}... e.g. "Use TypeScript for all new components"`}
                    value={whisperText}
                    onChange={(e) => setWhisperText(e.target.value)}
                  />
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button type="submit" className="view-btn active" style={{ fontSize: '12px' }}>
                      Dispatch Whisper
                    </button>
                  </div>
                </form>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* Skill Store & AGY Sync Modal */}
      <SkillStoreModal
        isOpen={isSkillStoreOpen}
        onClose={() => setIsSkillStoreOpen(false)}
        projectId={project?.project_id}
        projectPath={project?.workspace_path}
        agents={projectSkills.length > 0 ? projectSkills : agents}
        onSkillAssigned={(role, skillName) => {
          fetchProjectSkills();
          if (selectedSkillRole === role) {
            fetchSkillDetail(role);
          }
        }}
      />
    </div>
  );
}
