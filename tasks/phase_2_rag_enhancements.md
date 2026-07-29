# Phase 2: RAG Pipeline & Knowledge Base Upgrades

This task document outlines the enhancements required for document parsing, hybrid vector/keyword search, and knowledge base management in EchoStack.

---

## 1. Objectives
- Expand document parsing beyond PDFs to support `.docx`, `.txt`, `.csv`, `.md`, and `.pptx`.
- Implement Hybrid Search (combining PostgreSQL full-text search `tsvector` with `pgvector` HNSW cosine similarity).
- Build a Knowledge Base Management UI modal for inspecting document chunks and vector scores.

---

## 2. Technical Tasks

### 2.1 Multi-Format Ingestion Worker ([backend/worker.py](file:///c:/git-hub/EchoStack/backend/worker.py))
- [x] Update `/upload-document` API endpoint to accept `.docx`, `.txt`, `.csv`, `.md`, `.pptx`, and `.pdf` extensions.
- [x] Configure **IBM Docling `DocumentConverter`** format handlers for Office formats and markdown tables.
- [x] Implement chunk-level metadata tagging (page numbers, section titles, file formats).

### 2.2 Hybrid Vector + Keyword Search ([backend/agent.py](file:///c:/git-hub/EchoStack/backend/agent.py))
- [x] Add PostgreSQL full-text search index (`tsvector`) to `vector_knowledge`.
- [x] Implement **Reciprocal Rank Fusion (RRF)** in `rag_knowledge_search()`:
  - Query 1: `pgvector` HNSW cosine distance (`embedding <=> query_vector`).
  - Query 2: Full-text match (`to_tsquery('english', query)`).
  - Merge and rank top 5 combined results.

### 2.3 Knowledge Base Manager UI ([frontend/src/components/KnowledgeManager.jsx](file:///c:/git-hub/EchoStack/frontend/src/components/KnowledgeManager.jsx))
- [x] Create a Document Knowledge Explorer modal:
  - View document chunk breakdown and semantic similarity scores.
  - Delete individual documents or clear knowledge collections.
  - Re-index documents on demand.

---

## 3. Verification Criteria
- [x] System successfully processes `.docx` and `.csv` files into vector knowledge.
- [x] RAG queries return hybrid-ranked chunks combining semantic similarity and exact keyword matching.
- [x] Users can delete or re-index documents through the UI.
