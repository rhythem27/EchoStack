# Phase 3: Multimodal Vision & Live Tools Integration

This task document details the additions for streaming camera/screen frames and executing expanded agent tools within live Gemini sessions.

---

## 1. Objectives
- Enable live camera and screen capture streaming over WebSocket to Gemini 3.1 Live API.
- Add real-time web search and code execution tools to the agent.
- Enhance tool calling feedback in the frontend user interface.

---

## 2. Technical Tasks

### 2.1 Multimodal Video & Image Proxy ([backend/websocket.py](file:///c:/git-hub/EchoStack/backend/websocket.py))
- [ ] Extend WebSocket protocol to handle `video_frame` Base64 JPEG payloads.
- [ ] Forward video frames to `gemini_session.send_realtime_input(media_chunks=[types.Blob(mime_type="image/jpeg", data=raw_bytes)])`.
- [ ] Add client-side camera/screen capture toggle button in React UI.

### 2.2 Expanded Agent Tools ([backend/agent.py](file:///c:/git-hub/EchoStack/backend/agent.py))
- [ ] Add Google Search / Tavily API tool declaration to `live_config.tools`.
- [ ] Add Python Code Interpreter sandbox tool for numerical calculations.
- [ ] Trace tool execution with `@observe(name="tool-execution")`.

### 2.3 Live Tool Visualizer UI ([frontend/src/App.jsx](file:///c:/git-hub/EchoStack/frontend/src/App.jsx))
- [ ] Display an animated tool badge when Gemini executes mid-speech tools (`Searching Knowledge...`, `Executing Analytics...`).
- [ ] Show raw JSON tool call inputs/outputs in the Stream Activity logger.

---

## 3. Verification Criteria
- [ ] Users can toggle screen or webcam sharing and ask Gemini questions about visual content.
- [ ] Gemini successfully triggers web search tools mid-speech and synthesizes verbal answers.
