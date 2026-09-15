import React, { useState } from 'react';
import { AlertCircle, CheckCircle2, XCircle } from 'lucide-react';

export function DecisionGateModal({ approval, onResolve }) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  if (!approval) return null;
  const resolve = async decision => {
    setSubmitting(true);
    setError('');
    try { await onResolve(approval.request_id, decision); }
    catch (err) { setError(err.message || 'บันทึกการตัดสินใจไม่สำเร็จ ลองอีกครั้ง'); }
    finally { setSubmitting(false); }
  };
  return <div className="modal-overlay">
    <section className="gate-modal" role="dialog" aria-modal="true" aria-labelledby="gate-heading">
      <div className="gate-title" id="gate-heading"><AlertCircle size={20} />รอการตัดสินใจจากคุณ</div>
      <p>{approval.gate_type === 'QA_FAILURE_ESCALATION' ? 'ผลทดสอบยังไม่ผ่าน การอนุมัติจะให้ทำงานต่อพร้อมระบุข้อจำกัดในสรุป' : 'อ่านแผนและเกณฑ์สำเร็จก่อนอนุมัติให้ทีมเริ่มลงมือ'}</p>
      <div className="gate-body" style={{ whiteSpace: 'pre-wrap', maxHeight: '50vh', overflowY: 'auto', overflowWrap: 'anywhere' }}>{approval.summary}</div>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>หากต้องการเปลี่ยนแผน ให้ปฏิเสธแล้วส่งคำสั่งใหม่พร้อมสิ่งที่ต้องแก้</p>
      {error && <p role="alert">{error}</p>}
      <div className="gate-actions">
        <button className="btn-reject" disabled={submitting} onClick={() => resolve('REJECTED')}><XCircle size={14} /> หยุดเพื่อแก้คำสั่ง</button>
        <button className="btn-approve" disabled={submitting} onClick={() => resolve('APPROVED')}><CheckCircle2 size={14} /> {submitting ? 'กำลังบันทึก…' : 'อนุมัติให้ทำต่อ'}</button>
      </div>
    </section>
  </div>;
}
