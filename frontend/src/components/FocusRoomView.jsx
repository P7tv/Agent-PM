import React, { useState, useEffect, useRef } from 'react';
import { 
  ArrowLeft, 
  Terminal, 
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
  Sparkles,
  Trash2,
  Send,
  Play,
  XCircle,
  CheckCircle2,
  Copy,
  Crown,
  Bot,
  Paperclip,
  Image as ImageIcon,
  Settings,
  User
} from 'lucide-react';
import { DecisionGateModal } from './DecisionGateModal';
import SkillStoreModal from './SkillStoreModal';
import GitCommitGraph from './GitCommitGraph';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const TABS = [
  { id: 'team-console', label: 'Team Console', icon: MessageSquare },
  { id: 'terminal', label: 'Terminal & Tests', icon: Terminal },
  { id: 'git-diff', label: 'File Changes', icon: GitBranch },
  { id: 'skills', label: 'Playbooks & Skills', icon: BookOpen },
];

// ─── Role Colors & Icons ─────────────────────────────────────
const ROLE_META = {
  TechLead: { color: '#f59e0b', emoji: '👑', label: 'Tech Lead' },
  Architect: { color: '#8b5cf6', emoji: '🏛️', label: 'Architect' },
  Designer: { color: '#ec4899', emoji: '🎨', label: 'Designer' },
  FrontendDev: { color: '#06b6d4', emoji: '⚛️', label: 'Frontend Dev' },
  BackendDev: { color: '#10b981', emoji: '⚙️', label: 'Backend Dev' },
  QATester: { color: '#ef4444', emoji: '🧪', label: 'QA Tester' },
  Reviewer: { color: '#6366f1', emoji: '🔍', label: 'Reviewer' },
  DocWriter: { color: '#14b8a6', emoji: '📝', label: 'Doc Writer' },
  system: { color: '#64748b', emoji: '🔔', label: 'System' },
  user: { color: '#3b82f6', emoji: '👤', label: 'You' },
};

import { ChatMessageItem } from './chat/ChatMessageItem';
import { ChatInputDeck } from './chat/ChatInputDeck';



