import React, { useState, useEffect, useRef, lazy, Suspense } from 'react';
import { 
  Building2, 
  Columns, 
  Focus, 
  Sun, 
  Moon, 
  Layers,
  Plus,
  ListOrdered,
  X,
  Loader2,
  Bell
} from 'lucide-react';
import PMCommandBar from './components/PMCommandBar';
import OfficeFloorView from './components/OfficeFloorView';
import DualSplitView from './components/DualSplitView';
const FocusRoomView = lazy(() => import('./components/FocusRoomView'));
import { DecisionGateModal } from './components/DecisionGateModal';
import AddProjectModal from './components/AddProjectModal';
import TechLeadStandupModal from './components/TechLeadStandupModal';
import DeleteProjectModal from './components/DeleteProjectModal';
import AddAgentModal from './components/AddAgentModal';
import AutoGenerateTeamModal from './components/AutoGenerateTeamModal';
import QuickWhisperDrawer from './components/QuickWhisperDrawer';
import BacklogBoardModal from './components/BacklogBoardModal';
import ProjectJournalModal from './components/ProjectJournalModal';
import SprintCompletionModal from './components/SprintCompletionModal';
import { ToastProvider, useToast } from './components/Toast';

export default function App() {
  return (
    <ToastProvider>
      <AppContent />
    </ToastProvider>
  );
}

