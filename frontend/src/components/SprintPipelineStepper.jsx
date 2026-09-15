import React from 'react';
import { Compass, Server, Layout, FlaskConical, ShieldCheck, CheckCircle2, Loader2 } from 'lucide-react';

const STAGES = [
  { id: 1, label: 'Plan & Triage', sub: 'TechLead & Architect', icon: Compass },
  { id: 2, label: 'Parallel Dev', sub: 'Backend & Designer', icon: Server },
  { id: 3, label: 'Frontend UI', sub: 'Components & Tokens', icon: Layout },
  { id: 4, label: 'QA Verification', sub: 'Self-Healing Tests', icon: FlaskConical },
  { id: 5, label: 'Audit & Release', sub: 'Review & Docs', icon: ShieldCheck }
];

export default function SprintPipelineStepper({ agents = [], sprints = [] }) {
  // Determine active stage from agent states
  const agentMap = {};
  (agents || []).forEach((a) => {
    agentMap[a.role] = a.status;
  });

  const activeSprint = (sprints || []).find((s) => s.status === 'RUNNING');
  const latestSprint = activeSprint || (sprints && sprints.length > 0 ? sprints[sprints.length - 1] : null);
  const isSprintRunning = Boolean(activeSprint);

  let currentStage = 0;
  if (isSprintRunning) {
    if (agentMap['Reviewer'] === 'REVIEWING' || agentMap['DocWriter'] === 'WORKING') {
      currentStage = 5;
    } else if (agentMap['QATester'] === 'TESTING' || agentMap['QATester'] === 'BLOCKED') {
      currentStage = 4;
    } else if (agentMap['FrontendDev'] === 'WORKING') {
      currentStage = 3;
    } else if (agentMap['BackendDev'] === 'WORKING' || agentMap['Designer'] === 'WORKING') {
      currentStage = 2;
    } else if (agentMap['TechLead'] === 'THINKING' || agentMap['Architect'] === 'THINKING') {
      currentStage = 1;
    } else {
      currentStage = 1;
    }
  } else if (latestSprint && latestSprint.status === 'COMPLETED') {
    currentStage = 6; // All stages completed
  } else if (latestSprint && latestSprint.status === 'FAILED') {
    currentStage = 4;
  }

  const badgeText = isSprintRunning 
    ? '⚡ SPRINT IN PROGRESS' 
    : (latestSprint && latestSprint.status === 'COMPLETED' ? '✅ LATEST SPRINT COMPLETED' : '⚪ PIPELINE STANDBY');

  return (
    <div className="sprint-pipeline-stepper" role="progressbar" aria-label="Sprint Pipeline Progress">
      <div className="stepper-header">
        <div className="stepper-title-wrap">
          <span className={`stepper-badge ${isSprintRunning ? 'is-running' : ''}`}>{badgeText}</span>
          <span className="stepper-directive-text" title={latestSprint?.directive}>
            {latestSprint?.directive || 'Ready for next PM directive'}
          </span>
        </div>
        {latestSprint?.sprint_id && (
          <span className="stepper-sprint-id">{latestSprint.sprint_id}</span>
        )}
      </div>

      <div className="stepper-track">
        {STAGES.map((st, idx) => {
          const Icon = st.icon;
          const isDone = currentStage > st.id || currentStage === 6;
          const isActive = isSprintRunning && currentStage === st.id;
          const isPending = currentStage < st.id;

          let statusClass = 'is-pending';
          if (isDone) statusClass = 'is-done';
          if (isActive) statusClass = 'is-active';

          return (
            <React.Fragment key={st.id}>
              <div className={`stepper-node ${statusClass}`}>
                <div className="stepper-icon-circle">
                  {isDone ? (
                    <CheckCircle2 size={15} className="text-success" />
                  ) : isActive ? (
                    <Loader2 size={15} className="spin text-primary" />
                  ) : (
                    <Icon size={14} />
                  )}
                </div>
                <div className="stepper-node-text">
                  <span className="stepper-node-label">{st.label}</span>
                  <span className="stepper-node-sub">{st.sub}</span>
                </div>
              </div>
              {idx < STAGES.length - 1 && (
                <div className={`stepper-connector ${currentStage > st.id || currentStage === 6 ? 'is-done' : ''}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
