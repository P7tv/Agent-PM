import React, { useState, useEffect, useRef } from 'react';
import { Building2, Columns, Focus, Radio, Plus, RefreshCw } from 'lucide-react';
import PMCommandBar from './components/PMCommandBar';
import OfficeFloorView from './components/OfficeFloorView';
import DualSplitView from './components/DualSplitView';
import FocusRoomView from './components/FocusRoomView';
import { DecisionGateModal, WhisperModal } from './components/DecisionGateModal';

export default function App() {
  const [viewMode, setViewMode] = useState('OFFICE'); // OFFICE, SPLIT, FOCUS
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [focusedProjectId, setFocusedProjectId] = useState(null);

  const [agentStates, setAgentStates] = useState({}); // { [projId]: [AgentState] }
  const [tasksByProject, setTasksByProject] = useState({}); // { [projId]: [TaskItem] }
  const [liveStreams, setLiveStreams] = useState({}); // { [projId]: [logs] }

  const [activeApproval, setActiveApproval] = useState(null);
  const [whisperTarget, setWhisperTarget] = useState(null); // { projectId, role }
  const [wsConnected, setWsConnected] = useState(false);

  const socketRef = useRef(null);

  // Fetch projects and initial data
  const fetchData = async () => {
    try {
      let res = await fetch('/api/projects');
      let data = await res.json();
      
      // If no projects, bootstrap 2 default projects
      if (data.length === 0) {
        await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: 'alpha-app',
            name: 'Project Alpha (Core App)',
            workspace_path: '/Users/panpan/My PM/projects/alpha',
            auto_pilot: true
          })
        });
        await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: 'beta-api',
            name: 'Project Beta (Next Service)',
            workspace_path: '/Users/panpan/My PM/projects/beta',
            auto_pilot: false
          })
        });
        res = await fetch('/api/projects');
        data = await res.json();
      }

      setProjects(data);
      if (data.length > 0 && !activeProjectId) {
        setActiveProjectId(data[0].project_id);
      }

      // Fetch agents & tasks for each project
      for (const p of data) {
        fetchProjectDetails(p.project_id);
      }
    } catch (err) {
      console.error('Error fetching initial data:', err);
    }
  };

  const fetchProjectDetails = async (projId) => {
    try {
      const [agentsRes, tasksRes, approvalsRes] = await Promise.all([
        fetch(`/api/projects/${projId}/agents`),
        fetch(`/api/projects/${projId}/tasks`),
        fetch(`/api/projects/${projId}/approvals`)
      ]);

      const agents = await agentsRes.json();
      const tasks = await tasksRes.json();
      const approvals = await approvalsRes.json();

      setAgentStates((prev) => ({ ...prev, [projId]: agents }));
      setTasksByProject((prev) => ({ ...prev, [projId]: tasks }));
      if (approvals.length > 0) {
        setActiveApproval(approvals[0]);
      }
    } catch (e) {
      console.error(`Error loading details for ${projId}:`, e);
    }
  };

  // Setup WebSocket connection
  useEffect(() => {
    fetchData();

    const connectWs = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/live`;
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          const evType = parsed.event;
          const data = parsed.data;
          const projId = data.project_id;

          // Append to live stream
          if (projId) {
            setLiveStreams((prev) => ({
              ...prev,
              [projId]: [...(prev[projId] || []), data]
            }));
          }

          // Handle state updates
          if (evType === 'AGENT_STATE_UPDATE' || evType === 'AGENT_STATUS_CHANGE') {
            fetchProjectDetails(projId);
          } else if (evType === 'TASKS_UPDATED') {
            fetch(`/api/projects/${projId}/tasks`)
              .then((r) => r.json())
              .then((tasks) => {
                setTasksByProject((prev) => ({ ...prev, [projId]: tasks }));
              });
          } else if (evType === 'DECISION_GATE_OPEN') {
            setActiveApproval(data);
          } else if (evType === 'DECISION_GATE_RESOLVED') {
            setActiveApproval(null);
          }
        } catch (e) {
          console.error('WS parse error:', e);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        setTimeout(connectWs, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connectWs();

    return () => {
      if (socketRef.current) socketRef.current.close();
    };
  }, []);

  const handleDispatchDirective = async (projectId, directive) => {
    await fetch(`/api/projects/${projectId}/directive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ directive })
    });
    fetchProjectDetails(projectId);
  };

  const handleResolveApproval = async (requestId, decision) => {
    if (!activeApproval) return;
    await fetch(`/api/projects/${activeApproval.project_id}/approvals/${requestId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision })
    });
    setActiveApproval(null);
    fetchProjectDetails(activeApproval.project_id);
  };

  const handleSendWhisper = async (projectId, role, message) => {
    await fetch(`/api/projects/${projectId}/whisper`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, message })
    });
  };

  const handleFocusProject = (projectId) => {
    setFocusedProjectId(projectId);
    setViewMode('FOCUS');
  };

  const focusedProject = projects.find((p) => p.project_id === focusedProjectId);

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <div className="brand-logo">
          <div className="brand-icon">🏢</div>
          <div>
            <h1 className="brand-title">ANTIGRAVITY AI OFFICE</h1>
            <div className="brand-subtitle">MULTI-AGENT PM COMMAND CENTER</div>
          </div>
        </div>

        {/* View Switcher */}
        <div className="view-switcher">
          <button
            className={`view-btn ${viewMode === 'OFFICE' ? 'active' : ''}`}
            onClick={() => setViewMode('OFFICE')}
          >
            <Building2 size={15} />
            <span>OFFICE FLOOR</span>
          </button>
          <button
            className={`view-btn ${viewMode === 'SPLIT' ? 'active' : ''}`}
            onClick={() => setViewMode('SPLIT')}
          >
            <Columns size={15} />
            <span>DUAL SPLIT</span>
          </button>
          {focusedProject && (
            <button
              className={`view-btn ${viewMode === 'FOCUS' ? 'active' : ''}`}
              onClick={() => setViewMode('FOCUS')}
            >
              <Focus size={15} />
              <span>WAR ROOM: {focusedProject.name}</span>
            </button>
          )}
        </div>

        {/* Real-time indicator */}
        <div className="status-pill">
          <div className={`status-dot ${wsConnected ? '' : 'disconnected'}`} />
          <span>{wsConnected ? 'ANTIGRAVITY ONLINE' : 'CONNECTING...'}</span>
        </div>
      </header>

      {/* Persistent PM Directive Box */}
      <PMCommandBar
        projects={projects}
        activeProjectId={activeProjectId}
        onSelectProject={setActiveProjectId}
        onDispatchDirective={handleDispatchDirective}
      />

      {/* Main Viewport */}
      <main className="content-area">
        {viewMode === 'OFFICE' && (
          <OfficeFloorView
            projects={projects}
            agentStates={agentStates}
            onAgentClick={(projId, role) => setWhisperTarget({ projectId: projId, role })}
            onFocusProject={handleFocusProject}
          />
        )}

        {viewMode === 'SPLIT' && (
          <DualSplitView
            projects={projects}
            tasksByProject={tasksByProject}
            liveStreamsByProject={liveStreams}
          />
        )}

        {viewMode === 'FOCUS' && focusedProject && (
          <FocusRoomView
            project={focusedProject}
            agents={agentStates[focusedProjectId] || []}
            tasks={tasksByProject[focusedProjectId] || []}
            liveStream={liveStreams[focusedProjectId] || []}
            onBack={() => setViewMode('OFFICE')}
            onAgentClick={(projId, role) => setWhisperTarget({ projectId: projId, role })}
          />
        )}
      </main>

      {/* Modals */}
      <DecisionGateModal
        approval={activeApproval}
        onResolve={handleResolveApproval}
      />

      <WhisperModal
        whisperTarget={whisperTarget}
        onClose={() => setWhisperTarget(null)}
        onSendWhisper={handleSendWhisper}
      />
    </div>
  );
}
