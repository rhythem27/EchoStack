import os
import uuid
import logging
import asyncio
import torch
from typing import Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from langchain.tools import tool
from langchain.agents import initialize_agent, AgentType
from langchain_google_genai import ChatGoogleGenerativeAI
from langfuse.decorators import observe, langfuse_context

from backend.config import settings
from backend.db import get_db_pool
from backend.auth import current_user_id, current_user_permissions

logger = logging.getLogger("backend-agent")

# Singleton holder for SentenceTransformer
_embed_model: Optional[SentenceTransformer] = None

def get_embedding_model() -> SentenceTransformer:
    """Loads the SentenceTransformer model on GPU/CUDA if available, otherwise CPU."""
    global _embed_model
    if _embed_model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Initializing SentenceTransformer (BAAI/bge-small-en-v1.5) on device: {device}")
        _embed_model = SentenceTransformer("BAAI/bge-small-en-v1.5", device=device)
    return _embed_model


@tool("query_user_analytics")
@observe(name="query_user_analytics", as_type="span")
async def query_user_analytics() -> str:
    """
    Queries the user analytics database to retrieve engagement insights,
    such as total interactions, top topics, and last update timestamp.
    """
    user_id = current_user_id.get()
    permissions = current_user_permissions.get()

    logger.info(f"Tool query_user_analytics called by user: {user_id}")

    langfuse_context.update_current_observation(
        input={"user_id": str(user_id) if user_id else None},
        metadata={"permission_checked": "can_query_analytics"}
    )

    # RBAC Validation
    if not permissions or not permissions.get("can_query_analytics", False):
        logger.warning(f"RBAC Denied for user {user_id} on query_user_analytics")
        return "Authorization Failure: User lacks required permission 'can_query_analytics'."

    if not user_id:
        return "Error: User context is missing."

    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT total_interactions, top_topics, last_updated_at FROM user_analytics WHERE user_id = $1",
                user_id
            )
            if not row:
                return f"No user analytics data found for user ID: {user_id}."

            import json
            top_topics_val = row["top_topics"]
            if isinstance(top_topics_val, str):
                topics_str = top_topics_val
            else:
                topics_str = json.dumps(top_topics_val)

            res = (
                f"User Analytics Insights:\n"
                f"- Total Interactions: {row['total_interactions']}\n"
                f"- Top Topics: {topics_str}\n"
                f"- Last Updated: {row['last_updated_at']}"
            )
            langfuse_context.update_current_observation(output=res)
            return res
    except Exception as e:
        logger.error(f"Error querying user analytics: {e}")
        return f"Error executing query: {str(e)}"


