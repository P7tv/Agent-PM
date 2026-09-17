import React, { useState, useEffect, useRef } from 'react';
import SprintRecoveryPanel from './SprintRecoveryPanel';
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
  User,
  History,
  FolderTree,
  Square,
  Download,
  ListTodo,
  BookMarked,
  UploadCloud,
  DownloadCloud
} from 'lucide-react';
import { DecisionGateModal } from './DecisionGateModal';
import SkillStoreModal from './SkillStoreModal';
import BacklogBoardModal from './BacklogBoardModal';
import ProjectJournalModal from './ProjectJournalModal';
import GitCommitGraph from './GitCommitGraph';
import SprintHistoryPanel from './SprintHistoryPanel';
import ActivityTimeline from './ActivityTimeline';
import WorkspaceFileBrowser from './WorkspaceFileBrowser';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const TABS = [
  { id: 'mission-hub', label: 'Mission Hub', icon: MessageSquare },
  { id: 'code-and-git', label: 'Code & Changes', icon: Code2 },
  { id: 'sprints-qa', label: 'Sprints & QA', icon: History },
  { id: 'skills', label: 'Team & Skills', icon: BookOpen },
];

const TAB_ALIASES = {
  'team-console': 'mission-hub',
  'timeline': 'mission-hub',
  'files': 'code-and-git',
  'git-diff': 'code-and-git',
  'sprints': 'sprints-qa',
  'terminal': 'sprints-qa',
  'skills': 'skills',
  'mission-hub': 'mission-hub',
  'code-and-git': 'code-and-git',
  'sprints-qa': 'sprints-qa'
};

// ─── Role Colors & Icons ─────────────────────────────────────
export const ROLE_META = {
  TechLead: { color: '#f59e0b', icon: Bot, label: 'Tech Lead' },
  Architect: { color: '#8b5cf6', icon: Compass, label: 'Architect' },
  Designer: { color: '#ec4899', icon: Palette, label: 'Designer' },
  FrontendDev: { color: '#06b6d4', icon: Layout, label: 'Frontend Dev' },
  BackendDev: { color: '#10b981', icon: Server, label: 'Backend Dev' },
  QATester: { color: '#ef4444', icon: FlaskConical, label: 'QA Tester' },
  Reviewer: { color: '#6366f1', icon: ShieldCheck, label: 'Reviewer' },
  DocWriter: { color: '#14b8a6', icon: FileText, label: 'Doc Writer' },
  system: { color: '#64748b', icon: Bell, label: 'System' },
  user: { color: '#3b82f6', icon: User, label: 'You' },
};

import { ChatMessageItem } from './chat/ChatMessageItem';
import { useToast } from './Toast';
import SprintPipelineStepper from './SprintPipelineStepper';
import { Palette, Layout, Server, FlaskConical, ShieldCheck, FileText, Compass, Bell } from 'lucide-react';
import { ChatInputDeck } from './chat/ChatInputDeck';



