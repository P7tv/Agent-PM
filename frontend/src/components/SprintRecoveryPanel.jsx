import React, { useEffect, useState } from 'react';

const STAGE_NAMES = { PLANNING: 'วางแผน', QA: 'QA', REVIEWER: 'Reviewer', FINAL: 'ตรวจขั้นสุดท้าย' };

export default function SprintRecoveryPanel({ sprints = [], onResume, onStartOver }) {
  const latest = [...sprints].sort((a, b) => b.started_at - a.started_at)[0];
  const [requestState, setRequestState] = useState('idle');
  const [preview, setPreview] = useState({});
  useEffect(() => setRequestState('idle'), [latest?.sprint_id]);
  if (!latest || !['FAILED', 'REJECTED', 'PAUSED', 'INTERRUPTED'].includes(latest.status)) return null;

  const stage = latest.execution_plan?.checkpoint_stage;
  const applied = latest.change_evidence?.applied_to_project === true;
  const legacyCheckpoint = Boolean(latest.checkpoint_path && !latest.execution_plan?.checkpoint_manifest_hash);
  const canResume = Boolean(onResume && latest.checkpoint_path && !legacyCheckpoint && !applied && ['PLANNING', 'IMPLEMENTATION', 'QA', 'REVIEWER', 'FINAL'].includes(stage));
  const changes = ['added', 'modified', 'deleted'].flatMap(kind =>
    (latest.change_evidence?.[kind] || []).map(path => ({ kind, path })),
  );
  const resume = async () => {
    setRequestState('sending');
    try {
      const result = await onResume(latest, ['PLANNING', 'IMPLEMENTATION'].includes(stage) ? stage : 'QA');
      setRequestState(result === false ? 'idle' : 'queued');
    } catch {
      setRequestState('error');
    }
  };
  const previewCheckpoint = async () => {
    setPreview({ busy: true });
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(latest.project_id)}/preview?sprint_id=${encodeURIComponent(latest.sprint_id)}`, { method: 'POST' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'เปิด Preview ไม่สำเร็จ');
      const url = new URL(result.url);
      if (!['http:', 'https:'].includes(url.protocol) || !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) throw new Error('Preview ต้องใช้ URL ของเครื่องนี้');
      setPreview({ url: url.href });
    } catch (error) { setPreview({ error: error.message }); }
  };

  return <section className="sprint-recovery-panel" aria-label="ทำงานต่อจาก checkpoint">
    <strong>หยุดงานแล้ว{stage ? ` · ขั้นล่าสุด: ${STAGE_NAMES[stage] || stage}` : ''}</strong>
    <div>{applied ? 'ไฟล์ถูกนำเข้าโปรเจกต์แล้ว แต่รอบงานหยุดก่อนจบ' : changes.length ? `เก็บการเปลี่ยนแปลง ${changes.length} ไฟล์แล้ว · ยังไม่นำเข้าโปรเจกต์` : 'ยังไม่มีรายการการเปลี่ยนแปลงไฟล์ที่บันทึกไว้'}</div>
    {latest.checkpoint_path && !applied && <div className="recovery-path">โฟลเดอร์พักงาน: <code>{latest.checkpoint_path}</code></div>}
    <p>{canResume ? 'Resume จะใช้ไฟล์ที่พักไว้ ตรวจงานที่ยังไม่เสร็จ และข้ามขั้นเขียนที่เสร็จแล้ว จากนั้นตรวจ QA และ Review ก่อนนำเข้าโปรเจกต์' : applied ? 'ตรวจไฟล์ในโปรเจกต์และสรุปรอบงานก่อนเริ่มรอบใหม่' : legacyCheckpoint ? 'Checkpoint เก่าไม่มีฐานเปรียบเทียบไฟล์เดิม จึงไม่เปิด automatic Resume เพื่อป้องกันการทับงาน ตรวจหรือกู้ไฟล์จากโฟลเดอร์พักงานได้' : 'ไม่พบ checkpoint ที่ใช้ต่อได้ ใช้ “เริ่มรอบใหม่” เพื่อเริ่ม pipeline จากต้น'}</p>
    <div className="recovery-actions">
      {latest.checkpoint_path && !legacyCheckpoint && !applied && <button className="view-btn" disabled={preview.busy} onClick={previewCheckpoint}>{preview.busy ? 'กำลังเปิด Preview…' : 'ลองไฟล์พักงาน'}</button>}
      {canResume && <button className="view-btn" disabled={['sending', 'queued'].includes(requestState)} onClick={resume}>
        {requestState === 'sending' ? 'กำลังสั่ง Resume…' : requestState === 'queued' ? 'ส่ง Resume เข้าคิวแล้ว' : '▶ Resume จากไฟล์เดิม'}
      </button>}
      {onStartOver && <button className="view-btn" disabled={['sending', 'queued'].includes(requestState)} onClick={() => {
        if (window.confirm('เริ่ม pipeline รอบใหม่จากต้น? รอบใหม่นี้จะไม่ใช้ไฟล์ใน checkpoint เดิม')) onStartOver(latest.directive);
      }}>เริ่มรอบใหม่</button>}
    </div>
    {requestState === 'error' && <p role="alert">สั่ง Resume ไม่สำเร็จ ลองอีกครั้งได้</p>}
    {preview.url && <p><a href={preview.url} target="_blank" rel="noreferrer">เปิด Preview ของไฟล์พักงาน</a> · ยังไม่ได้ตรวจรับหรือนำเข้าโปรเจกต์</p>}
    {preview.error && <p role="alert">{preview.error}</p>}
    {changes.length > 0 && <details><summary>ดูรายการไฟล์{applied ? 'ที่นำเข้าโปรเจกต์' : 'ที่พักไว้'} ({changes.length})</summary>
      <ul>{changes.map(({ kind, path }) => <li key={`${kind}:${path}`}><code>{kind}</code> {path}</li>)}</ul>
      {latest.change_evidence?.diff && <details><summary>ดูความเปลี่ยนแปลงของไฟล์</summary><pre>{latest.change_evidence.diff}</pre></details>}
    </details>}
  </section>;
}
