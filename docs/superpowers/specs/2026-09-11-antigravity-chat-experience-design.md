# Antigravity Chat Experience Design Specification

## 1. Executive Summary & Problem Statement

### 1.1 Background & Pain Points
The Team Console within the AI Office PM Dashboard previously utilized a classic mobile-messaging bubble layout (`maxWidth: '75%'`, user right-aligned in blue gradients, agent left-aligned). While functional for short text, this layout creates significant friction during technical interactions:
- **Eye Strain & Cramped Space**: Long technical markdown explanations, multi-file architectural breakdowns, and code snippets are squeezed into narrow 75% bubbles with unnatural line breaks.
- **Log Pollution**: Detailed background logs (thinking processes, test executions, directory scans) flood the chat window as continuous text walls.
- **Code Block Limitations**: Code blocks lack syntax headers, quick copy actions, or direct one-click "Apply to File" capabilities.
- **Agent Orchestration**: Directing tasks to specific agents requires manual typing without autocomplete or suggestion support.

### 1.2 Objective
Redesign and upgrade the Team Console into a full-fidelity **Antigravity IDE Chat Experience**:
- **Full-Width Linear Stream**: Single-column reading flow (100% width with optimal reading line-length) ensuring zero visual fatigue.
- **Collapsible Activity Accordions**: Background operations, thinking steps, and test suites are neatly folded into sleek interactive pills.
- **Rich Code Blocks**: Top headers displaying syntax languages/filenames, one-click copy buttons, and direct file modification buttons.
- **Interactive Mention Autocomplete**: Fast popup recommendations for `@TechLead`, `@FrontendDev`, `@BackendDev`, etc.
- **Docked Input Deck**: Modern bottom-docked textarea supporting clipboard image paste, attachment chips, and keyboard shortcuts (`Shift+Enter` for newline, `Enter` to send).

---

## 2. Component Architecture & Modular Layout

To maintain high maintainability and avoid further bloat to `FocusRoomView.jsx`, the chat system is decomposed into specialized components under `frontend/src/components/chat/`:

```
frontend/src/components/chat/
├── ChatStreamView.jsx        # Main full-width linear container & smart auto-scroll
├── ChatMessageItem.jsx       # Individual message item (User block vs Agent doc block)
├── ActivityAccordion.jsx     # Collapsible status/log pill (Thinking, Test run, Tool execution)
├── RichCodeBlock.jsx         # Code block with language header, copy button & apply trigger
├── MentionSuggestPopup.jsx   # Keyboard-navigable @mention & /command autocomplete
└── ChatInputDeck.jsx         # Fixed bottom deck with auto-expanding input & clipboard preview
```

### 2.1 Visual Hierarchy & Styling Tokens

#### Container (`ChatStreamView.jsx`)
- Full width with a maximum reading boundary (`max-width: 980px; margin: 0 auto;`).
- Consistent vertical padding (`padding: 24px 20px;`).
- Smart auto-scrolling: automatically scrolls to the bottom when a new message arrives, unless the user has scrolled up to inspect previous messages.

#### User Message Block (`ChatMessageItem.jsx`)
- Distinct subtle background (`rgba(59, 130, 246, 0.05)`) with a clean blue left accent border (`border-left: 3px solid #3b82f6`).
- Sender header: `👤 You` badge with formatted timestamp.
- Image and file attachments rendered as clean preview tiles with zoom/download support.

#### Agent Message Block (`ChatMessageItem.jsx`)
- Role badge with official color and emoji (e.g., `👑 Tech Lead` in amber `#f59e0b`, `⚛️ Frontend Dev` in cyan `#06b6d4`).
- Document-grade typography:
  - Font size: `13.5px`, line-height: `1.65`.
  - Headers (`H1`, `H2`, `H3`): Clear weight hierarchy with subtle bottom dividers for `H1` and `H2`.
  - Unordered/Ordered lists: Clean indentation (`24px`), custom bullet styling.
  - Blockquotes: Styled callouts with left accent bars.

---

## 3. Detailed Component Specifications

### 3.1 Rich Code Block (`RichCodeBlock.jsx`)
Replaces standard markdown code blocks with an IDE-grade interactive container:
- **Header Bar**:
  - Left: Language identifier pill (e.g., `typescript`, `python`, `css`) or detected target filename.
  - Right:
    - **Copy Button**: Copies code to clipboard with visual feedback (`✓ Copied!`).
    - **Apply to File Button**: Triggered when code block specifies a target file or when attached to a code proposal. Calls `/api/projects/{id}/apply-change`.
- **Code Container**:
  - Dark theme background (`#0d1117` / `#0a0d14`).
  - Monospace font (`JetBrains Mono`, `Fira Code`, `ui-monospace`).
  - Horizontal overflow handled with custom sleek scrollbar.