function AppContent() {
  const toast = useToast();
  const parseRoute = () => {
    const hash = window.location.hash.replace(/^#\/?/, '');
    const parts = hash.split('/').filter(Boolean);
    if (parts[0] === 'project' && parts[1]) {
      return {
        viewMode: 'FOCUS',
        projectId: parts[1],
        tab: parts[2] || 'mission-hub'
      };
    }
    if (parts[0] === 'split') {
      return {
        viewMode: 'SPLIT',
        projectId: null,
        tab: 'mission-hub'
      };
    }
    if (parts[0] === 'queue') {
      return {
        viewMode: 'OFFICE',
        projectId: null,
        tab: 'mission-hub',
        openQueue: true
      };
    }
    if (parts[0] === 'office') {
      return {
        viewMode: 'OFFICE',
        projectId: null,
        tab: 'mission-hub'
      };
    }

    // Fallback to localStorage if no specific route is given in hash
    try {
      const saved = localStorage.getItem('agent_pm_last_route');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.viewMode) {
          return parsed;
        }
      }
    } catch (e) {
      console.warn('Failed to parse last route:', e);
    }

    return {
      viewMode: 'OFFICE',
      projectId: null,
      tab: 'mission-hub'
    };
  };

  const initialRoute = parseRoute();
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'dark';
  });
  const [viewMode, setViewMode] = useState(initialRoute.viewMode);
  const [projects, setProjects] = useState([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [activeProjectId, setActiveProjectId] = useState(initialRoute.projectId);
  const [focusedProjectId, setFocusedProjectId] = useState(initialRoute.projectId);
  const [activeTabFromRoute, setActiveTabFromRoute] = useState(initialRoute.tab);
  const [activeWhisperAgent, setActiveWhisperAgent] = useState(null); // { project, agent }

  const [agentStates, setAgentStates] = useState({}); // { [projId]: [AgentState] }
  const [tasksByProject, setTasksByProject] = useState({}); // { [projId]: [TaskItem] }
  const [liveStreams, setLiveStreams] = useState({}); // { [projId]: [logs] }
  const [consoleHistories, setConsoleHistories] = useState({}); // { [projId]: [ConsoleMessage] }
  const [timelineEvents, setTimelineEvents] = useState({}); // { [projId]: [event] }
  const [sprintsByProject, setSprintsByProject] = useState({}); // { [projId]: [SprintRecord] }

  const [activeApproval, setActiveApproval] = useState(null);
  const [standupProject, setStandupProject] = useState(null); // { projectId, projectName }
  const [isAddProjectOpen, setIsAddProjectOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState(null);
  const [addAgentProject, setAddAgentProject] = useState(null);
  const [autoGenProject, setAutoGenProject] = useState(null);
  const [backlogProject, setBacklogProject] = useState(null); // { projectId, projectName }
  const [journalProject, setJournalProject] = useState(null); // { projectId, projectName }
  const [completedSprint, setCompletedSprint] = useState(null); // { sprint data for modal }
  const [runtime, setRuntime] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [globalQueue, setGlobalQueue] = useState([]);
  const [isQueueDrawerOpen, setIsQueueDrawerOpen] = useState(Boolean(initialRoute.openQueue));
  const [notificationsEnabled, setNotificationsEnabled] = useState(() => localStorage.getItem('agent_pm_notifications') === 'on');

  const socketRef = useRef(null);
  const notificationsRef = useRef(notificationsEnabled);

  useEffect(() => { notificationsRef.current = notificationsEnabled; }, [notificationsEnabled]);

  const toggleNotifications = async () => {
    if (!notificationsEnabled && 'Notification' in window) {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') return toast.error('เบราว์เซอร์ยังไม่อนุญาตการแจ้งเตือน');
    }
    const next = !notificationsEnabled;
    setNotificationsEnabled(next);
    localStorage.setItem('agent_pm_notifications', next ? 'on' : 'off');
  };

  // Sync route on hashchange (Browser Back/Forward or manual URL edit)
  useEffect(() => {
    const handleHashChange = () => {
      const r = parseRoute();
      setViewMode(r.viewMode);
      setFocusedProjectId(r.projectId);
      if (r.projectId) {
        setActiveProjectId(r.projectId);
      }
      if (r.tab) {
        setActiveTabFromRoute(r.tab);
      }
      if (r.openQueue) {
        setIsQueueDrawerOpen(true);
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Sync theme with DOM and localStorage
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const requestJson = async (url, options) => {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${res.status})`);
    return data;
  };

  const fetchRuntime = async () => {
    try { setRuntime(await requestJson('/api/runtime')); }
    catch (error) { setRuntime({ available: false, mode: 'offline', message: `เชื่อมต่อ backend ไม่สำเร็จ: ${error.message}` }); }
  };

  // Fetch projects and initial data
  const fetchData = async () => {
    try {
      const data = await requestJson('/api/projects');
      setLoadError(null);
      
      setProjects(data);
      setIsLoadingProjects(false);

      const route = parseRoute();
      if (route.projectId && data.some(p => p.project_id === route.projectId)) {
        setActiveProjectId(route.projectId);
        setFocusedProjectId(route.projectId);
        setViewMode('FOCUS');
        if (route.tab) setActiveTabFromRoute(route.tab);
        window.location.hash = `#/project/${route.projectId}/${route.tab || 'mission-hub'}`;
        try {
          localStorage.setItem('agent_pm_last_route', JSON.stringify({
            viewMode: 'FOCUS',
            projectId: route.projectId,
            tab: route.tab || 'mission-hub'
          }));
        } catch (e) {}
      } else if (route.viewMode === 'SPLIT') {
        setViewMode('SPLIT');
        window.location.hash = '#/split';
        if (data.length > 0 && !activeProjectId) {
          setActiveProjectId(data[0].project_id);
        }
      } else {
        if (route.projectId && !data.some(p => p.project_id === route.projectId)) {
          toast.info('Project not found, showing Office Floor');
        }
        setViewMode('OFFICE');
        window.location.hash = '#/office';
        if (data.length > 0 && (!activeProjectId || !data.some(p => p.project_id === activeProjectId))) {
          setActiveProjectId(data[0].project_id);
        }
        try {
          localStorage.setItem('agent_pm_last_route', JSON.stringify({
            viewMode: 'OFFICE',
            projectId: null,
            tab: 'mission-hub'
          }));
        } catch (e) {}
      }

      // Fetch agents, tasks, console history, and sprints for each project
      for (const p of data) {
        fetchProjectDetails(p.project_id);
        fetchConsoleHistory(p.project_id);
        fetchSprints(p.project_id);
      }
      fetchGlobalQueue();
    } catch (err) {
      setIsLoadingProjects(false);
      setLoadError(err.message);
      console.error('Error fetching initial data:', err);
    }
  };

  const fetchGlobalQueue = async () => {
    try {
      setGlobalQueue(await requestJson('/api/queue/all'));
    } catch (e) {
      toast.error(`โหลดคิวไม่สำเร็จ: ${e.message}`);
      console.error('Error loading global queue:', e);
    }
  };

  const handleCancelQueueItem = async (queueId) => {
    try {
      await requestJson(`/api/queue/${queueId}`, { method: 'DELETE' });
      await fetchGlobalQueue();
    } catch (e) {
      toast.error(`ยกเลิกคิวไม่สำเร็จ: ${e.message}`);
      console.error('Error cancelling queue item:', e);
    }
  };

  const handleSetQueuePriority = async (queueId, priority) => {
    try {
      await requestJson(`/api/queue/${queueId}/priority`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ priority })
      });
      await fetchGlobalQueue();
    } catch (e) {
      toast.error(`เปลี่ยน priority ไม่สำเร็จ: ${e.message}`);
      console.error('Error updating queue priority:', e);
    }
  };

  const handleReorderQueueItem = async (queueId, direction) => {
    try {
      await requestJson(`/api/queue/${queueId}/reorder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ direction })
      });
      await fetchGlobalQueue();
    } catch (e) {
      toast.error(`จัดลำดับคิวไม่สำเร็จ: ${e.message}`);
      console.error('Error reordering queue item:', e);
    }
  };

  const fetchSprints = async (projId) => {
    try {
      const sprints = await requestJson(`/api/projects/${projId}/sprints`);
      setSprintsByProject((prev) => ({ ...prev, [projId]: sprints }));
    } catch (e) {
      console.error(`Error loading sprints for ${projId}:`, e);
    }
  };

  const fetchProjectDetails = async (projId) => {
    try {
      const [agents, tasks, approvals] = await Promise.all([
        requestJson(`/api/projects/${projId}/agents`),
        requestJson(`/api/projects/${projId}/tasks`),
        requestJson(`/api/projects/${projId}/approvals`)
      ]);

      setAgentStates((prev) => ({ ...prev, [projId]: agents }));
      setTasksByProject((prev) => ({ ...prev, [projId]: tasks }));
      setActiveApproval((current) => {
        if (approvals?.length) return current && current.project_id !== projId ? current : approvals[0];
        return current?.project_id === projId ? null : current;
      });
    } catch (e) {
      console.error(`Error loading details for ${projId}:`, e);
    }
  };

  const fetchConsoleHistory = async (projId) => {
    try {
      const history = await requestJson(`/api/projects/${projId}/console/history`);
      setConsoleHistories((prev) => ({ ...prev, [projId]: history }));
    } catch (e) {
      console.error(`Error loading console history for ${projId}:`, e);
    }
  };

  // Setup WebSocket connection
  useEffect(() => {
    fetchData();
    fetchRuntime();
    let disposed = false;
    let reconnectTimer;
    let hasConnected = false;
    let lastSequence = 0;

    const connectWs = () => {
      if (disposed) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/live${lastSequence ? `?after=${lastSequence}` : ''}`;
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        if (hasConnected) fetchData();
        hasConnected = true;
        fetchRuntime();
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.sequence && parsed.sequence <= lastSequence) return;
          if (parsed.sequence) lastSequence = parsed.sequence;
          const evType = parsed.event;
          const data = parsed.data;
          const projId = data.project_id;
          if (!parsed.replayed && notificationsRef.current && document.hidden && 'Notification' in window && Notification.permission === 'granted') {
            if (evType === 'DECISION_GATE_OPEN') new Notification('Agent PM รอการตัดสินใจ', { body: data.summary || 'มีแผนงานรออนุมัติ' });
            if (evType === 'PIPELINE_COMPLETED') new Notification('Sprint เสร็จแล้ว', { body: data.directive || data.summary || '' });
            if (['PIPELINE_HALTED', 'PIPELINE_REJECTED'].includes(evType)) new Notification('Sprint หยุดทำงาน', { body: data.summary || '' });
          }

          // Append to live stream
          if (projId) {
            setLiveStreams((prev) => ({
              ...prev,
              [projId]: [...(prev[projId] || []).slice(-299), data]
            }));
          }

          // Append to timeline events
          if (projId) {
            setTimelineEvents((prev) => ({
              ...prev,
              [projId]: [
                ...(prev[projId] || []).slice(-199),
                { type: evType, data, timestamp: data.timestamp || Date.now() / 1000 }
              ]
            }));
          }

          // Replayed events rebuild history. Current REST snapshots own state;
          // do not re-open an old approval or completion dialog during replay.
          if (parsed.replayed) return;
          // Handle state updates
          if (['AGENT_STATE_UPDATE', 'AGENT_STATUS_CHANGE', 'AGENT_THOUGHT_DELTA', 'AGENT_PROGRESS'].includes(evType)) {
            setAgentStates(prev => {
              const agents = [...(prev[projId] || [])];
              const index = agents.findIndex(agent => agent.role === data.role);
              const patch = { ...data, thought: data.thought || data.message };
              Object.keys(patch).forEach(key => patch[key] === undefined && delete patch[key]);
              if (index >= 0) agents[index] = { ...agents[index], ...patch };
              else if (data.role) agents.push({ status: 'IDLE', ...patch });
              return { ...prev, [projId]: agents };
            });
            if (evType === 'AGENT_STATE_UPDATE') {
              requestJson(`/api/projects/${projId}/tasks`).then(tasks => {
                if (Array.isArray(tasks)) setTasksByProject(prev => ({ ...prev, [projId]: tasks }));
              }).catch(console.error);
            }
          } else if (['AGENT_ROSTER_UPDATED', 'AGENT_DELETED'].includes(evType)) {
            fetchProjectDetails(projId);
          } else if (evType === 'TASKS_UPDATED') {
            requestJson(`/api/projects/${projId}/tasks`)
              .then((tasks) => {
                setTasksByProject((prev) => ({ ...prev, [projId]: tasks }));
              });
          } else if (evType === 'DECISION_GATE_OPEN') {
            setActiveApproval(data);
          } else if (evType === 'DECISION_GATE_RESOLVED') {
            setActiveApproval(current => current?.request_id === data.request_id ? null : current);
          } else if (evType === 'PROJECT_DELETED') {
            fetchData();
          } else if (evType === 'PIPELINE_COMPLETED') {
            fetchRuntime();
            if (projId) {
              fetchSprints(projId);
              fetchProjectDetails(projId);
              // Show sprint completion modal with release summary
              setCompletedSprint({
                sprint_id: data.sprint_id,
                project_id: projId,
                directive: data.directive,
                release_summary: data.summary,
                total_tokens: data.total_tokens,
                tasks_count: data.tasks_count,
                started_at: null,
                completed_at: Date.now() / 1000
              });
            }
          } else if (['SPRINT_STARTED', 'PIPELINE_REJECTED', 'PIPELINE_HALTED'].includes(evType)) {
            if (projId) {
              fetchRuntime();
              fetchSprints(projId);
              fetchProjectDetails(projId);
              if (evType !== 'SPRINT_STARTED') toast.error(data.summary || 'Sprint stopped');
            }
          } else if (['QUEUE_UPDATED', 'QUEUE_ITEM_STARTED', 'QUEUE_ITEM_FINISHED', 'DIRECTIVE_STARTED'].includes(evType)) {
            fetchGlobalQueue();
          } else if (evType === 'CONSOLE_MESSAGE') {
            // Append console message to the correct project's history
            if (projId) {
              setConsoleHistories((prev) => ({
                ...prev,
                [projId]: [...(prev[projId] || []).filter(msg => !data.message_id || msg.message_id !== data.message_id).slice(-199), data]
              }));
            }
          }
        } catch (e) {
          console.error('WS parse error:', e);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        if (!disposed) reconnectTimer = setTimeout(connectWs, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connectWs();

    return () => {
      disposed = true;
      clearTimeout(reconnectTimer);
      if (socketRef.current) { socketRef.current.onclose = null; socketRef.current.close(); }
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isQueueDrawerOpen) {
        setIsQueueDrawerOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isQueueDrawerOpen]);

  const handleDispatchDirective = async (projectId, directive, options = {}) => {
    const result = await requestJson(`/api/projects/${projectId}/directive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ directive, ...options })
    });
    fetchProjectDetails(projectId);
    fetchGlobalQueue();
    handleFocusProject(projectId);
    toast.success('รับคำสั่งเข้าคิวแล้ว ติดตามขั้นตอนและผลลัพธ์ในแชตนี้');
    return result;
  };

  const handleResolveApproval = async (requestId, decision, feedback = '') => {
    if (!activeApproval) return;
    await requestJson(`/api/projects/${activeApproval.project_id}/approvals/${requestId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision, feedback })
    });
    setActiveApproval(null);
    fetchData();
  };

  const handleSendWhisper = async (projectId, role, message) => {
    return await requestJson(`/api/projects/${projectId}/whisper`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, message })
    });
  };

  const handleSendConsoleMessage = async (projectId, message, attachments = [], isDirective = false) => {
    await requestJson(`/api/projects/${projectId}/console/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, attachments, is_directive: isDirective })
    });
  };

  const handleAddProject = async (projectData) => {
    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(projectData)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not add project');
    }
    const created = await res.json();
    await fetchData();
    setActiveProjectId(created.project_id);
  };

  const handleDeleteProject = async (projectId) => {
    setProjectToDelete(null);
    try {
      // 1. Optimistically remove project from state immediately
      setProjects((prev) => prev.filter((p) => p.project_id !== projectId));
      setAgentStates((prev) => {
        const next = { ...prev };
        delete next[projectId];
        return next;
      });
      setTasksByProject((prev) => {
        const next = { ...prev };
        delete next[projectId];
        return next;
      });
      if (activeProjectId === projectId) {
        setActiveProjectId(null);
      }
      if (focusedProjectId === projectId) {
        setViewMode('OFFICE');
        setFocusedProjectId(null);
      }

      // 2. Perform backend deletion
      const res = await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json();
        console.error('Failed to delete project on backend:', err);
      }
      // 3. Re-sync from server
      await fetchData();
    } catch (err) {
      console.error('Delete project failed:', err);
    }
  };

  const handleAddCustomAgent = async (agentData) => {
    if (!addAgentProject) return;
    const res = await fetch(`/api/projects/${addAgentProject.project_id}/agents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(agentData)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Could not recruit specialist');
    }
    await fetchProjectDetails(addAgentProject.project_id);
  };

  const handleDeleteCustomAgent = async (projectId, role) => {
    try {
      const res = await fetch(`/api/projects/${projectId}/agents/${role}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        toast.success(`Removed ${role} from team`);
        await fetchProjectDetails(projectId);
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to remove agent');
      }
    } catch (e) {
      toast.error(`Error deleting agent: ${e.message}`);
      console.error('Failed to delete agent:', e);
    }
  };

  const handleApplyGeneratedTeam = async (genResult) => {
    if (genResult && genResult.project_id) {
      await fetchProjectDetails(genResult.project_id);
    }
  };

  const handleFocusProject = (projectId, tab = 'mission-hub') => {
    setFocusedProjectId(projectId);
    setActiveProjectId(projectId);
    setViewMode('FOCUS');
    setActiveTabFromRoute(tab);
    window.location.hash = `#/project/${projectId}/${tab}`;
    try {
      localStorage.setItem('agent_pm_last_route', JSON.stringify({
        viewMode: 'FOCUS',
        projectId,
        tab
      }));
    } catch (e) {}
  };

  const handleBackToOverview = () => {
    setViewMode('OFFICE');
    setFocusedProjectId(null);
    window.location.hash = '#/office';
    try {
      localStorage.setItem('agent_pm_last_route', JSON.stringify({
        viewMode: 'OFFICE',
        projectId: null,
        tab: 'mission-hub'
      }));
    } catch (e) {}
  };

  const handleSwitchToSplit = () => {
    setViewMode('SPLIT');
    setFocusedProjectId(null);
    window.location.hash = '#/split';
    try {
      localStorage.setItem('agent_pm_last_route', JSON.stringify({
        viewMode: 'SPLIT',
        projectId: null,
        tab: 'mission-hub'
      }));
    } catch (e) {}
  };

  const handleRerunSprint = (directive) => {
    if (focusedProjectId) {
      handleDispatchDirective(focusedProjectId, directive);
    }
  };

  const handleRetrySprint = async (sprint, stage = 'QA') => {
    try {
      await requestJson(`/api/projects/${sprint.project_id}/sprints/${sprint.sprint_id}/retry`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stage })
      });
      fetchGlobalQueue();
      toast.success(`นำ checkpoint กลับเข้าคิว เริ่มต่อจาก ${stage}`);
      return true;
    } catch (error) {
      toast.error(error.message || 'สั่ง Resume ไม่สำเร็จ');
      return false;
    }
  };

  const focusedProject = projects.find((p) => p.project_id === focusedProjectId);

  // Compute session token usage and estimated cost for active project
  const currentSprints = sprintsByProject[activeProjectId] || [];
  const sessionTokens = currentSprints.reduce((acc, sp) => acc + (sp.total_tokens || 0), 0);
  const costUSD = (sessionTokens * 0.000001).toFixed(3);
  const sprintCost = { tokens: sessionTokens, costUSD };

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <div className="brand-logo" onClick={handleBackToOverview} style={{ cursor: 'pointer' }} title="Go to Office Floor">
          <div className="brand-icon">
            <Layers size={20} />
          </div>
          <div>
            <h1 className="brand-title">Antigravity PM Workspace</h1>
            <div className="brand-subtitle">MULTI-AGENT ORCHESTRATION</div>
          </div>
        </div>

        {/* Navigation & Controls */}
        <div className="header-actions">
          {/* View Switcher */}
          <div className="view-switcher">
            <button
              className={`view-btn ${viewMode === 'OFFICE' ? 'active' : ''}`}
              onClick={handleBackToOverview}
            >
              <Building2 size={14} />
              <span>Office Floor</span>
            </button>
            <button
              className={`view-btn ${viewMode === 'SPLIT' ? 'active' : ''}`}
              onClick={handleSwitchToSplit}
            >
              <Columns size={14} />
              <span>Dual Split</span>
            </button>
            {focusedProject && (
              <button
                className={`view-btn ${viewMode === 'FOCUS' ? 'active' : ''}`}
                onClick={() => handleFocusProject(focusedProject.project_id, activeTabFromRoute)}
              >
                <Focus size={14} />
                <span>{focusedProject.name}</span>
              </button>
            )}
          </div>

          {/* Add Project Button */}
          <button
            className="view-btn"
            onClick={() => setIsAddProjectOpen(true)}
            style={{ border: '1px dashed var(--border-medium)', color: 'var(--primary)' }}
          >
            <Plus size={14} />
            <span>Add Project</span>
          </button>

          {/* Global Queue Button */}
          <button
            className={`view-btn queue-toggle-btn ${isQueueDrawerOpen ? 'active' : ''}`}
            onClick={() => setIsQueueDrawerOpen(!isQueueDrawerOpen)}
            title="Open Global Directive Queue"
          >
            <ListOrdered size={14} />
            <span>Queue</span>
            {globalQueue.length > 0 && (
              <span className="queue-badge-count">{globalQueue.length}</span>
            )}
          </button>

          {/* Theme Toggle Button */}
          <button className={`theme-toggle-btn ${notificationsEnabled ? 'active' : ''}`} onClick={toggleNotifications} title="Desktop notifications" aria-label="Toggle notifications">
            <Bell size={17} />
          </button>
          <button
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          </button>

          {/* Real-time indicator */}
          <div className="status-pill">
            <div className="status-dot" />
            <span>{wsConnected ? 'Live' : 'Connecting'}</span>
          </div>
        </div>
      </header>

      <div className="runtime-banner" role="status">
        <strong>AI: {runtime?.mode || 'checking'}</strong>
        <span>{runtime?.message || 'กำลังตรวจ AI runtime…'}</span>
        {!wsConnected && <span>การอัปเดตสดขาดการเชื่อมต่อ กำลังเชื่อมต่อใหม่…</span>}
        <button type="button" className="view-btn" onClick={fetchRuntime}>ตรวจอีกครั้ง</button>
      </div>
      {loadError && <div className="runtime-banner" role="alert">โหลดโปรเจกต์ไม่สำเร็จ: {loadError}<button className="view-btn" onClick={fetchData}>ลองใหม่</button></div>}

      {/* Global Queue Drawer */}
      {isQueueDrawerOpen && (
        <>
          <div className="queue-drawer-backdrop" onClick={() => setIsQueueDrawerOpen(false)} />
          <div className="queue-drawer-container">
          <div className="queue-drawer-header">
            <div className="queue-drawer-title-wrap">
              <ListOrdered size={16} color="var(--primary)" />
              <h3 className="queue-drawer-title">Global Directive Queue</h3>
              <span className="queue-drawer-count-badge">
                {globalQueue.filter(q => q.status === 'RUNNING').length} running · {globalQueue.filter(q => q.status === 'QUEUED').length} queued
              </span>
            </div>
            <button
              className="queue-drawer-close-btn"
              onClick={() => setIsQueueDrawerOpen(false)}
              title="Close Queue Drawer"
            >
              <X size={15} />
            </button>
          </div>

          <div className="queue-drawer-content">
            {globalQueue.length === 0 ? (
              <div className="queue-drawer-empty">
                <span className="queue-empty-icon">☕</span>
                <p className="queue-empty-text">No directives currently in queue.</p>
                <p className="queue-empty-sub">Directives dispatched to any project will queue and process sequentially here.</p>
              </div>
            ) : (
              <div className="queue-drawer-list">
                {globalQueue.map((item) => {
                  const isRunning = item.status === 'RUNNING';
                  const priority = item.priority || 'NORMAL';
                  const priorityClass = `priority-${priority.toLowerCase()}`;

                  return (
                    <div key={item.queue_id} className={`queue-drawer-card ${isRunning ? 'is-running' : ''}`}>
                      <div className="queue-card-header">
                        <span className="queue-card-project-tag">{item.project_name || item.project_id}</span>

                        {/* Priority Selector / Badge */}
                        {!isRunning ? (
                          <select
                            value={priority}
                            onChange={(e) => handleSetQueuePriority(item.queue_id, e.target.value)}
                            className={`priority-badge ${priorityClass}`}
                            style={{ border: 'none', cursor: 'pointer', outline: 'none', fontSize: '10px' }}
                            title="Change priority"
                          >
                            <option value="URGENT">🔥 Urgent</option>
                            <option value="HIGH">⚡ High</option>
                            <option value="NORMAL">Normal</option>
                            <option value="LOW">Low</option>
                          </select>
                        ) : (
                          <span className={`priority-badge ${priorityClass}`}>{priority}</span>
                        )}

                        <span className={`queue-card-status ${isRunning ? 'status-running' : 'status-queued'}`}>
                          {isRunning ? (
                            <>
                              <Loader2 size={11} className="spin" />
                              <span>Running</span>
                            </>
                          ) : (
                            <span>Queued #{item.position + 1}</span>
                          )}
                        </span>

                        {/* Reorder Up/Down for queued items */}
                        {!isRunning && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
                            <button
                              onClick={() => handleReorderQueueItem(item.queue_id, 'up')}
                              className="view-btn"
                              style={{ fontSize: '10px', padding: '1px 5px', height: 'auto' }}
                              title="Move Up in Queue"
                            >
                              ▲
                            </button>
                            <button
                              onClick={() => handleReorderQueueItem(item.queue_id, 'down')}
                              className="view-btn"
                              style={{ fontSize: '10px', padding: '1px 5px', height: 'auto' }}
                              title="Move Down in Queue"
                            >
                              ▼
                            </button>
                          </div>
                        )}

                        <span className="queue-card-time">
                          {new Date(item.created_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>

                        {!isRunning && (
                          <button
                            className="queue-card-cancel-btn"
                            onClick={() => handleCancelQueueItem(item.queue_id)}
                            title="Cancel this queued directive"
                          >
                            ✕ Cancel
                          </button>
                        )}
                      </div>
                      <div className="queue-card-directive">{item.directive}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
        </>
      )}

      {/* Persistent PM Directive Box — shown in Floor and Split modes */}
      {viewMode !== 'FOCUS' && (
        <PMCommandBar
          projects={projects}
          activeProjectId={activeProjectId}
          onSelectProject={setActiveProjectId}
          onDispatchDirective={handleDispatchDirective}
          onOpenBacklog={(pid) => {
            const p = projects.find(pr => pr.project_id === pid);
            setBacklogProject({ projectId: pid, projectName: p?.name });
          }}
          onOpenJournal={(pid) => {
            const p = projects.find(pr => pr.project_id === pid);
            setJournalProject({ projectId: pid, projectName: p?.name });
          }}
          sprintCost={sprintCost}
        />
      )}

      {/* Main Viewport */}
      <main className="content-area">
        <Suspense fallback={<div role="status" style={{ padding: 24 }}>กำลังโหลดพื้นที่ทำงาน…</div>}>
        {viewMode === 'OFFICE' && (
          <OfficeFloorView
            key="office"
            projects={projects}
            agentStates={agentStates}
            onAgentClick={(projId, role) => handleFocusProject(projId)}
            onFocusProject={handleFocusProject}
            onDeleteProject={handleDeleteProject}
            onRequestDelete={setProjectToDelete}
            onOpenAddProject={() => setIsAddProjectOpen(true)}
            onOpenStandup={(pid, pname) => setStandupProject({ projectId: pid, projectName: pname })}
            onOpenAddAgent={(proj) => setAddAgentProject(proj)}
            onOpenAutoGenTeam={(proj) => setAutoGenProject(proj)}
            onDeleteAgent={handleDeleteCustomAgent}
            onOpenAgentWhisper={(proj, agent) => setActiveWhisperAgent({ project: proj, agent })}
          />
        )}

        {viewMode === 'SPLIT' && (
          <DualSplitView
            projects={projects}
            tasksByProject={tasksByProject}
            liveStreamsByProject={liveStreams}
            onDeleteProject={handleDeleteProject}
            onRequestDelete={setProjectToDelete}
            onOpenAddProject={() => setIsAddProjectOpen(true)}
            onDispatchDirective={handleDispatchDirective}
            onOpenStandup={(pid, pname) => setStandupProject({ projectId: pid, projectName: pname })}
          />
        )}

        {isLoadingProjects && viewMode === 'FOCUS' && (
          <div className="view-loading-skeleton" style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '420px',
            gap: '14px',
            color: 'var(--text-muted)'
          }}>
            <Loader2 size={36} className="spin-slow" color="var(--primary)" />
            <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)' }}>
              Loading Project Workspace...
            </div>
            <div style={{ fontSize: '12px' }}>
              Restoring agents, backlog, and sprint pipeline
            </div>
          </div>
        )}

        {viewMode === 'FOCUS' && focusedProject && (
          <FocusRoomView
            key={focusedProjectId}
            project={focusedProject}
            initialTab={activeTabFromRoute}
            onTabChange={(tab) => {
              setActiveTabFromRoute(tab);
              window.location.hash = `#/project/${focusedProject.project_id}/${tab}`;
            }}
            agents={agentStates[focusedProjectId] || []}
            tasks={tasksByProject[focusedProjectId] || []}
            liveStream={liveStreams[focusedProjectId] || []}
            consoleHistory={consoleHistories[focusedProjectId] || []}
            timelineEvents={timelineEvents[focusedProjectId] || []}
            sprints={sprintsByProject[focusedProjectId] || []}
            onRerunSprint={handleRerunSprint}
            onRetrySprint={handleRetrySprint}
            onBack={handleBackToOverview}
            onSendConsoleMessage={handleSendConsoleMessage}
            onSendWhisper={handleSendWhisper}
            onRequestDelete={setProjectToDelete}
            onDeleteProject={handleDeleteProject}
          />
        )}
      </Suspense>
      </main>

      {/* Modals */}
      <DecisionGateModal
        key={activeApproval?.request_id}
        approval={activeApproval}
        onResolve={handleResolveApproval}
      />

      <AddProjectModal
        isOpen={isAddProjectOpen}
        onClose={() => setIsAddProjectOpen(false)}
        onAddProject={handleAddProject}
      />

      <DeleteProjectModal
        isOpen={Boolean(projectToDelete)}
        project={projectToDelete}
        onConfirm={handleDeleteProject}
        onCancel={() => setProjectToDelete(null)}
      />

      <TechLeadStandupModal
        isOpen={Boolean(standupProject)}
        onClose={() => setStandupProject(null)}
        projectId={standupProject?.projectId}
        projectName={standupProject?.projectName}
        theme={theme}
      />

      <AddAgentModal
        isOpen={Boolean(addAgentProject)}
        project={addAgentProject}
        onClose={() => setAddAgentProject(null)}
        onAddAgent={handleAddCustomAgent}
      />

      <AutoGenerateTeamModal
        isOpen={Boolean(autoGenProject)}
        project={autoGenProject}
        onClose={() => setAutoGenProject(null)}
        onConfirmTeam={handleApplyGeneratedTeam}
      />

      <QuickWhisperDrawer
        isOpen={Boolean(activeWhisperAgent)}
        onClose={() => setActiveWhisperAgent(null)}
        project={activeWhisperAgent?.project}
        agent={activeWhisperAgent?.agent}
        onSendWhisper={handleSendWhisper}
        onDeepDive={(projId) => {
          setActiveWhisperAgent(null);
          handleFocusProject(projId);
        }}
      />

      <BacklogBoardModal
        isOpen={Boolean(backlogProject)}
        onClose={() => setBacklogProject(null)}
        projectId={backlogProject?.projectId}
        projectName={backlogProject?.projectName}
      />

      <ProjectJournalModal
        isOpen={Boolean(journalProject)}
        onClose={() => setJournalProject(null)}
        projectId={journalProject?.projectId}
        projectName={journalProject?.projectName}
      />

      {completedSprint && (
        <SprintCompletionModal
          sprint={completedSprint}
          projectId={completedSprint.project_id}
          onClose={() => setCompletedSprint(null)}
          onViewHistory={() => {
            setCompletedSprint(null);
            // Navigate to Focus Room + Sprints & QA tab if possible
            if (completedSprint.project_id) {
              setFocusedProjectId(completedSprint.project_id);
              setViewMode('FOCUS');
            }
          }}
        />
      )}
    </div>
  );
}
