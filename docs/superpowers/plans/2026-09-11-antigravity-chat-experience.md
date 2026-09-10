# Antigravity Chat Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the AI Office PM Dashboard chat system into a full-width, clean, and interactive Antigravity IDE-style chat experience.

**Architecture:** Decompose the monolithic `ConsoleBubble` in `FocusRoomView.jsx` into specialized React components (`ChatStreamView`, `ChatMessageItem`, `ActivityAccordion`, `RichCodeBlock`, `ChatInputDeck`, `MentionSuggestPopup`). 

**Tech Stack:** React, CSS Modules (or inline styles following existing patterns), Lucide-React, React-Markdown.

## Global Constraints

- No external chat UI library (e.g. react-chat-elements) should be added; build custom components.
- Maintain existing WebSocket and HTTP endpoints (`/api/projects/{id}/console/chat`).
- Follow the visual hierarchy and color tokens (dark theme, blue accent) defined in the design spec.

---

### Task 1: Create Helper Components (`ActivityAccordion` & `RichCodeBlock`)

**Files:**
- Create: `frontend/src/components/chat/ActivityAccordion.jsx`
- Create: `frontend/src/components/chat/RichCodeBlock.jsx`

**Interfaces:**
- Consumes: Nothing
- Produces: `ActivityAccordion` (props: `title`, `status`, `logs`), `RichCodeBlock` (props: `language`, `code`, `filepath`, `onApply`)

- [ ] **Step 1: Write `ActivityAccordion.jsx`**

```jsx
import React, { useState } from 'react';
import { ChevronRight, ChevronDown, CheckCircle2, Loader2, Terminal } from 'lucide-react';

export function ActivityAccordion({ title, status, logs }) {
  const [isOpen, setIsOpen] = useState(status === 'running');
  const isRunning = status === 'running';

  return (
    <div style={{ margin: '8px 0', border: '1px solid var(--border-subtle)', borderRadius: '8px', overflow: 'hidden' }}>
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{ 
          display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 12px', 
          background: 'var(--bg-surface)', cursor: 'pointer', fontSize: '12px', color: 'var(--text-muted)' 
        }}
      >
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {isRunning ? <Loader2 size={14} className="spin" color="#3b82f6" /> : <CheckCircle2 size={14} color="#22c55e" />}
        <span style={{ fontWeight: 600 }}>{title}</span>
      </div>
      {isOpen && logs && (
        <pre style={{ margin: 0, padding: '12px', background: '#0a0d14', color: '#e2e8f0', fontSize: '11px', overflowX: 'auto', fontFamily: 'var(--font-mono)' }}>
          {logs}
        </pre>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write `RichCodeBlock.jsx`**

```jsx
import React, { useState } from 'react';
import { Copy, Check, FileCode2, Play } from 'lucide-react';

export function RichCodeBlock({ language, code, filepath, onApply, applying }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ margin: '12px 0', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border-medium)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 12px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '11px' }}>
          {filepath ? <FileCode2 size={12} /> : null}
          <span style={{ fontWeight: 600 }}>{filepath || language || 'text'}</span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {filepath && onApply && (
            <button onClick={() => onApply(filepath, code)} disabled={applying} style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: '#3b82f6', color: '#fff', border: 'none', cursor: applying ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
              {applying ? <span className="spin">⟳</span> : <Play size={11} />} Apply
            </button>
          )}
          <button onClick={handleCopy} style={{ fontSize: '11px', padding: '2px 6px', background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}>
            {copied ? <Check size={12} color="#22c55e" /> : <Copy size={12} />}
          </button>
        </div>
      </div>
      <pre style={{ margin: 0, padding: '12px', background: '#0a0d14', color: '#e2e8f0', fontSize: '13px', overflowX: 'auto', fontFamily: 'var(--font-mono)' }}>
        <code>{code}</code>
      </pre>
    </div>
  );
}
```

---

### Task 2: Create Core Chat Components (`ChatMessageItem` & `MentionSuggestPopup`)

**Files:**
- Create: `frontend/src/components/chat/MentionSuggestPopup.jsx`
- Create: `frontend/src/components/chat/ChatMessageItem.jsx`

**Interfaces:**
- Consumes: `RichCodeBlock`, `ActivityAccordion`
- Produces: `MentionSuggestPopup` (props: `x, y, onSelect, onClose`), `ChatMessageItem` (props: `msg, onApply`)

- [ ] **Step 1: Write `MentionSuggestPopup.jsx`**

```jsx
import React from 'react';
import { Users, Code2, PenTool, CheckCircle } from 'lucide-react';

