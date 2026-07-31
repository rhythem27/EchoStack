# Phase 7: Structural Video Frame Deduplication (SSIM)

This task document outlines client-side frame deduplication to optimize WebRTC video streaming latency and token consumption.

---

## 1. Objectives
- Implement Structural Similarity Index (SSIM) or pixel-difference frame comparison on the React canvas.
- Only transmit base64 video frames over WebSockets when significant scene motion or visual content changes occur.
- Drastically reduce Gemini Live vision API token costs and bandwidth overhead.

---

## 2. Technical Tasks

### 2.1 Canvas Frame Deduplication Utility ([frontend/src/utils/frameDeduplicator.js](file:///c:/git-hub/EchoStack/frontend/src/utils/frameDeduplicator.js))
- [x] Implement a lightweight image pixel-difference / SSIM similarity comparator in WebAssembly or Canvas API:
  - Downsample camera frames to a low-res matrix (e.g., 64x64).
  - Compute structural similarity or mean square error (MSE) against the previously sent frame.
  - Expose a configurable threshold parameter (e.g., `DIFF_THRESHOLD = 0.15`).

### 2.2 Integration with Live Vision Stream ([backend/websocket.py](file:///c:/git-hub/EchoStack/backend/websocket.py) & Frontend)
- [x] Wrap canvas frame capture loop in React frontend with `shouldSendFrame(currentCanvas)` filter.
- [x] Log frame skip vs frame send metrics in client dev console (e.g. *"Skipped 82% identical static frames"*).
- [x] Verify continuous smooth AI vision understanding when user shows dynamic motion vs static objects.

---

## 3. Verification Criteria
- [x] Static camera feed streams only 1 initial frame and skips redundant frames until motion occurs.
- [x] WebSocket traffic drops significantly while maintaining instant visual response on physical movement.
