# Phase 6: Embedding-Based Semantic Chunking

This task document details upgrading the document ingestion pipeline in `worker.py` from fixed header-only splitting to embedding-driven semantic chunking.

---

## 1. Objectives
- Replace rigid text splitting with dynamic semantic boundary detection using embedding similarity thresholds (`semchunk` / cosine distance transitions).
- Avoid splitting continuous thoughts, paragraphs, or sentence groups mid-concept.
- Improve vector retrieval accuracy and context quality in RAG search queries.

---

## 2. Technical Tasks

### 2.1 Embedding Semantic Splitter Engine ([backend/worker.py](file:///c:/git-hub/EchoStack/backend/worker.py))
- [ ] Integrate semantic chunking module (`semchunk` or sentence embedding boundary analyzer).
- [ ] Calculate sentence-level embedding vectors and evaluate cosine distance between adjacent sentence blocks.
- [ ] Split documents at natural semantic shift points (where similarity drops below a dynamic percentile threshold).

### 2.2 Ingestion Worker Pipeline Integration
- [ ] Update `IngestionWorker.process_document()` to use the new semantic chunking engine after Docling layout parsing.
- [ ] Retain markdown header context in chunk metadata (`Header_1`, `section_title`).
- [ ] Measure chunk length variance and semantic coherence score against fixed-length chunking.

---

## 3. Verification Criteria
- [ ] Document ingestion produces semantically cohesive text chunks rather than arbitrary line/length cuts.
- [ ] Hybrid vector search queries return higher relevance context scores.
