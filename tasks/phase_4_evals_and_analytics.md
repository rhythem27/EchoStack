# Phase 4: Langfuse Evals & Analytics Dashboard

This task document outlines the evaluation pipelines, LLM-as-a-Judge evaluators, and real-time dashboard analytics UI in EchoStack.

---

## 1. Objectives
- Implement automated LLM-as-a-Judge evaluations using Langfuse datasets and scores.
- Build an interactive Analytics & Metrics Dashboard UI in the React client.
- Add operational alert webhooks for latency or quality degradation.

---

## 2. Technical Tasks

### 2.1 Automated Langfuse Evaluation Pipeline ([backend/agent.py](file:///c:/git-hub/EchoStack/backend/agent.py))
- [ ] Utilize **Langfuse AI Skill** ([.agents/skills/langfuse/SKILL.md](file:///c:/git-hub/EchoStack/.agents/skills/langfuse/SKILL.md)) for trace scoring.
- [ ] Implement an automated LLM-as-a-Judge score evaluator for RAG faithfulness and answer relevance.
- [ ] Export trace data into Langfuse Datasets for regression testing.

### 2.2 Analytics Dashboard UI ([frontend/src/components/AnalyticsDashboard.jsx](file:///c:/git-hub/EchoStack/frontend/src/components/AnalyticsDashboard.jsx))
- [ ] Render interactive charts (Recharts / Chart.js) for `user_analytics`:
  - Total interactions over time.
  - Top topics distribution pie chart.
  - Latency RTT histogram (WebSocket voice delays).
  - Telemetry cost & token consumption breakdown.

### 2.3 Production Observability & Alerting
- [ ] Configure alert thresholds for trace latencies > 2000ms.
- [ ] Flush telemetry data gracefully on process shutdown.

---

## 3. Verification Criteria
- [ ] Traces in Langfuse UI automatically feature relevance and faithfulness scores.
- [ ] React frontend renders interactive charts from PySpark `user_analytics` data.
