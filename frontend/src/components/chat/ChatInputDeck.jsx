import React, { useState, useRef, useEffect } from 'react';
import { Paperclip, Send, X } from 'lucide-react';
import { MentionSuggestPopup } from './MentionSuggestPopup';

export function ChatInputDeck({ onSendMessage, isSending, onAttachFile }) {
  const [text, setText] = useState('');
  const [mentionPos, setMentionPos] = useState(null);
  const textareaRef = useRef(null);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (text.trim() && !isSending) {
        onSendMessage(text);
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
    
    // Check if the last typed word starts with @ and we are currently typing it
    if (lastWord.startsWith('@')) {
      // Calculate a rough position based on text length (simplified)
      // In a real app we'd use getBoundingClientRect or a hidden div to get exact coords
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

  return (
    <div style={{ position: 'relative', padding: '16px', background: 'var(--bg-canvas)', borderTop: '1px solid var(--border-medium)' }}>
      {mentionPos && <MentionSuggestPopup x={mentionPos.x} y={mentionPos.y} onSelect={insertMention} />}
      
      <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '12px', padding: '8px' }}>
        <button 
          onClick={onAttachFile}
          style={{ padding: '8px', background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          title="Attach File or Paste Image"
        >
          <Paperclip size={18} />
        </button>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask Tech Lead or type @ to mention an agent..."
          disabled={isSending}
          style={{
            flex: 1, minHeight: '24px', maxHeight: '180px', background: 'transparent',
            border: 'none', color: 'var(--text-primary)', fontSize: '14px',
            resize: 'none', outline: 'none', padding: '8px 0', fontFamily: 'inherit'
          }}
        />
        <button 
          onClick={() => { if(text.trim()) { onSendMessage(text); setText(''); } }}
          disabled={isSending || !text.trim()}
          style={{ padding: '8px', background: text.trim() ? '#3b82f6' : 'transparent', border: 'none', borderRadius: '8px', color: text.trim() ? '#fff' : 'var(--text-muted)', cursor: isSending ? 'wait' : 'pointer' }}
        >
          <Send size={18} />
        </button>
      </div>
      <div style={{ textAlign: 'center', marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
        Press <kbd>Enter</kbd> to send, <kbd>Shift+Enter</kbd> for new line
      </div>
    </div>
  );
}