const AGENTS = [
  { role: 'TechLead', emoji: '👑', label: 'Tech Lead', color: '#f59e0b' },
  { role: 'Architect', emoji: '🏛️', label: 'Architect', color: '#8b5cf6' },
  { role: 'FrontendDev', emoji: '⚛️', label: 'Frontend Dev', color: '#06b6d4' },
  { role: 'BackendDev', emoji: '⚙️', label: 'Backend Dev', color: '#10b981' },
  { role: 'Designer', emoji: '🎨', label: 'Designer', color: '#ec4899' },
  { role: 'QATester', emoji: '🧪', label: 'QA Tester', color: '#ef4444' },
  { role: 'Team', emoji: '📢', label: 'Team Broadcast', color: '#3b82f6' }
];

export function MentionSuggestPopup({ x, y, onSelect }) {
  return (
    <div style={{
      position: 'absolute', bottom: y, left: x, background: 'var(--bg-canvas)',
      border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '6px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.3)', zIndex: 100, width: '220px',
      display: 'flex', flexDirection: 'column', gap: '2px'
    }}>
      {AGENTS.map(agent => (
        <div key={agent.role} onClick={() => onSelect(agent.role)} style={{
          padding: '6px 10px', borderRadius: '4px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px',
          color: 'var(--text-primary)'
        }} onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-surface)'}
           onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
          <span>{agent.emoji}</span>
          <span style={{ fontWeight: 600 }}>{agent.role}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Write `ChatMessageItem.jsx`**

```jsx
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { RichCodeBlock } from './RichCodeBlock';
import { ActivityAccordion } from './ActivityAccordion';
import { User, Paperclip } from 'lucide-react';

const ROLE_META = {
  TechLead: { color: '#f59e0b', emoji: '👑', label: 'Tech Lead' },
  Architect: { color: '#8b5cf6', emoji: '🏛️', label: 'Architect' },
  FrontendDev: { color: '#06b6d4', emoji: '⚛️', label: 'Frontend Dev' },
  BackendDev: { color: '#10b981', emoji: '⚙️', label: 'Backend Dev' },
  Designer: { color: '#ec4899', emoji: '🎨', label: 'Designer' },
  QATester: { color: '#ef4444', emoji: '🧪', label: 'QA Tester' },
  system: { color: '#64748b', emoji: '🔔', label: 'System' },
  user: { color: '#3b82f6', emoji: '👤', label: 'You' },
};

export function ChatMessageItem({ msg, onApply }) {
  const isUser = msg.sender === 'user';
  const meta = ROLE_META[msg.sender] || ROLE_META.system;

  return (
    <div style={{
      marginBottom: '24px', paddingBottom: '24px', borderBottom: '1px solid var(--border-subtle)',
      display: 'flex', flexDirection: 'column', gap: '8px'
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{
          width: '24px', height: '24px', borderRadius: '6px',
          background: isUser ? '#3b82f6' : `linear-gradient(135deg, ${meta.color}44, ${meta.color}22)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px',
          color: isUser ? '#fff' : meta.color, border: isUser ? 'none' : `1px solid ${meta.color}55`
        }}>
          {isUser ? <User size={14} /> : meta.emoji}
        </div>
        <span style={{ fontSize: '13px', fontWeight: 600, color: isUser ? 'var(--text-primary)' : meta.color }}>
          {isUser ? 'You' : meta.label}
        </span>
        {msg.created_at && (
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {new Date(msg.created_at).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Content */}
      <div style={{
        paddingLeft: '32px', fontSize: '13.5px', lineHeight: '1.65', color: 'var(--text-primary)',
        wordBreak: 'break-word',
        ...(isUser ? {
          background: 'rgba(59, 130, 246, 0.05)', borderLeft: '3px solid #3b82f6',
          padding: '12px 16px', borderRadius: '0 8px 8px 0', marginLeft: '32px'
        } : {})
      }}>
        {isUser ? (
          <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code: ({node, inline, className, children, ...props}) => {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <RichCodeBlock language={match[1]} code={String(children).replace(/\n$/, '')} onApply={onApply} />
                ) : (
                  <code style={{background: 'rgba(0,0,0,0.2)', padding: '2px 4px', borderRadius: '4px', fontFamily: 'var(--font-mono)'}} {...props}>
                    {children}
                  </code>
                )
              }
            }}
          >
            {msg.content}
          </ReactMarkdown>
        )}

        {/* Attachments */}
        {msg.attachments && msg.attachments.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
            {msg.attachments.map((att, idx) => (
              att.url.match(/\.(jpeg|jpg|gif|png|webp)$/i) ? (
                <img key={idx} src={att.url} alt={att.filename} style={{ maxHeight: '150px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }} />
              ) : (
                <a key={idx} href={att.url} target="_blank" rel="noopener noreferrer" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', padding: '6px 12px', background: 'var(--bg-surface)', borderRadius: '6px', color: 'var(--text-primary)', textDecoration: 'none', border: '1px solid var(--border-subtle)' }}>
                  <Paperclip size={12} /> {att.filename}
                </a>
              )
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

---

### Task 3: Assemble `ChatInputDeck` & Refactor `FocusRoomView.jsx`

**Files:**
- Create: `frontend/src/components/chat/ChatInputDeck.jsx`
- Modify: `frontend/src/components/FocusRoomView.jsx`

**Interfaces:**
- Consumes: `MentionSuggestPopup`, `ChatMessageItem`
- Produces: Integrated Chat UI in `FocusRoomView.jsx`

- [ ] **Step 1: Write `ChatInputDeck.jsx`**

```jsx
import React, { useState, useRef, useEffect } from 'react';
import { Paperclip, Send, X } from 'lucide-react';
import { MentionSuggestPopup } from './MentionSuggestPopup';

export function ChatInputDeck({ onSendMessage, isSending }) {
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
    const lastWord = val.split(' ').pop();
    if (lastWord.startsWith('@')) {
      setMentionPos({ x: 20, y: 70 }); // Position relative to deck
    } else {
      setMentionPos(null);
    }
  };

  const insertMention = (role) => {
    const words = text.split(' ');
    words.pop(); // remove partial @
    setText(words.join(' ') + ` @${role} `);
    setMentionPos(null);
    textareaRef.current?.focus();
  };

  return (
    <div style={{ position: 'relative', padding: '16px', background: 'var(--bg-canvas)', borderTop: '1px solid var(--border-medium)' }}>
      {mentionPos && <MentionSuggestPopup x={mentionPos.x} y={mentionPos.y} onSelect={insertMention} />}
      
      <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '12px', padding: '8px' }}>
        <button style={{ padding: '8px', background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
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
```

- [ ] **Step 2: Refactor `FocusRoomView.jsx`**

Replace `ConsoleBubble` usage with the new `ChatMessageItem` and `ChatInputDeck`. Wrap the messages map in a max-width container (`max-width: 980px, margin: 0 auto`).

*Implementation Note:* Remove the `ConsoleBubble` and `CodeProposalCard` components from `FocusRoomView.jsx`. Import `ChatMessageItem` and `ChatInputDeck`. Update the `return` block inside the `team-console` tab content to use the new components.