export default function FocusRoomView({ 
  project, 
  agents, 
  tasks, 
  liveStream, 
  consoleHistory,
  onBack, 
  onAgentClick, 
  onSendWhisper,
  onSendConsoleMessage,
  onRequestDelete,
  onDeleteProject
}) {

  const [activeTab, setActiveTab] = useState('team-console');
  
  const [consoleInput, setConsoleInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const consoleEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const [pendingAttachments, setPendingAttachments] = useState([]);

  // Git live data state
  const [gitData, setGitData] = useState(null);
  const [gitLoading, setGitLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState('ALL');

  // Terminal / Test state
  const [testResults, setTestResults] = useState(null);
  const [testRunning, setTestRunning] = useState(false);

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

  // Computed thinking agents
  const thinkingAgents = (agents || []).filter(a => a.status === 'THINKING');

  // Auto-scroll console
  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [consoleHistory]);

  // ─── Console ────────────────────────────────────────────────
  const handleConsoleSend = async (eOrText) => {
    let textToSend = consoleInput;
    if (eOrText && eOrText.preventDefault) {
      eOrText.preventDefault();
    } else if (typeof eOrText === 'string') {
      textToSend = eOrText;
    }

    if ((!textToSend.trim() && pendingAttachments.length === 0) || isSending) return;
    setIsSending(true);
    try {
      let uploadedAttachments = [];
      if (pendingAttachments.length > 0) {
        for (const file of pendingAttachments) {
          const formData = new FormData();
          formData.append('file', file);
          const res = await fetch(`/api/projects/${project.project_id}/console/upload`, {
            method: 'POST',
            body: formData
          });
          const data = await res.json();
          if (data.status === 'SUCCESS') {
            uploadedAttachments.push(data);
          }
        }
      }

      if (onSendConsoleMessage) {
        await onSendConsoleMessage(project.project_id, textToSend, uploadedAttachments);
      }
    } catch (err) {
      console.error('Console send error:', err);
    } finally {
      setConsoleInput('');
      setPendingAttachments([]);
      setIsSending(false);
    }
  };

  // ─── Tests ──────────────────────────────────────────────────
  const handleRunTests = async () => {
    if (!project?.project_id || testRunning) return;
    setTestRunning(true);
    setTestResults(null);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/run-tests`, { method: 'POST' });
      const data = await res.json();
      setTestResults(data);
    } catch (err) {
      setTestResults({ status: 'ERROR', stderr: String(err), stdout: '', command: 'unknown' });
    } finally {
      setTestRunning(false);
    }
  };

  // ─── Skills ─────────────────────────────────────────────────
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

  const handleRemoveSkill = async (role, skillName) => {
    if (!project?.project_id) return;
    try {
      await fetch(`/api/projects/${project.project_id}/agents/${role}/skills/remove`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_name: skillName })
      });
      fetchProjectSkills();
    } catch (err) {
      console.error('Failed to remove skill:', err);
    }
  };

  const handleToggleMode = async (role, currentMode) => {
    if (!project?.project_id) return;
    const newMode = currentMode === 'AUTO' ? 'MANUAL' : 'AUTO';
    try {
      await fetch(`/api/projects/${project.project_id}/agents/${role}/skills/set-mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode })
      });
      fetchProjectSkills();
    } catch (err) {
      console.error('Failed to toggle mode:', err);
    }
  };

  // ─── Git ────────────────────────────────────────────────────
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

  // Filter stream by type for terminal tab
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

  // Quick mention buttons for console
  const mentionButtons = [
    { label: '👑 TechLead', value: '@TechLead ' },
    { label: '🏛️ Architect', value: '@Architect ' },
    { label: '⚛️ Frontend', value: '@FrontendDev ' },
    { label: '⚙️ Backend', value: '@BackendDev ' },
    { label: '📢 Team', value: '@Team ' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button className="view-btn" onClick={onBack}>
          <ArrowLeft size={16} />
          <span>Back to Overview</span>
        </button>
        <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span className="room-tag">PROJECT WORKSPACE</span>
            <h2 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)' }}>{project.name}</h2>
          </div>
          {(onRequestDelete || onDeleteProject) && (
            <button
              className="view-btn"
              onClick={() => {
                if (onRequestDelete) {
                  onRequestDelete(project);
                } else {
                  onDeleteProject(project.project_id);
                }
              }}
              title="Disconnect and remove project"
              style={{
                color: 'var(--accent-coral)',
                borderColor: 'rgba(239, 68, 68, 0.3)',
                padding: '6px 12px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '12px'
              }}
            >
              <Trash2 size={14} />
              <span>Delete Project</span>
            </button>
          )}
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
            {agents.map((ag) => {
              const roleMeta = ROLE_META[ag.role] || ROLE_META.system;
              return (
                <div
                  key={ag.role}
                  onClick={() => {
                    // Click agent → insert @mention in console
                    setConsoleInput(prev => prev ? prev : `@${ag.role} `);
                    setActiveTab('team-console');
                  }}
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
                  title={`Click to chat with ${ag.role} in Team Console`}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '14px' }}>{roleMeta.emoji}</span>
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-primary)' }}>{ag.role}</div>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', maxWidth: '130px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {ag.thought || ag.current_task_id || 'Standing by'}
                      </div>
                    </div>
                  </div>
                  <span className={`agent-status-badge status-${ag.status}`}>
                    {ag.status}
                  </span>
                </div>
              );
            })}
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
            padding: activeTab === 'team-console' ? '0' : '20px',
            border: '1px solid var(--border-subtle)',
            minHeight: '480px',
            flex: 1,
            display: 'flex',
            flexDirection: 'column'
          }}>

            {/* ═══ TEAM CONSOLE ═══ */}
            {activeTab === 'team-console' && (
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                {/* Console Header */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '12px 16px',
                  borderBottom: '1px solid var(--border-subtle)',
                  background: 'var(--bg-canvas)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
                    <MessageSquare size={16} color="var(--primary)" />
                    <span>Team Console</span>
                    <span style={{
                      fontSize: '10px', padding: '2px 8px', borderRadius: '8px',
                      background: 'var(--primary-subtle)', color: 'var(--primary-text)',
                      fontWeight: '700'
                    }}>
                      Use @Role to talk to specific agents
                    </span>
                  </div>
                </div>

                {/* Message Thread Container */}
                <div style={{
                  flex: 1,
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  minHeight: '340px',
                  maxHeight: '420px',
                  background: 'var(--bg-primary)'
                }}>
                  <div style={{ maxWidth: '980px', margin: '0 auto', width: '100%', padding: '24px 20px' }}>
                    {(!consoleHistory || consoleHistory.length === 0) ? (
                      <div style={{
                        textAlign: 'center', padding: '60px 20px',
                        color: 'var(--text-muted)', fontSize: '13px'
                      }}>
                        <Bot size={36} style={{ margin: '0 auto 12px auto', opacity: 0.3 }} />
                        <p style={{ fontWeight: '600', marginBottom: '6px' }}>Team Console Ready</p>
                        <p style={{ fontSize: '12px', maxWidth: '320px', margin: '0 auto', lineHeight: '1.5' }}>
                          Start a conversation or mention an agent using @Role.
                        </p>
                      </div>
                    ) : (
                      consoleHistory.map((msg, i) => (
                        <ChatMessageItem
                          key={msg.message_id || i}
                          msg={{ ...msg, project_id: project.project_id }}
                          onApply={() => {
                            if (activeTab === 'git-diff') fetchGitStatus();
                          }}
                        />
                      ))
                    )}
                    {thinkingAgents.map(ag => (
                      <div key={`thinking-${ag.role}`} style={{
                        display: 'flex', gap: '10px', padding: '6px 0', alignItems: 'flex-start'
                      }}>
                        <div style={{
                          width: '32px', height: '32px', borderRadius: '10px',
                          background: `linear-gradient(135deg, ${(ROLE_META[ag.role] || ROLE_META.system).color}44, ${(ROLE_META[ag.role] || ROLE_META.system).color}22)`,
                          border: `1.5px solid ${(ROLE_META[ag.role] || ROLE_META.system).color}55`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: '15px', flexShrink: 0,
                          color: (ROLE_META[ag.role] || ROLE_META.system).color
                        }}>
                          {(ROLE_META[ag.role] || ROLE_META.system).emoji}
                        </div>
                        <div style={{ maxWidth: '75%', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          <span style={{ fontSize: '11px', fontWeight: '700', color: (ROLE_META[ag.role] || ROLE_META.system).color }}>
                            {(ROLE_META[ag.role] || ROLE_META.system).emoji} {ag.role}
                          </span>
                          <div style={{
                            padding: '10px 14px', borderRadius: '14px 14px 14px 4px',
                            background: 'var(--bg-canvas)', color: 'var(--text-muted)',
                            border: '1px solid var(--border-subtle)', fontSize: '12.5px',
                            display: 'flex', alignItems: 'center', gap: '8px'
                          }}>
                            <Loader2 size={14} className="spin" />
                            <span style={{ fontStyle: 'italic' }}>{ag.thought || 'Processing...'}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                    <div ref={consoleEndRef} />
                  </div>
                </div>

                {/* Input Bar */}
                <div style={{ maxWidth: '980px', margin: '0 auto', width: '100%', padding: '0 20px' }}>
                  {pendingAttachments.length > 0 && (
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', padding: '8px 16px', background: 'var(--bg-canvas)' }}>
                      {pendingAttachments.map((f, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'var(--bg-surface)', padding: '2px 8px', borderRadius: '12px', fontSize: '11px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ maxWidth: '100px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-primary)' }}>{f.name}</span>
                          <button type="button" onClick={() => setPendingAttachments(prev => prev.filter((_, idx) => idx !== i))} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}><XCircle size={12} /></button>
                        </div>
                      ))}
                    </div>
                  )}
                  <input type="file" ref={fileInputRef} multiple style={{ display: 'none' }} onChange={(e) => { if (e.target.files) setPendingAttachments(prev => [...prev, ...Array.from(e.target.files)]); }} />
                  <ChatInputDeck 
                    onSendMessage={handleConsoleSend} 
                    isSending={isSending} 
                    onAttachFile={() => fileInputRef.current?.click()}
                  />
                </div>
              </div>
            )}

            {/* ═══ TERMINAL & TESTS ═══ */}
            {activeTab === 'terminal' && (
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
                    <Terminal size={16} color="var(--accent-amber)" />
                    <span>Tool Execution & Test Output</span>
                  </div>
                  <button
                    onClick={handleRunTests}
                    disabled={testRunning}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '6px',
                      padding: '6px 14px', borderRadius: '8px',
                      background: testRunning ? 'var(--text-muted)' : 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                      color: '#fff', border: 'none', cursor: testRunning ? 'wait' : 'pointer',
                      fontWeight: '700', fontSize: '12px',
                      boxShadow: '0 2px 8px rgba(16, 185, 129, 0.2)'
                    }}
                  >
                    {testRunning ? <Loader2 size={13} className="spin" /> : <Play size={13} />}
                    <span>{testRunning ? 'Running...' : '▶ Run Tests'}</span>
                  </button>
                </div>

                {/* Test Results */}
                {testResults && (
                  <div style={{ marginBottom: '14px' }}>
                    <QAResultCard qaResults={testResults} />
                  </div>
                )}

                {/* Tool Stream */}
                <div className="live-stream-box" style={{ flex: 1, minHeight: '280px', background: '#0a0d14' }}>
                  {toolStream.length === 0 && !testResults ? (
                    <div style={{ color: '#4a5568', fontStyle: 'italic' }}>No tools executed yet. Use "Run Tests" above or send a directive.</div>
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

            {/* ═══ GIT DIFF / FILE CHANGES ═══ */}
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
                        display: 'inline-flex', alignItems: 'center', gap: '4px',
                        padding: '2px 8px', borderRadius: '10px', fontSize: '11px',
                        fontWeight: '600', background: 'var(--primary-subtle)', color: 'var(--primary-text)'
                      }}>
                        🌿 {gitData.branch || 'main'}
                      </span>
                    )}

                    {gitData?.has_git && (
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: '4px',
                        padding: '2px 8px', borderRadius: '10px', fontSize: '11px',
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
                  <div style={{
                    padding: '28px', background: 'var(--bg-canvas)',
                    border: '1px dashed var(--border-medium)', borderRadius: '12px', textAlign: 'center'
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
                        background: 'var(--primary)', color: '#fff', border: 'none',
                        padding: '8px 16px', fontSize: '12px', fontWeight: '600'
                      }}
                    >
                      <FolderPlus size={14} style={{ marginRight: '6px', verticalAlign: 'middle' }} />
                      Initialize Git Repository
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {gitData.files?.length > 0 && (
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: '6px',
                        overflowX: 'auto', paddingBottom: '4px'
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
                              fontSize: '11px', padding: '3px 8px', whiteSpace: 'nowrap',
                              display: 'flex', alignItems: 'center', gap: '4px'
                            }}
                          >
                            <span style={{
                              fontSize: '9px', fontWeight: '700',
                              color: f.status === 'ADDED' ? 'var(--success)' : f.status === 'DELETED' ? 'var(--accent-coral)' : '#f59e0b'
                            }}>
                              [{f.code}]
                            </span>
                            <span>{f.file}</span>
                          </button>
                        ))}
                      </div>
                    )}

                    {gitData.files?.length > 0 ? (
                      <div style={{
                        background: '#090d16', border: '1px solid var(--border-medium)',
                        borderRadius: '10px', height: '260px', overflowY: 'auto', padding: '12px'
                      }}>
                        {renderDiffContent()}
                      </div>
                    ) : (
                      <div style={{
                        padding: '16px 20px', background: 'var(--bg-canvas)',
                        border: '1px solid var(--border-subtle)', borderRadius: '10px',
                        display: 'flex', alignItems: 'center', gap: '12px'
                      }}>
                        <div style={{
                          width: '32px', height: '32px', borderRadius: '8px',
                          background: 'rgba(16, 185, 129, 0.12)',
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          color: '#34d399'
                        }}>
                          <CheckCircle size={18} />
                        </div>
                        <div>
                          <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)' }}>
                            Working Tree Clean
                          </div>
                          <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                            All workspace files are committed and aligned with branch <code>{gitData.branch}</code>.
                          </div>
                        </div>
                      </div>
                    )}

                    <GitCommitGraph commits={gitData.commits} branch={gitData.branch} />
                  </div>
                )}
              </div>
            )}

            {/* ═══ PLAYBOOKS & SKILLS ═══ */}
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
                        display: 'flex', alignItems: 'center', gap: '6px',
                        padding: '6px 14px',
                        background: 'linear-gradient(135deg, #10b981 0%, #3b82f6 100%)',
                        color: '#ffffff', border: 'none', borderRadius: '8px',
                        fontSize: '12px', fontWeight: '700', cursor: 'pointer',
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

                <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: '14px', minHeight: '380px' }}>
                  {/* Left Column: Team Specialists */}
                  <div style={{
                    background: 'var(--bg-canvas)', border: '1px solid var(--border-medium)',
                    borderRadius: '12px', padding: '12px',
                    display: 'flex', flexDirection: 'column', gap: '6px'
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
                            borderRadius: '8px', padding: '8px 10px', textAlign: 'left',
                            cursor: 'pointer', display: 'flex', flexDirection: 'column',
                            gap: '2px', transition: 'all 0.15s ease'
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '12px', fontWeight: '700' }}>{ag.role}</span>
                            <span style={{
                              fontSize: '8.5px', fontWeight: '700', padding: '1px 4px', borderRadius: '4px',
                              background: isSelected ? 'rgba(255,255,255,0.25)' : (tier === 'project' ? 'rgba(245,158,11,0.2)' : tier === 'agy' ? 'rgba(16,185,129,0.2)' : 'var(--border-subtle)'),
                              color: isSelected ? '#ffffff' : (tier === 'project' ? '#d97706' : tier === 'agy' ? '#10b981' : 'var(--text-muted)')
                            }}>
                              {tier.toUpperCase()}
                            </span>
                          </div>
                          <span style={{ fontSize: '10.5px', opacity: isSelected ? 0.9 : 0.7 }}>
                            {ag.equipped_skills?.length > 0 ? `${ag.equipped_skills.length} skills equipped` : (ag.skill_mode === 'AUTO' ? 'Auto-Adaptive' : 'No skills')}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Right Column: Skill Detail & Playbook Editor */}
                  <div style={{
                    background: 'var(--bg-canvas)', border: '1px solid var(--border-medium)',
                    borderRadius: '12px', padding: '16px 18px',
                    display: 'flex', flexDirection: 'column', gap: '12px'
                  }}>
                    {skillLoading ? (
                      <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
                        <Loader2 size={28} className="spin" style={{ margin: '0 auto 10px auto', color: 'var(--primary)' }} />
                        <p style={{ fontSize: '13px' }}>Loading agent playbook...</p>
                      </div>
                    ) : skillDetail ? (
                      <>
                        {(() => {
                          const selectedAgent = projectSkills.find(ag => ag.role === selectedSkillRole) || agents.find(ag => ag.role === selectedSkillRole);
                          const isAuto = selectedAgent?.skill_mode === 'AUTO';
                          const equipped = selectedAgent?.equipped_skills || [];
                          
                          return (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                              
                              {/* Equipped Skills Section */}
                              <div style={{ background: 'var(--bg-input)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Sparkles size={14} color="var(--primary)" />
                                    <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)' }}>Equipped Capabilities</span>
                                  </div>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <button
                                      onClick={() => handleToggleMode(selectedSkillRole, selectedAgent?.skill_mode)}
                                      style={{
                                        fontSize: '11px', padding: '4px 10px', borderRadius: '12px', border: '1px solid var(--border-subtle)',
                                        background: isAuto ? 'var(--primary-subtle)' : 'var(--bg-surface)',
                                        color: isAuto ? 'var(--primary-text)' : 'var(--text-secondary)',
                                        cursor: 'pointer', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '4px'
                                      }}
                                    >
                                      {isAuto ? <RefreshCw size={12} /> : <Settings size={12} />}
                                      Mode: {isAuto ? 'Auto-Adaptive' : 'Manual'}
                                    </button>
                                    <button
                                      onClick={() => setIsSkillStoreOpen(true)}
                                      style={{
                                        fontSize: '11px', padding: '4px 10px', borderRadius: '12px', border: 'none',
                                        background: 'var(--primary)', color: '#fff', cursor: 'pointer', fontWeight: '600'
                                      }}
                                    >
                                      + Equip Skill
                                    </button>
                                  </div>
                                </div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                  {isAuto && equipped.length === 0 ? (
                                    <span style={{ fontSize: '11.5px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                      Agent will automatically select relevant domain skills when needed.
                                    </span>
                                  ) : equipped.length === 0 ? (
                                    <span style={{ fontSize: '11.5px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                      No skills equipped in Manual mode.
                                    </span>
                                  ) : (
                                    equipped.map(sName => (
                                      <div key={sName} style={{
                                        display: 'flex', alignItems: 'center', gap: '4px', padding: '3px 8px', borderRadius: '12px',
                                        background: 'var(--bg-surface)', border: '1px solid var(--primary)', fontSize: '11.5px', color: 'var(--text-primary)'
                                      }}>
                                        {sName}
                                        <button onClick={() => handleRemoveSkill(selectedSkillRole, sName)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0', marginLeft: '4px' }}>
                                          <XCircle size={12} />
                                        </button>
                                      </div>
                                    ))
                                  )}
                                </div>
                              </div>
                              
                              {/* Core Role Playbook Section */}
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
                                <div>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <h3 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
                                      {skillDetail.title || skillDetail.name}
                                    </h3>
                                    <span style={{
                                      fontSize: '10px', fontWeight: '700', padding: '2px 7px', borderRadius: '8px',
                                      background: 'var(--primary-subtle)', color: 'var(--primary-text)'
                                    }}>
                                      CORE ROLE
                                    </span>
                                  </div>
                                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                                    {skillDetail.description}
                                  </p>
                                </div>
                                <div style={{ display: 'flex', gap: '8px' }}>
                                  {isEditingSkill ? (
                                    <>
                                      <button className="view-btn" onClick={() => { setIsEditingSkill(false); setSkillEditText(skillDetail.raw_content || skillDetail.instructions || ''); }} style={{ fontSize: '12px' }}>Cancel</button>
                                      <button className="view-btn active" onClick={handleSaveSkill} disabled={savingSkill} style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                                        <Save size={13} /><span>{savingSkill ? 'Saving...' : 'Save & Apply'}</span>
                                      </button>
                                    </>
                                  ) : (
                                    <button className="view-btn" onClick={() => setIsEditingSkill(true)} style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                                      <Edit3 size={13} /><span>Edit Playbook</span>
                                    </button>
                                  )}
                                </div>
                              </div>

                              {isEditingSkill ? (
                                <div style={{ display: 'flex', flexDirection: 'column', flex: 1, gap: '8px' }}>
                                  <textarea
                                    value={skillEditText}
                                    onChange={(e) => setSkillEditText(e.target.value)}
                                    style={{ width: '100%', minHeight: '200px', background: 'var(--bg-input)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: '12px', lineHeight: '1.5', padding: '12px', border: '1px solid var(--border-medium)', borderRadius: '8px', outline: 'none', resize: 'vertical' }}
                                  />
                                </div>
                              ) : (
                                <div style={{ maxHeight: '200px', overflowY: 'auto', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '14px 16px', fontSize: '12px', lineHeight: '1.6', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap' }}>
                                  {skillDetail.instructions || skillDetail.raw_content || 'No instructions specified.'}
                                </div>
                              )}
                            </div>
                          );
                        })()}
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