export default function FocusRoomView({ 
  project, 
  agents = [], 
  tasks = [], 
  liveStream = [], 
  consoleHistory,
  timelineEvents = [],
  sprints = [],
  initialTab = 'mission-hub',
  onTabChange,
  onRerunSprint,
  onRetrySprint,
  onBack, 
  onAgentClick, 
  onSendWhisper,
  onSendConsoleMessage,
  onRequestDelete,
  onDeleteProject
}) {
  const toast = useToast();
  const [stoppingSprint, setStoppingSprint] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (onBack) onBack();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onBack]);

  const [activeTab, setActiveTab] = useState(() => {
    const raw = initialTab || 'mission-hub';
    return TAB_ALIASES[raw] || raw;
  });

  useEffect(() => {
    if (initialTab) {
      const normalized = TAB_ALIASES[initialTab] || initialTab;
      if (normalized !== activeTab) {
        setActiveTab(normalized);
      }
    }
  }, [initialTab]);

  const handleTabSelect = (tabId) => {
    setActiveTab(tabId);
    if (onTabChange) {
      onTabChange(tabId);
    }
  };

  const [missionSubView, setMissionSubView] = useState('chat'); // 'chat' | 'timeline' | 'split'
  const [codeSubView, setCodeSubView] = useState('files'); // 'files' | 'git'
  const [sprintSubView, setSprintSubView] = useState('history'); // 'history' | 'tests'
  
  const currentTab = TAB_ALIASES[activeTab] || activeTab;
  
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
  const [personaText, setPersonaText] = useState('');
  const [identityName, setIdentityName] = useState('');
  const [identitySaving, setIdentitySaving] = useState(false);
  const [promptPreview, setPromptPreview] = useState(null);
  const [previewMessage, setPreviewMessage] = useState('');
  const [promptMode, setPromptMode] = useState('');
  const [promptBusy, setPromptBusy] = useState(false);
  const [promptTraces, setPromptTraces] = useState(null);
  const skillRequestRef = useRef(0);
  const skillContextRef = useRef('');
  skillContextRef.current = `${project?.project_id}:${selectedSkillRole}`;
  const [skillLoading, setSkillLoading] = useState(false);
  const [isEditingSkill, setIsEditingSkill] = useState(false);
  const [skillEditText, setSkillEditText] = useState('');
  const [savingSkill, setSavingSkill] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState(null);
  const [isSkillStoreOpen, setIsSkillStoreOpen] = useState(false);

  // Backlog & Journal modals state
  const [isBacklogOpen, setIsBacklogOpen] = useState(false);
  const [isJournalOpen, setIsJournalOpen] = useState(false);

  // Git Remotes & Branch state
  const [gitBranches, setGitBranches] = useState([]);
  const [gitRemotes, setGitRemotes] = useState({});
  const [gitActionLoading, setGitActionLoading] = useState(false);
  const [gitToast, setGitToast] = useState(null);
  const [isSettingRemote, setIsSettingRemote] = useState(false);
  const [remoteUrlInput, setRemoteUrlInput] = useState('');

  // Agent Performance & Activity Metrics state
  const [agentMetrics, setAgentMetrics] = useState({});
  const [recentActivities, setRecentActivities] = useState([]);
  const [showActivityLog, setShowActivityLog] = useState(false);
  const [projectConfig, setProjectConfig] = useState(null);
  const [previewRunning, setPreviewRunning] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);

  useEffect(() => {
    fetch(`/api/projects/${project.project_id}/config`)
      .then(res => res.ok ? res.json() : null)
      .then(setProjectConfig)
      .catch(() => setProjectConfig(null));
    fetch(`/api/projects/${project.project_id}/preview`)
      .then(res => res.ok ? res.json() : null)
      .then(data => setPreviewRunning(Boolean(data?.running)))
      .catch(() => setPreviewRunning(false));
  }, [project.project_id]);

  const togglePreview = async () => {
    setPreviewBusy(true);
    try {
      const response = await fetch(`/api/projects/${project.project_id}/preview`, { method: previewRunning ? 'DELETE' : 'POST' });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Preview action failed');
      setPreviewRunning(Boolean(data.running));
    } catch (error) {
      toast.error(error.message);
    } finally {
      setPreviewBusy(false);
    }
  };

  // Computed thinking agents
  const thinkingAgents = (agents || []).filter(a => a.status === 'THINKING');

  // Auto-scroll console
  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [consoleHistory]);

  // ─── Console ────────────────────────────────────────────────
  const handleConsoleSend = async (eOrText, isDirective = false) => {
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
          if (!res.ok) throw new Error(data.detail || 'Upload failed');
          if (data.status === 'SUCCESS') {
            uploadedAttachments.push(data);
          }
        }
      }

      if (onSendConsoleMessage) {
        await onSendConsoleMessage(project.project_id, textToSend, uploadedAttachments, isDirective);
        setConsoleInput('');
        setPendingAttachments([]);
      }
    } catch (err) {
      console.error('Console send error:', err);
      throw err;
    } finally {
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
    const context = `${project.project_id}:${role}`;
    if (context !== skillContextRef.current) return;
    const requestId = ++skillRequestRef.current;
    setSkillLoading(true);
    setSkillDetail(null);
    setIsEditingSkill(false);
    setSaveSuccessMsg(null);
    setPromptPreview(null);
    setPromptTraces(null);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/skills/${role}`);
      const data = await res.json();
      if (requestId !== skillRequestRef.current || context !== skillContextRef.current) return;
      if (!res.ok) throw new Error(data.detail || 'โหลด playbook ไม่สำเร็จ');
      setSkillDetail(data);
      setPersonaText(data.persona || '');
      setIdentityName(data.display_name || role);
      setSkillEditText(data.raw_content || data.instructions || '');
    } catch (err) {
      if (requestId === skillRequestRef.current && context === skillContextRef.current) toast.error(err.message);
    } finally {
      if (requestId === skillRequestRef.current && context === skillContextRef.current) setSkillLoading(false);
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
  }, [activeTab, selectedSkillRole, project?.project_id]);

    const handleSaveSkill = async () => {
    if (!project?.project_id || !selectedSkillRole || savingSkill || skillDetail?.role !== selectedSkillRole) return;
    setSavingSkill(true);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/skills/${selectedSkillRole}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: skillEditText })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'บันทึก project rules ไม่สำเร็จ');
      if (data.status === 'SUCCESS') {
        setSaveSuccessMsg('บันทึก Project Rules แล้ว จะใช้ในการเรียก agent ครั้งถัดไป');
        setIsEditingSkill(false);
        fetchProjectSkills();
        fetchSkillDetail(selectedSkillRole);
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSavingSkill(false);
    }
  };

  const handleSaveIdentity = async () => {
    if (identitySaving || !selectedSkillRole || skillDetail?.role !== selectedSkillRole) return;
    setIdentitySaving(true);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/agents/${selectedSkillRole}/identity`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: identityName, persona: personaText })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'ตรวจชื่อและ persona อีกครั้ง');
      toast.success('บันทึก persona แล้ว ใช้ทั้งการคุยและสั่งงานครั้งถัดไป');
      setPromptPreview(null);
      await fetchProjectSkills();
      await fetchSkillDetail(selectedSkillRole);
    } catch (error) { toast.error(error.message); }
    finally { setIdentitySaving(false); }
  };

  const handlePromptPreview = async () => {
    if (promptBusy || !selectedSkillRole) return;
    setPromptBusy(true);
    const context = skillContextRef.current;
    try {
      const res = await fetch(`/api/projects/${project.project_id}/agents/${selectedSkillRole}/prompt-preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: previewMessage, mode: promptMode || null })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'สร้าง preview ไม่สำเร็จ');
      if (context === skillContextRef.current) setPromptPreview(data);
    } catch (error) { toast.error(error.message); }
    finally { setPromptBusy(false); }
  };

  const handlePromptTraces = async () => {
    if (promptBusy || !selectedSkillRole) return;
    setPromptBusy(true);
    const context = skillContextRef.current;
    try {
      const res = await fetch(`/api/projects/${project.project_id}/agents/${selectedSkillRole}/prompt-traces`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'โหลดประวัติ prompt ไม่สำเร็จ');
      if (context === skillContextRef.current) setPromptTraces(data);
    } catch (error) { toast.error(error.message); }
    finally { setPromptBusy(false); }
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

  const fetchGitBranches = async () => {
    if (!project?.project_id) return;
    try {
      const res = await fetch(`/api/projects/${project.project_id}/git/branches`);
      const data = await res.json();
      setGitBranches(data.branches || []);
    } catch (err) {
      console.error('Failed to fetch git branches:', err);
    }
  };

  const fetchGitRemotes = async () => {
    if (!project?.project_id) return;
    try {
      const res = await fetch(`/api/projects/${project.project_id}/git/remotes`);
      const data = await res.json();
      setGitRemotes(data.remotes || {});
    } catch (err) {
      console.error('Failed to fetch git remotes:', err);
    }
  };

  const handleCheckoutBranch = async (branchName) => {
    if (!project?.project_id || gitActionLoading) return;
    setGitActionLoading(true);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/git/checkout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ branch_name: branchName })
      });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        toast.success(`Switched to branch ${branchName}`);
        await fetchGitStatus();
        await fetchGitBranches();
      } else {
        toast.error(data.error || 'Failed to switch branch');
      }
    } catch (err) {
      toast.error(String(err));
    } finally {
      setGitActionLoading(false);
    }
  };

  const handleCreateBranch = async () => {
    if (!project?.project_id || gitActionLoading) return;
    const branchName = window.prompt('Enter new branch name:');
    if (!branchName || !branchName.trim()) return;
    setGitActionLoading(true);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/git/branches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ branch_name: branchName.trim(), checkout: true })
      });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        toast.success(`Created & checked out ${branchName.trim()}`);
        await fetchGitStatus();
        await fetchGitBranches();
      } else {
        toast.error(data.error || 'Failed to create branch');
      }
    } catch (err) {
      toast.error(String(err));
    } finally {
      setGitActionLoading(false);
    }
  };

  const handleSetRemote = async () => {
    if (!project?.project_id || !remoteUrlInput.trim() || gitActionLoading) return;
    setGitActionLoading(true);
    try {
      await fetch(`/api/projects/${project.project_id}/git/remotes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'origin', url: remoteUrlInput.trim() })
      });
      setIsSettingRemote(false);
      await fetchGitRemotes();
      toast.success('Remote origin updated');
    } catch (err) {
      toast.error(String(err));
    } finally {
      setGitActionLoading(false);
    }
  };

  const handlePushGit = async () => {
    if (!project?.project_id || gitActionLoading) return;
    setGitActionLoading(true);
    setGitToast(null);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/git/push`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ remote: 'origin', branch: gitData?.branch || 'main' })
      });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        toast.success('Pushed changes successfully!');
      } else {
        toast.error(`Git push output: ${data.stderr || data.error || 'Failed'}`);
      }
    } catch (err) {
      toast.error(String(err));
    } finally {
      setGitActionLoading(false);
    }
  };

  const handlePullGit = async () => {
    if (!project?.project_id || gitActionLoading) return;
    setGitActionLoading(true);
    setGitToast(null);
    try {
      const res = await fetch(`/api/projects/${project.project_id}/git/pull`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ remote: 'origin', branch: gitData?.branch || 'main' })
      });
      const data = await res.json();
      if (data.status === 'SUCCESS') {
        toast.success('Pulled latest changes!');
        await fetchGitStatus();
      } else {
        toast.error(`Git pull output: ${data.stderr || data.error || 'Failed'}`);
      }
    } catch (err) {
      toast.error(String(err));
    } finally {
      setGitActionLoading(false);
    }
  };

  // ─── Agent Metrics & Activity ───────────────────────────────
  const fetchAgentMetrics = async () => {
    if (!project?.project_id) return;
    try {
      const res = await fetch(`/api/projects/${project.project_id}/agents/metrics`);
      const data = await res.json();
      setAgentMetrics(data || {});
    } catch (err) {
      console.error('Failed to fetch agent metrics:', err);
    }
  };

  const fetchRecentActivities = async (role) => {
    if (!project?.project_id) return;
    try {
      const url = role 
        ? `/api/projects/${project.project_id}/agents/activities?role=${role}&limit=20`
        : `/api/projects/${project.project_id}/agents/activities?limit=20`;
      const res = await fetch(url);
      const data = await res.json();
      setRecentActivities(data || []);
    } catch (err) {
      console.error('Failed to fetch activities:', err);
    }
  };

  useEffect(() => {
    if (currentTab === 'code-and-git' && codeSubView === 'git') {
      fetchGitStatus();
      fetchGitBranches();
      fetchGitRemotes();
    }
  }, [currentTab, codeSubView, project?.project_id]);

  useEffect(() => {
    if (currentTab === 'skills') {
      fetchAgentMetrics();
      if (selectedSkillRole) {
        fetchRecentActivities(selectedSkillRole);
      }
    }
  }, [currentTab, selectedSkillRole, project?.project_id]);

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
      <div className="focus-room-header">
        <button className="view-btn back-to-overview-btn" onClick={onBack}>
          <ArrowLeft size={16} />
          <span>Back to Overview</span>
        </button>
        <div className="focus-header-meta">
          <span className="room-tag">PROJECT WORKSPACE</span>
          <h2 className="focus-header-title">{project.name}</h2>
        </div>
        <div className="focus-header-actions">

          {projectConfig?.preview?.url && (
            <>
              <button className="view-btn" onClick={togglePreview} disabled={previewBusy} title="Start or stop the configured preview process">
                {previewRunning ? <Square size={13} /> : <Play size={14} />} <span>{previewBusy ? 'Working…' : previewRunning ? 'Stop Preview' : 'Start Preview'}</span>
              </button>
              {previewRunning && <a className="view-btn" href={projectConfig.preview.url} target="_blank" rel="noreferrer" title="Open the configured app preview">
                <Play size={14} /> <span>Open Preview</span>
              </a>}
            </>
          )}

          <button
            className="view-btn"
            onClick={() => setIsBacklogOpen(true)}
            title="Manage Product Backlog and plan user stories"
            style={{
              padding: '6px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              fontWeight: '600'
            }}
          >
            <ListTodo size={14} color="var(--primary)" />
            <span>Backlog Board</span>
          </button>

          <button
            className="view-btn"
            onClick={() => setIsJournalOpen(true)}
            title="Manage architectural rules & persistent agent memory"
            style={{
              padding: '6px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              fontWeight: '600'
            }}
          >
            <BookMarked size={14} color="#8b5cf6" />
            <span>Project Journal</span>
          </button>

          {sprints.some(s => s.status === 'RUNNING') && (
            <button
              className="view-btn"
              disabled={stoppingSprint}
              onClick={async () => {
                if (window.confirm('พักงานรอบนี้? ระบบจะหยุด agent เก็บไฟล์ และให้ Resume เพื่อทำงานที่ค้างต่อได้')) {
                  setStoppingSprint(true);
                  try {
                    const response = await fetch(`/api/projects/${project.project_id}/sprints/pause`, { method: 'POST' });
                    if (!response.ok) throw new Error('Stop failed');
                    toast.success('ส่งคำสั่งหยุดแล้ว กำลังรอ agent หยุดทำงาน');
                  } catch {
                    toast.error('สั่งหยุดไม่สำเร็จ ลองอีกครั้ง');
                  } finally {
                    setStoppingSprint(false);
                  }
                }
              }}
              title="Stop active sprint and halt agents"
              style={{
                color: '#ef4444',
                borderColor: 'rgba(239, 68, 68, 0.4)',
                background: 'rgba(239, 68, 68, 0.08)',
                padding: '6px 12px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '12px',
                fontWeight: '600'
              }}
            >
              <Square size={13} />
              <span>{stoppingSprint ? 'กำลังสั่งหยุด…' : 'Pause · พักงาน'}</span>
            </button>
          )}
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


      {/* Sprint Pipeline Stepper (UI/UX Pro Max) */}
      <SprintPipelineStepper agents={agents} tasks={tasks} sprints={sprints} events={timelineEvents} />
      <SprintRecoveryPanel sprints={sprints} onResume={onRetrySprint} onStartOver={onRerunSprint} />

      {/* Main Focus Room Layout */}
      <div className="focus-room-layout">
        {/* Left column: Agent roster */}
        <div className="focus-roster-column">
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
                    handleTabSelect('mission-hub');
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
                    {React.createElement(roleMeta.icon || Bot, { size: 14, style: { color: roleMeta.color } })}
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
            display: 'flex', gap: '4px',
            background: 'var(--bg-canvas)', padding: '6px 8px 0 8px',
            borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
            border: '1px solid var(--border-subtle)', borderBottom: 'none',
            alignItems: 'center', overflowX: 'auto'
          }}>
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = currentTab === tab.id;
              return (
                <button
                  key={tab.id}
                  className={`view-btn ${isActive ? 'active' : ''}`}
                  onClick={() => handleTabSelect(tab.id)}
                  style={{
                    fontSize: '12.5px',
                    padding: '7px 16px',
                    fontWeight: isActive ? '700' : '500',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <Icon size={14} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Tab Content */}
          <div style={{
            background: 'var(--bg-surface)',
            borderRadius: '0 0 var(--radius-lg) var(--radius-lg)',
            padding: currentTab === 'skills' ? '20px' : '0',
            border: '1px solid var(--border-subtle)',
            minHeight: '480px',
            flex: 1,
            display: 'flex',
            flexDirection: 'column'
          }}>

            {/* ═══ CONSOLIDATED TAB 1: MISSION HUB (Console + Activity Timeline) ═══ */}
            {currentTab === 'mission-hub' && (
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                {/* Mission Hub Sub-Nav Bar */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 16px',
                  borderBottom: '1px solid var(--border-subtle)',
                  background: 'var(--bg-canvas)',
                  flexWrap: 'wrap', gap: '8px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
                    <MessageSquare size={15} color="var(--primary)" />
                    <span>Live Mission Hub</span>
                    <span style={{
                      fontSize: '10px', padding: '2px 8px', borderRadius: '8px',
                      background: 'var(--primary-subtle)', color: 'var(--primary-text)',
                      fontWeight: '700'
                    }}>
                      Use @Role to whisper specific agents
                    </span>
                  </div>

                  {/* Subview Pill Switcher */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'var(--bg-surface)', padding: '3px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <button
                      type="button"
                      className={`view-btn ${missionSubView === 'chat' ? 'active' : ''}`}
                      onClick={() => setMissionSubView('chat')}
                      style={{ fontSize: '11px', padding: '3px 10px', height: 'auto' }}
                    >
                      💬 Chat Console
                    </button>
                    <button
                      type="button"
                      className={`view-btn ${missionSubView === 'timeline' ? 'active' : ''}`}
                      onClick={() => setMissionSubView('timeline')}
                      style={{ fontSize: '11px', padding: '3px 10px', height: 'auto' }}
                    >
                      ⚡ Activity Feed ({timelineEvents?.length || 0})
                    </button>
                    <button
                      type="button"
                      className={`view-btn ${missionSubView === 'split' ? 'active' : ''}`}
                      onClick={() => setMissionSubView('split')}
                      style={{ fontSize: '11px', padding: '3px 10px', height: 'auto' }}
                    >
                      ◫ Split View
                    </button>
                  </div>
                </div>

                {/* Subview Content */}
                {missionSubView === 'timeline' ? (
                  <ActivityTimeline events={timelineEvents || []} />
                ) : (
                  <div className={missionSubView === 'split' ? 'mission-split-container' : 'mission-flex-container'}>
                    {/* Chat Column */}
                    <div className={`mission-chat-column ${missionSubView === 'split' ? 'is-split' : ''}`}>
                      {/* Message Thread Container */}
                      <div style={{
                        flex: 1,
                        overflowY: 'auto',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                        minHeight: '340px',
                        maxHeight: missionSubView === 'split' ? '460px' : '420px',
                        background: 'var(--bg-primary)'
                      }}>
                        <div style={{ maxWidth: '980px', margin: '0 auto', width: '100%', padding: '20px 16px' }}>
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
                                  if (codeSubView === 'git') fetchGitStatus();
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
                                {React.createElement((ROLE_META[ag.role] || ROLE_META.system).icon || Bot, { size: 14 })}
                              </div>
                              <div style={{ maxWidth: '75%', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                <span style={{ fontSize: '11px', fontWeight: '700', color: (ROLE_META[ag.role] || ROLE_META.system).color }}>
                                  {React.createElement((ROLE_META[ag.role] || ROLE_META.system).icon || Bot, { size: 14 })} {ag.role}
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
                      <div style={{ maxWidth: '980px', margin: '0 auto', width: '100%', padding: '0 16px 12px 16px' }}>
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

                    {/* Split Screen Side Activity Stream */}
                    {missionSubView === 'split' && (
                      <div style={{ maxHeight: '520px', overflowY: 'auto', background: 'var(--bg-canvas)' }}>
                        <ActivityTimeline events={timelineEvents || []} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ═══ CONSOLIDATED TAB 2: CODE & CHANGES (Workspace Files + Git Diff) ═══ */}
            {currentTab === 'code-and-git' && (
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                {/* Code Sub-Nav Bar */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 16px',
                  borderBottom: '1px solid var(--border-subtle)',
                  background: 'var(--bg-canvas)',
                  flexWrap: 'wrap', gap: '8px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
                    <Code2 size={16} color="var(--primary)" />
                    <span>Workspace Code & Version Control</span>
                  </div>

                  {/* Subview Pill Switcher */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'var(--bg-surface)', padding: '3px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <button
                      type="button"
                      className={`view-btn ${codeSubView === 'files' ? 'active' : ''}`}
                      onClick={() => setCodeSubView('files')}
                      style={{ fontSize: '11px', padding: '3px 10px', height: 'auto' }}
                    >
                      📁 Workspace Files & Editor
                    </button>
                    <button
                      type="button"
                      className={`view-btn ${codeSubView === 'git' ? 'active' : ''}`}
                      onClick={() => {
                        setCodeSubView('git');
                        fetchGitStatus();
                      }}
                      style={{ fontSize: '11px', padding: '3px 10px', height: 'auto' }}
                    >
                      🌿 Git Changes {gitData?.files?.length > 0 ? `(${gitData.files.length})` : ''}
                    </button>
                  </div>
                </div>

                {codeSubView === 'files' ? (
                  <WorkspaceFileBrowser projectId={project?.project_id} />
                ) : (
                  <div style={{ padding: '20px' }}>
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

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <a
                          href={`/api/projects/${project.project_id}/git/patch`}
                          download={`${project.project_id}-changes.patch`}
                          className="view-btn"
                          style={{
                            fontSize: '11px', padding: '4px 10px', display: 'flex', alignItems: 'center', gap: '4px',
                            textDecoration: 'none', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)'
                          }}
                          title="Download workspace git changes as a .patch file"
                        >
                          <Download size={12} />
                          <span>Download Patch (.diff)</span>
                        </a>
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
                    </div>

                    {/* Git Remote & Branch Control Bar */}
                    {gitData?.has_git && (
                      <div className="git-remote-bar">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: '700', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <GitBranch size={13} color="var(--primary)" />
                            <span>Branch:</span>
                          </span>
                          <select
                            value={gitData.branch || 'main'}
                            onChange={(e) => handleCheckoutBranch(e.target.value)}
                            disabled={gitActionLoading}
                            style={{
                              background: 'var(--bg-canvas)',
                              color: 'var(--text-primary)',
                              border: '1px solid var(--border-subtle)',
                              borderRadius: 'var(--radius-sm)',
                              padding: '2px 8px',
                              fontSize: '11.5px',
                              fontWeight: '600'
                            }}
                          >
                            {gitBranches.length > 0 ? (
                              gitBranches.map(b => (
                                <option key={b.name} value={b.name}>{b.name}{b.current ? ' (current)' : ''}</option>
                              ))
                            ) : (
                              <option value={gitData.branch || 'main'}>{gitData.branch || 'main'}</option>
                            )}
                          </select>

                          <button
                            type="button"
                            onClick={handleCreateBranch}
                            disabled={gitActionLoading}
                            className="view-btn"
                            style={{ fontSize: '11px', padding: '2px 8px', height: 'auto' }}
                            title="Create and checkout a new branch"
                          >
                            + New Branch
                          </button>

                          <span style={{ color: 'var(--border-medium)', margin: '0 4px' }}>|</span>

                          <span style={{ color: 'var(--text-muted)' }}>Remote:</span>
                          {gitRemotes.origin ? (
                            <span className="git-remote-url" title={gitRemotes.origin}>
                              origin ({gitRemotes.origin.length > 30 ? gitRemotes.origin.substring(0, 30) + '...' : gitRemotes.origin})
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '11px' }}>
                              No remote origin
                            </span>
                          )}

                          {isSettingRemote ? (
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                              <input
                                type="text"
                                placeholder="https://github.com/org/repo.git"
                                value={remoteUrlInput}
                                onChange={(e) => setRemoteUrlInput(e.target.value)}
                                style={{
                                  padding: '2px 6px', fontSize: '11px', background: 'var(--bg-canvas)',
                                  border: '1px solid var(--border-medium)', borderRadius: '4px', color: 'var(--text-primary)'
                                }}
                              />
                              <button
                                type="button"
                                onClick={handleSetRemote}
                                disabled={gitActionLoading}
                                className="view-btn active"
                                style={{ fontSize: '10.5px', padding: '2px 6px', height: 'auto' }}
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                onClick={() => setIsSettingRemote(false)}
                                className="view-btn"
                                style={{ fontSize: '10.5px', padding: '2px 6px', height: 'auto' }}
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => {
                                setRemoteUrlInput(gitRemotes.origin || '');
                                setIsSettingRemote(true);
                              }}
                              className="view-btn"
                              style={{ fontSize: '10.5px', padding: '2px 6px', height: 'auto' }}
                            >
                              {gitRemotes.origin ? 'Edit' : '+ Set Remote'}
                            </button>
                          )}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          {gitToast && (
                            <span style={{ fontSize: '11px', color: 'var(--success-text)', fontWeight: '600' }}>
                              ✓ {gitToast}
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={handlePullGit}
                            disabled={gitActionLoading || !gitRemotes.origin}
                            className="view-btn"
                            style={{ fontSize: '11px', padding: '3px 8px', height: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}
                            title="Pull latest commits from remote origin"
                          >
                            <DownloadCloud size={12} />
                            <span>Pull</span>
                          </button>
                          <button
                            type="button"
                            onClick={handlePushGit}
                            disabled={gitActionLoading || !gitRemotes.origin}
                            className="git-push-btn"
                            title="Push commits to remote origin"
                          >
                            {gitActionLoading ? <Loader2 size={12} className="spin" /> : <UploadCloud size={12} />}
                            <span>Push</span>
                          </button>
                        </div>
                      </div>
                    )}

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
              </div>
            )}

            {/* ═══ CONSOLIDATED TAB 3: SPRINTS & QA (Sprint History + Terminal & Tests) ═══ */}
            {currentTab === 'sprints-qa' && (
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                {/* Sprints Sub-Nav Bar */}
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 16px',
                  borderBottom: '1px solid var(--border-subtle)',
                  background: 'var(--bg-canvas)',
                  flexWrap: 'wrap', gap: '8px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', fontWeight: '600', fontSize: '13px' }}>
                    <History size={16} color="#d97706" />
                    <span>Sprint Operations & Quality Assurance</span>
                  </div>

                  {/* Subview Pill Switcher */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'var(--bg-surface)', padding: '3px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <button
                      type="button"
                      className={`view-btn ${sprintSubView === 'history' ? 'active' : ''}`}
                      onClick={() => setSprintSubView('history')}
                      style={{ fontSize: '11px', padding: '3px 10px', height: 'auto' }}
                    >
                      🏃 Sprint History ({sprints?.length || 0})
                    </button>
                    <button
                      type="button"
                      className={`view-btn ${sprintSubView === 'tests' ? 'active' : ''}`}
                      onClick={() => setSprintSubView('tests')}
                      style={{ fontSize: '11px', padding: '3px 10px', height: 'auto' }}
                    >
                      🧪 Automated Tests & Terminal
                    </button>
                  </div>
                </div>

                {sprintSubView === 'history' ? (
                  <SprintHistoryPanel sprints={sprints || []} onRerun={onRerunSprint} onRetry={onRetrySprint} />
                ) : (
                  <div style={{ padding: '20px', flex: 1, display: 'flex', flexDirection: 'column' }}>
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
              </div>
            )}

            {/* ═══ CONSOLIDATED TAB 4: TEAM & SKILLS ═══ */}
            {currentTab === 'skills' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h4 style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary)', margin: 0 }}>
                      Agent Playbooks & Operational Skills (SKILL.md)
                    </h4>
                    <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                      Core Role + Project Rules + Selected Skills + Project Context
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

                <div style={{ display: 'grid', gridTemplateColumns: '220px minmax(0, 1fr)', gap: '14px', minHeight: '380px' }}>
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
                          disabled={savingSkill || identitySaving || promptBusy}
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
                            <span style={{ fontSize: '12px', fontWeight: '700' }}>{ag.display_name || ag.role}</span>
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
                    ) : skillDetail?.role === selectedSkillRole ? (
                      <>
                        {(() => {
                          const selectedAgent = projectSkills.find(ag => ag.role === selectedSkillRole) || agents.find(ag => ag.role === selectedSkillRole);
                          const isAuto = selectedAgent?.skill_mode === 'AUTO';
                          const equipped = selectedAgent?.equipped_skills || [];
                          
                          return (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                              <section aria-label="Agent identity">
                                <h3 style={{ fontSize: '15px', margin: '0 0 8px' }}>ตัวตนของ Agent</h3>
                                    {skillDetail.persona_source === 'legacy_title' && <p style={{ fontSize: '12px', whiteSpace: 'normal', overflowWrap: 'anywhere' }}>Persona เดิมถูกสถานะเขียนทับ ระบบใช้ชื่อเดิมเป็นค่าเริ่มต้น<br />กรุณาระบุความเชี่ยวชาญอีกครั้งก่อนสั่งงาน</p>}
                                <label style={{ display: 'block' }}>ชื่อที่แสดง
                                  <input value={identityName} maxLength={120} onChange={event => setIdentityName(event.target.value)} style={{ width: '100%', padding: '8px', background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-medium)' }} />
                                </label>
                                <label style={{ display: 'block', marginTop: '8px' }}>Persona / ความเชี่ยวชาญถาวร
                                  <textarea value={personaText} maxLength={4000} onChange={event => setPersonaText(event.target.value)} rows={3} style={{ width: '100%', padding: '8px', background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-medium)' }} />
                                </label>
                                <button className="view-btn active" onClick={handleSaveIdentity} disabled={identitySaving || !identityName.trim() || !personaText.trim()}>{identitySaving ? 'กำลังบันทึก…' : 'บันทึกตัวตน'}</button>
                              </section>
                              <section aria-label="Prompt preview">
                                <h3 style={{ fontSize: '15px', margin: '0 0 8px' }}>ดู Prompt ก่อนเรียก AI</h3>
                                <p style={{ fontSize: '12px' }}>ใช้ค่าที่บันทึกแล้วและบริบทโปรเจกต์ปัจจุบัน ผลงานระหว่าง Sprint จะเพิ่มตอนทำงานจริง การดู preview ไม่เรียก AI</p>
                                <label>คำสั่งตัวอย่าง
                                  <textarea value={previewMessage} maxLength={16000} onChange={event => setPreviewMessage(event.target.value)} rows={2} style={{ width: '100%', padding: '8px', background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-medium)' }} />
                                </label>
                                <label>โหมด <select value={promptMode} onChange={event => setPromptMode(event.target.value)} style={{ padding: '6px', background: 'var(--bg-input)', color: 'var(--text-primary)', border: '1px solid var(--border-medium)' }}>
                                  <option value="">ตามบทบาทใน Pipeline</option>
                                  <option value="consultation">คุยปรึกษา</option>
                                </select></label>
                                <button className="view-btn active" onClick={handlePromptPreview} disabled={promptBusy}>{promptBusy ? 'กำลังโหลด…' : 'ดู Prompt และแหล่งข้อมูล'}</button>
                                <button className="view-btn" onClick={handlePromptTraces} disabled={promptBusy}>ดูประวัติ Prompt ที่ประกอบตอนทำงาน</button>
                                {promptTraces && <details open>
                                  <summary>ประวัติ {promptTraces.length} ครั้งล่าสุด — เก็บแหล่งไฟล์และ hash โดยไม่เก็บข้อความ prompt</summary>
                                  {promptTraces.length === 0 ? <p>ยังไม่มีประวัติหลังอัปเดตระบบ</p> : promptTraces.map(item => <div key={item.trace_id}>
                                    <p>{new Date(item.created_at * 1000).toLocaleString()} · {item.trace.execution_mode}</p>
                                    <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(item.trace, null, 2)}</pre>
                                  </div>)}
                                </details>}
                                {promptPreview && <div>
                                  <p>โหมด: {promptPreview.trace.execution_mode} · {promptPreview.trace.characters.toLocaleString()} ตัวอักษร · Skills ที่เข้า prompt: {promptPreview.trace.operational_skills.join(', ') || 'ไม่มี skill เพิ่มเติม'}</p>
                                  {Object.entries(promptPreview.trace.selection_reasons || {}).map(([name, reason]) => <p key={name}>{name}: {reason}</p>)}
                                  {promptPreview.trace.warnings.map(message => <p key={message} role="alert">{message}</p>)}
                                  {promptPreview.trace.truncated_sections.length > 0 && <p>ส่วนที่ใช้ excerpt: {promptPreview.trace.truncated_sections.join(', ')}</p>}
                                  <details><summary>ไฟล์และเวอร์ชันที่โหลด</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(promptPreview.trace.sources, null, 2)}</pre></details>
                                  <details><summary>System Prompt</summary><pre style={{ whiteSpace: 'pre-wrap', maxHeight: '350px', overflow: 'auto' }}>{promptPreview.system_prompt}</pre></details>
                                </div>}
                              </section>
                              
                              {/* Performance Metrics Bar */}
                              <div style={{
                                background: 'var(--bg-surface-elevated)',
                                padding: '10px 14px',
                                borderRadius: '8px',
                                border: '1px solid var(--border-subtle)',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                flexWrap: 'wrap',
                                gap: '10px'
                              }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                  <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                                    Analytics ({selectedSkillRole}):
                                  </span>
                                  <span className="agent-metrics-pill">
                                    ⚡ <strong>{agentMetrics[selectedSkillRole]?.total_actions || 0}</strong> tasks
                                  </span>
                                  <span className="agent-metrics-pill">
                                    🪙 <strong>{(agentMetrics[selectedSkillRole]?.total_tokens || 0).toLocaleString()}</strong> tok
                                  </span>
                                  <span className="agent-metrics-pill">
                                    ⏱ <strong>{(agentMetrics[selectedSkillRole]?.avg_duration_seconds || 0).toFixed(1)}s</strong> avg
                                  </span>
                                  <span className="agent-metrics-pill" style={{ color: 'var(--success-text)' }}>
                                    🎯 <strong>{agentMetrics[selectedSkillRole]?.success_rate ?? 100}%</strong> success
                                  </span>
                                </div>

                                <button
                                  type="button"
                                  onClick={() => {
                                    setShowActivityLog(!showActivityLog);
                                    if (!showActivityLog) fetchRecentActivities(selectedSkillRole);
                                  }}
                                  className="view-btn"
                                  style={{ fontSize: '11px', padding: '3px 8px', height: 'auto' }}
                                >
                                  {showActivityLog ? 'Hide Activities' : `Recent Logs (${recentActivities.length})`}
                                </button>
                              </div>

                              {showActivityLog && (
                                <div style={{
                                  background: 'var(--bg-surface)',
                                  border: '1px solid var(--border-subtle)',
                                  borderRadius: '8px',
                                  padding: '10px',
                                  maxHeight: '160px',
                                  overflowY: 'auto',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  gap: '6px'
                                }}>
                                  <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-secondary)' }}>
                                    Recent Execution Log for {selectedSkillRole}:
                                  </span>
                                  {recentActivities.length === 0 ? (
                                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                      No recorded task executions yet for this role.
                                    </span>
                                  ) : (
                                    recentActivities.map(act => (
                                      <div key={act.activity_id} style={{
                                        fontSize: '11px',
                                        padding: '4px 8px',
                                        background: 'var(--bg-canvas)',
                                        borderRadius: '4px',
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                        gap: '8px'
                                      }}>
                                        <span style={{ color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                                          {act.task_title || act.action_type}
                                        </span>
                                        <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '10px' }}>
                                          {act.tokens_used} tok • {act.duration_seconds.toFixed(1)}s
                                        </span>
                                        <span style={{
                                          fontSize: '9px', fontWeight: '700', padding: '1px 4px', borderRadius: '3px',
                                          background: act.status === 'SUCCESS' ? 'var(--success-subtle)' : 'rgba(239, 68, 68, 0.15)',
                                          color: act.status === 'SUCCESS' ? 'var(--success-text)' : 'var(--accent-coral)'
                                        }}>
                                          {act.status}
                                        </span>
                                      </div>
                                    ))
                                  )}
                                </div>
                              )}

                              {/* Equipped Skills Section */}
                              <div style={{ background: 'var(--bg-input)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Sparkles size={14} color="var(--primary)" />
                                    <span style={{ fontSize: '13px', fontWeight: '700', color: 'var(--text-primary)' }}>{isAuto ? 'Skills ที่ปักไว้ + เลือกจากคลังตามงาน' : 'Skills ที่เลือกเอง'}</span>
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
                                      {skillDetail.project_rules_applied ? 'PROJECT RULES' : 'CORE REFERENCE'}
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
                                      <Edit3 size={13} /><span>แก้ Project Rules</span>
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
                              <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Project Rules ใช้ทุกครั้งในทั้ง Auto และ Manual โดยเพิ่มกฎของโปรเจกต์จาก core ด้านล่าง ภายใต้ข้อจำกัดของโหมดทำงาน</p>
                              <details>
                                <summary>Core Role ถาวร: {skillDetail.core_role_playbook?.title}</summary>
                                <pre style={{ whiteSpace: 'pre-wrap', maxHeight: '250px', overflow: 'auto' }}>{skillDetail.core_role_playbook?.instructions}</pre>
                              </details>
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

      {/* Product Backlog Board Modal */}
      <BacklogBoardModal
        isOpen={isBacklogOpen}
        onClose={() => setIsBacklogOpen(false)}
        projectId={project?.project_id}
        projectName={project?.name}
      />

      {/* Project Journal & Memory Modal */}
      <ProjectJournalModal
        isOpen={isJournalOpen}
        onClose={() => setIsJournalOpen(false)}
        projectId={project?.project_id}
        projectName={project?.name}
      />
    </div>
  );
}
