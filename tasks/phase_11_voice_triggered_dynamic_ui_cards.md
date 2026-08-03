# Phase 11: Voice-Triggered Dynamic UI Cards (Dual-Payload Generative UI Protocol)

This task document outlines the design and implementation of **Voice-Triggered Dynamic UI Cards** in EchoStack. This feature bridges voice interaction and visual UI by emitting dual-payload events over the active WebSocket connection when Gemini Live executes backend tools.

While Gemini speaks a natural language summary to the user via audio, the backend simultaneously pushes structured JSON UI card payloads to the React frontend, dynamically mounting interactive widgets (charts, metrics grids, document cards) directly in the chat timeline.

---

## 1. End-to-End Execution Flow

```text
[User speaks: "Show my usage metrics"] 
                  │
                  ▼
         [React Frontend] (Audio PCM via WebRTC/WS)
                  │
                  ▼
         [FastAPI WS Proxy] ──► [Gemini Live API]
                                      │
                                      ▼ (Gemini invokes tool)
                             [backend/agent.py]
                        (query_user_analytics Tool)
                                      │
                                      ▼
                      1. Queries Postgres / PySpark
                      2. Generates Dual Payload
                                  /       \
                                 /         \
   (Text summary for voice)     /           \  (Structured JSON for UI)
                               ▼             ▼
                      [Gemini Live]    [WebSocket Event]
                           │                 │
                           ▼                 ▼
                     Audio Stream    JSON UI Payload
                           │                 │
                           └────────┬────────┘
                                    ▼
                             [React Frontend]
               (Voice plays + Interactive Card mounts in chat)
```

---

## 2. Technical Tasks

### 2.1 Backend Dual-Payload Tool Protocol ([backend/agent.py](file:///c:/git-hub/EchoStack/backend/agent.py))
- [ ] Define standardized `UICardPayload` schema:
  - `component`: `"AnalyticsMetricsCard"` | `"DocumentSearchCard"` | `"PythonResultCard"`.
  - `data`: Component-specific structured dataset payload.
- [ ] Update `query_user_analytics` tool to return dual payload (spoken voice summary string + `ui_card` JSON metadata).
- [ ] Update `rag_knowledge_search` tool to return document chunk search results with a `DocumentSearchCard` UI payload.
- [ ] Update `python_code_interpreter` tool to return formatted math/code outputs with a `PythonResultCard` UI payload.

### 2.2 WebSocket Event Multiplexing ([backend/websocket.py](file:///c:/git-hub/EchoStack/backend/websocket.py))
- [ ] Update `execute_live_tool` execution loop to intercept dual-payload tool responses.
- [ ] Parse `ui_card` payloads and broadcast a `RENDER_UI_CARD` WebSocket message (`{"type": "RENDER_UI_CARD", "component": "...", "data": {...}}`) directly to the connected client.
- [ ] Extract the clean `voice_text` portion and pass it back to Gemini Live for natural speech synthesis.

### 2.3 Frontend Dynamic Component Dispatcher ([frontend/src/App.jsx](file:///c:/git-hub/EchoStack/frontend/src/App.jsx))
- [ ] Add `RENDER_UI_CARD` WebSocket message listener in `ws.onmessage`.
- [ ] Build dynamic UI card components:
  - **`AnalyticsMetricsCard`**: Visual metrics summary displaying total interactions, engagement progress bars, top topics badges, and sync timestamps.
  - **`DocumentSearchCard`**: Clickable search result cards showing document titles, section headings, format badges, and relevance scores.
  - **`PythonResultCard`**: Code execution card with syntax highlighting, output buffers, and a quick copy button.
- [ ] Mount dynamic card elements inline within the live transcript stream when received over WebSockets.

---

## 3. Verification Criteria

- [ ] Asking *"Show my usage metrics"* via voice causes Gemini to speak a voice summary while an interactive `AnalyticsMetricsCard` mounts live in the chat.
- [ ] Asking *"Search knowledge base for deployment docs"* mounts clickable `DocumentSearchCard` items in the chat.
- [ ] Executing a python code query renders a formatted `PythonResultCard`.
- [ ] Dual-payload execution causes 0 additional latency overhead or WebSocket disconnects.