### 3.2 Activity & Tool Accordion (`ActivityAccordion.jsx`)
Used for non-conversational operations (Agent thoughts, test runs, linting, tool invocations):
- **Collapsed Bar**:
  - Status indicator (spinner when active, checkmark when succeeded, alert when failed).
  - Title badge: e.g. `▶ 🧠 Thought Process (3 steps)` or `✓ 🧪 Tests Passed (4/4)`.
  - Elapsed duration / timestamp badge.
- **Expanded Panel**:
  - Raw stdout/stderr logs in monospaced terminal styling.
  - Re-collapsible upon clicking anywhere on the header bar.

### 3.3 Mention Autocomplete Popup (`MentionSuggestPopup.jsx`)
- Activated whenever the user types `@` or `/` inside the input deck.
- Shows agent roster with role colors, emojis, and brief responsibilities:
  - `@TechLead` 👑 - Architecture & Project Orchestration
  - `@Architect` 🏛️ - System Design & Core Modules
  - `@FrontendDev` ⚛️ - React UI, Styling & Components
  - `@BackendDev` ⚙️ - FastAPI, Python Services & DB
  - `@Designer` 🎨 - Design System & Visuals
  - `@QATester` 🧪 - Automated Tests & Quality Assurance
  - `@Team` 📢 - Broadcast directive to entire team
- Interaction:
  - Keyboard: `ArrowUp`, `ArrowDown` to navigate; `Enter` or `Tab` to select; `Escape` to close.
  - Mouse: Click item to insert mention into cursor position.

### 3.4 Docked Input Deck (`ChatInputDeck.jsx`)
- Pinned at the bottom of the Team Console.
- Auto-expanding `textarea` (from 42px up to 180px).
- Clipboard listener for image paste (`event.clipboardData.items`):
  - Converts pasted image to file attachment.
  - Displays thumbnail chip with `✕` remove button before sending.
- Keyboard shortcuts:
  - `Enter`: Submit message.
  - `Shift + Enter`: Insert new line.
- Action buttons: File attach (`📎`), Send button (`➤`).

---

## 4. Data Flow & Integration

```
+-------------------------------------------------------------------------------+
|                             ChatInputDeck.jsx                                 |
|  [Text Message] + [Clipboard/Attached Images] + [Target Agent @Role]          |
+-------------------------------------------------------------------------------+
                                      |
                                      v (POST /api/projects/{id}/console/chat)
+-------------------------------------------------------------------------------+
|                               routes.py                                       |
|  - Creates user message in ConsoleService                                     |
|  - Broadcasts CONSOLE_MESSAGE immediately (User sees message instantly)       |
|  - Sets target agent to THINKING (broadcasts AGENT_STATE_UPDATE)              |
|  - Spawns background task to query agent runner                               |
+-------------------------------------------------------------------------------+
                                      |
                                      v (WebSocket CONSOLE_MESSAGE & STATE)
+-------------------------------------------------------------------------------+
|                            ChatStreamView.jsx                                 |
|  - Live optimistic render of user message                                     |
|  - Thinking status pill with spinner                                          |
|  - Seamlessly renders Agent markdown response, code blocks & accordions       |
+-------------------------------------------------------------------------------+
```

---

## 5. Error Handling & Edge Cases

1. **Markdown Parse Safety**:
   - Wrap markdown rendering with React Error Boundary to avoid rendering crashes on unexpected syntax.
2. **Clipboard Paste Validation**:
   - Validate MIME types (images, PDFs, text files). Max file size limit: 10MB per attachment.
3. **Network Failure & Retries**:
   - If `/api/projects/{id}/console/chat` fails, display an inline error bar with a `↻ Retry` action preserving the original prompt.
4. **Context Overflow Protection**:
   - Maintain the existing `ConsoleService.get_recent_context` compaction so long histories are automatically summarized without crashing the agent context window.

---

## 6. Verification & Testing Plan

### 6.1 Visual & Layout Verification
- Verify that messages span the full width of the console container rather than being constrained to 75% bubbles.
- Verify that typography hierarchy (`H1`, `H2`, `H3`, lists, tables) renders with crisp readability and zero eye strain.

### 6.2 Interactive Feature Verification
- **Code Blocks**:
  - Test the "Copy Code" button and verify that the clipboard contains the exact code snippet.
  - Test the "Apply to File" button on code blocks with filename annotations.
- **Activity Accordion**:
  - Send a command that triggers thoughts or test runs and verify that logs are neatly folded inside the accordion.
  - Click to expand and collapse the accordion.
- **Mention Autocomplete**:
  - Type `@` in the input deck and verify that the popup appears.
  - Navigate with keyboard arrows and press `Enter` to insert the selected role.
- **Clipboard Image Paste**:
  - Copy an image from the clipboard, paste (`Cmd+V` / `Ctrl+V`) into the input deck, verify thumbnail appears, and send.