@tool("rag_knowledge_search")
@observe(name="rag_knowledge_search", as_type="retriever")
async def rag_knowledge_search(query: str) -> str:
    """
    Performs a hybrid vector & full-text keyword search against the knowledge base using
    Reciprocal Rank Fusion (RRF) to combine semantic similarity and exact term matching.
    """
    user_id = current_user_id.get()
    permissions = current_user_permissions.get()

    logger.info(f"Tool rag_knowledge_search called by user {user_id} with query: '{query}'")

    langfuse_context.update_current_observation(
        input={"query": query, "user_id": str(user_id) if user_id else None},
        metadata={"embedding_model": "BAAI/bge-small-en-v1.5", "search_mode": "hybrid_rrf", "top_k": 5}
    )

    # RBAC Validation
    if not permissions or not permissions.get("can_write_knowledge", False):
        logger.warning(f"RBAC Denied for user {user_id} on rag_knowledge_search")
        return "Authorization Failure: User lacks required permission 'can_write_knowledge'."

    if not user_id:
        return "Error: User context is missing."

    try:
        # Generate BGE-small embedding using CUDA-accelerated model
        embed_model = get_embedding_model()
        loop = asyncio.get_running_loop()
        query_vector = await loop.run_in_executor(
            None,
            lambda: embed_model.encode(query, convert_to_numpy=True).tolist()
        )
        vector_str = "[" + ",".join(map(str, query_vector)) + "]"

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # 1. Semantic Vector Cosine Distance Search
            vector_rows = await conn.fetch(
                """
                SELECT vk.id, vk.chunk_text, vk.metadata, 1 - (vk.embedding <=> $1::vector) AS similarity
                FROM vector_knowledge vk
                JOIN documents d ON vk.doc_id = d.id
                WHERE d.user_id = $2
                ORDER BY vk.embedding <=> $1::vector
                LIMIT 20
                """,
                vector_str, user_id
            )

            # 2. PostgreSQL Full-Text Keyword Search
            keyword_rows = await conn.fetch(
                """
                SELECT vk.id, vk.chunk_text, vk.metadata, ts_rank(vk.fts, plainto_tsquery('english', $1)) AS text_rank
                FROM vector_knowledge vk
                JOIN documents d ON vk.doc_id = d.id
                WHERE d.user_id = $2 AND (vk.fts @@ plainto_tsquery('english', $1) OR vk.chunk_text ILIKE '%' || $1 || '%')
                ORDER BY text_rank DESC
                LIMIT 20
                """,
                query, user_id
            )

            if not vector_rows and not keyword_rows:
                langfuse_context.update_current_observation(output="No matching knowledge base documents found.")
                return "No matching knowledge base documents found."

            # 3. Reciprocal Rank Fusion (RRF)
            import json
            scores = {}
            k_const = 60

            for rank, row in enumerate(vector_rows, start=1):
                doc_key = str(row['id'])
                meta = row['metadata']
                if isinstance(meta, str):
                    meta = json.loads(meta)
                scores[doc_key] = {
                    "chunk_text": row['chunk_text'],
                    "metadata": meta or {},
                    "vector_rank": rank,
                    "keyword_rank": None,
                    "similarity": float(row['similarity'])
                }

            for rank, row in enumerate(keyword_rows, start=1):
                doc_key = str(row['id'])
                meta = row['metadata']
                if isinstance(meta, str):
                    meta = json.loads(meta)
                if doc_key not in scores:
                    scores[doc_key] = {
                        "chunk_text": row['chunk_text'],
                        "metadata": meta or {},
                        "vector_rank": None,
                        "keyword_rank": rank,
                        "similarity": 0.0
                    }
                else:
                    scores[doc_key]["keyword_rank"] = rank

            # Compute combined RRF score
            for doc_key, item in scores.items():
                v_score = 1.0 / (k_const + item["vector_rank"]) if item["vector_rank"] is not None else 0.0
                k_score = 1.0 / (k_const + item["keyword_rank"]) if item["keyword_rank"] is not None else 0.0
                item["rrf_score"] = v_score + k_score

            # Sort candidate chunks by RRF score
            sorted_candidates = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)[:5]

            results = []
            for idx, item in enumerate(sorted_candidates):
                sec_title = item['metadata'].get('section_title', 'General')
                fmt = item['metadata'].get('file_format', 'txt').upper()
                results.append(
                    f"Result {idx+1} [Format: {fmt} | Section: {sec_title} | RRF Score: {item['rrf_score']:.4f}]:\n"
                    f"{item['chunk_text']}"
                )

            res_str = "\n\n".join(results)
            langfuse_context.update_current_observation(output=res_str)
            return res_str
    except Exception as e:
        logger.error(f"Error during Hybrid RAG search: {e}")
        return f"Error executing search: {str(e)}"


# Agent Executor cache
_agent_executor = None

def get_agent_executor():
    """Initializes the LangChain Agent Executor with structured chat tools."""
    global _agent_executor
    if _agent_executor is None:
        logger.info("Initializing LangChain ChatGoogleGenerativeAI and AgentExecutor...")
        
        # Use the configured Gemini model
        model_name = os.environ.get("GEMINI_LIVE_MODEL", "gemini-1.5-flash")
        
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.environ.get("GEMINI_API_KEY"),
            temperature=0.0
        )
        
        tools = [query_user_analytics, rag_knowledge_search]
        
        _agent_executor = initialize_agent(
            tools=tools,
            llm=llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True
        )
    return _agent_executor


@observe(name="system1-chat-agent", as_type="agent")
async def run_agent(message: str, user_id: Optional[str] = None, session_id: Optional[str] = None) -> str:
    """
    Executes the LangChain agent with Langfuse tracing.
    """
    uid = user_id or (str(current_user_id.get()) if current_user_id.get() else "guest")
    sid = session_id or f"session-{uuid.uuid4()}"

    langfuse_context.update_current_trace(
        name="system1-chat-agent",
        user_id=uid,
        session_id=sid,
        tags=["system-1", "langchain-agent", "chat"],
        input=message
    )

    # Retrieve the LangChain callback handler registered under the active Langfuse trace
    langfuse_handler = langfuse_context.get_current_langchain_handler()
    callbacks = [langfuse_handler] if langfuse_handler else []

    agent_executor = get_agent_executor()
    
    logger.info(f"Running agent for query: {message}")
    response = await agent_executor.ainvoke(
        {"input": message},
        config={"callbacks": callbacks}
    )
    out_str = response.get("output", "")
    langfuse_context.update_current_trace(output=out_str)
    return out_str
