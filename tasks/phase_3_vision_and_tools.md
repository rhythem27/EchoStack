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
- [x] Extend WebSocket protocol to handle `video_frame` Base64 JPEG payloads.
- [x] Forward video frames to `gemini_session.send_realtime_input(media_chunks=[types.Blob(mime_type="image/jpeg", data=raw_bytes)])`.
- [x] Add client-side camera/screen capture toggle button in React UI.

### 2.2 Expanded Agent Tools ([backend/agent.py](file:///c:/git-hub/EchoStack/backend/agent.py))
- [x] Add Google Search / Tavily API tool declaration to `live_config.tools`.
- [x] Add Python Code Interpreter sandbox tool for numerical calculations.
- [x] Trace tool execution with `@observe(name="tool-execution")`.

### 2.3 Live Tool Visualizer UI ([frontend/src/App.jsx](file:///c:/git-hub/EchoStack/frontend/src/App.jsx))
- [x] Display an animated tool badge when Gemini executes mid-speech tools (`Searching Knowledge...`, `Executing Analytics...`).
- [x] Show raw JSON tool call inputs/outputs in the Stream Activity logger.

---

## 3. Verification Criteria
- [x] Users can toggle screen or webcam sharing and ask Gemini questions about visual content.
- [x] Gemini successfully triggers web search tools mid-speech and synthesizes verbal answers.
