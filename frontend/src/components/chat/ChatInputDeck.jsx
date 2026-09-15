import React, { useState, useRef, useEffect } from 'react';
import { Paperclip, Send, Zap, MessageSquare } from 'lucide-react';
import { MentionSuggestPopup } from './MentionSuggestPopup';

export function ChatInputDeck({ onSendMessage, isSending, onAttachFile }) {
  const [text, setText] = useState('');
  const [isDirectiveMode, setIsDirectiveMode] = useState(false);
  const [mentionPos, setMentionPos] = useState(null);
  const textareaRef = useRef(null);

  const handleKeyDown = (e) => {
    // Ctrl+Enter or Cmd+Enter: Force run as Directive
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (text.trim() && !isSending) {
        onSendMessage(text, true);
        setText('');
      }
      return;
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (text.trim() && !isSending) {
        onSendMessage(text, isDirectiveMode);
        setText('');
      }
    }
  };

  const handleChange = (e) => {
    const val = e.target.value;
    setText(val);
    
    // Auto-resize
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;

    // Mention detection
    const words = val.split(' ');
    const lastWord = words[words.length - 1];
    
    if (lastWord.startsWith('@')) {
      setMentionPos({ x: 10, y: 70 });
    } else {
      setMentionPos(null);
    }
  };

  const insertMention = (role) => {
    const words = text.split(' ');
    words.pop(); // remove partial @
    const newText = words.join(' ') + (words.length > 0 ? ' ' : '') + `@${role} `;
    setText(newText);
    setMentionPos(null);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  const handleQuickChip = (chip) => {
    if (chip === 'DIRECTIVE') {
      setIsDirectiveMode(true);
      if (!text.startsWith('@Team')) {
        setText('@Team ' + text.replace(/^@\w+\s*/, ''));
      }
    } else {
      insertMention(chip);
    }
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  const handleSend = (forceDirective = false) => {
    if (!text.trim() || isSending) return;
    const asDirective = forceDirective || isDirectiveMode;
    onSendMessage(text, asDirective);
    setText('');
  };

  return (
    <div style={{ position: 'relative', padding: '12px 16px 16px 16px', background: 'var(--bg-canvas)', borderTop: '1px solid var(--border-medium)' }}>
      {mentionPos && <MentionSuggestPopup x={mentionPos.x} y={mentionPos.y} onSelect={insertMention} />}
      
      {/* Top Quick Chips & Mode Switcher */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflowX: 'auto' }}>
          <button
            type="button"
            onClick={() => handleQuickChip('DIRECTIVE')}
            style={{
              fontSize: '11px',
              padding: '3px 8px',
              borderRadius: '12px',
              border: '1px solid rgba(245, 158, 11, 0.4)',
              background: 'rgba(245, 158, 11, 0.12)',
              color: '#f59e0b',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <Zap size={12} />
            สั่งงานทั้งทีม (Directive)
          </button>

          {['TechLead', 'Architect', 'BackendDev', 'FrontendDev', 'QATester'].map((role) => (
            <button
              key={role}
              type="button"
              onClick={() => handleQuickChip(role)}
              style={{
                fontSize: '11px',
                padding: '3px 7px',
                borderRadius: '12px',
                border: '1px solid var(--border-subtle)',
                background: 'var(--bg-surface)',
                color: 'var(--text-secondary)',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              @{role}
            </button>
          ))}
        </div>

        {/* Mode Toggle Button */}
        <button
          type="button"
          onClick={() => setIsDirectiveMode(!isDirectiveMode)}
          style={{
            fontSize: '11px',
            padding: '3px 9px',
            borderRadius: '12px',
            border: isDirectiveMode ? '1px solid #f59e0b' : '1px solid var(--border-subtle)',
            background: isDirectiveMode ? 'rgba(245, 158, 11, 0.15)' : 'var(--bg-surface)',
            color: isDirectiveMode ? '#f59e0b' : 'var(--text-muted)',
            fontWeight: '600',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}
          title="Click to toggle between Chat and Sprint Directive mode"
        >
          {isDirectiveMode ? <Zap size={11} /> : <MessageSquare size={11} />}
          โหมด: {isDirectiveMode ? '⚡ สั่งงานทีม (Sprint)' : '💬 คุยปรึกษา'}
        </button>
      </div>

      <div style={{
        display: 'flex',
        gap: '8px',
        alignItems: 'flex-end',
        background: 'var(--bg-surface)',
        border: isDirectiveMode ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid var(--border-subtle)',
        boxShadow: isDirectiveMode ? '0 0 10px rgba(245, 158, 11, 0.08)' : 'none',
        borderRadius: '12px',
        padding: '8px 10px',
        transition: 'border-color 0.2s, box-shadow 0.2s'
      }}>
        <button 
          onClick={onAttachFile}
          style={{ padding: '6px', background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          title="Attach File or Paste Image"
        >
          <Paperclip size={17} />
        </button>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={
            isDirectiveMode
              ? "⚡ สั่งงานให้ทีมเริ่มทำทันที เช่น 'เริ่มลงมือเลย', 'สร้างระบบ POS API'..."
              : "พิมพ์สั่ง Tech Lead หรือกด @ เพื่อคุยกับ Agent (หรือกด ⚡ เพื่อสั่งงานทั้งทีม)..."
          }
          disabled={isSending}
          style={{
            flex: 1, minHeight: '26px', maxHeight: '180px', background: 'transparent',
            border: 'none', color: 'var(--text-primary)', fontSize: '13.5px',
            resize: 'none', outline: 'none', padding: '6px 0', fontFamily: 'inherit'
          }}
        />

        {/* Action Buttons: Directive vs Send */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {text.trim() && !isDirectiveMode && (
            <button
              type="button"
              onClick={() => handleSend(true)}
              disabled={isSending}
              style={{
                padding: '6px 10px',
                background: 'rgba(245, 158, 11, 0.15)',
                border: '1px solid rgba(245, 158, 11, 0.4)',
                borderRadius: '8px',
                color: '#f59e0b',
                cursor: isSending ? 'wait' : 'pointer',
                fontSize: '11px',
                fontWeight: '700',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
              title="สั่งให้ทีมเริ่มลงมือทำทันที (Run as Sprint Directive)"
            >
              <Zap size={13} />
              <span>สั่งงานทีม</span>
            </button>
          )}

          <button 
            type="button"
            onClick={() => handleSend(isDirectiveMode)}
            disabled={isSending || !text.trim()}
            style={{
              padding: '6px 12px',
              background: !text.trim() ? 'transparent' : (isDirectiveMode ? '#f59e0b' : '#3b82f6'),
              border: 'none',
              borderRadius: '8px',
              color: text.trim() ? '#fff' : 'var(--text-muted)',
              cursor: isSending ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontWeight: '600',
              fontSize: '12px'
            }}
          >
            {isDirectiveMode ? <Zap size={14} /> : <Send size={14} />}
            <span>{isDirectiveMode ? 'รัน Sprint' : 'ส่ง'}</span>
          </button>
        </div>
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px', fontSize: '11px', color: 'var(--text-muted)', padding: '0 4px' }}>
        <span>กด <kbd>Enter</kbd> เพื่อส่ง, <kbd>Shift+Enter</kbd> ขึ้นบรรทัดใหม่</span>
        <span>กด <kbd>Ctrl+Enter</kbd> เพื่อสั่งงานทั้งทีมทันที ⚡</span>
      </div>
    </div>
  );
}
