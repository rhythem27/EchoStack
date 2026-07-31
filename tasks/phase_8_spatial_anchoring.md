# Phase 8: Real-Time Vision Spatial Anchoring

This task document details real-time spatial bounding box overlays on the video stream canvas when the AI agent identifies objects, diagrams, or UI components.

---

## 1. Objectives
- Enable the Gemini Live agent to return normalized spatial coordinates (`[ymin, xmin, ymax, xmax]`) via tool call or structured output.
- Render interactive highlight boxes and labels on the user's video feed overlay in real-time.
- Support spatial visual Q&A (e.g., user points camera at a circuit or diagram and the AI highlights specific target parts).

---

## 2. Technical Tasks

### 2.1 Spatial Bounding Box Tool Definition ([backend/websocket.py](file:///c:/git-hub/EchoStack/backend/websocket.py))
- [ ] Define `highlight_spatial_object` tool declaration for Gemini Live API:
  - Input parameters: `label` (string), `box_2d` (`[ymin, xmin, ymax, xmax]` normalized 0-1000 integer array).
- [ ] Forward spatial highlight payloads to the WebSocket client as visual overlay events.

### 2.2 Frontend Canvas Bounding Box Overlay ([frontend/src/components/VisionOverlay.jsx](file:///c:/git-hub/EchoStack/frontend/src/components/VisionOverlay.jsx))
- [ ] Build an SVG/Canvas overlay component over the live camera video stream.
- [ ] Convert normalized 0-1000 coordinates to responsive element pixel coordinates (`width`, `height`).
- [ ] Draw glowing animated bounding boxes with label tags and auto-fade timeouts (e.g. 4 seconds).

---

## 3. Verification Criteria
- [ ] Asking *"Where is object X in the camera view?"* triggers the tool call and draws a glowing highlight box over object X in the video feed.
