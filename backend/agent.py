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
async def query_user_analytics() -> str:
    """
    Queries the user analytics database to retrieve engagement insights,
    such as total interactions, top topics, and last update timestamp.
    """
    user_id = current_user_id.get()
    permissions = current_user_permissions.get()

    logger.info(f"Tool query_user_analytics called by user: {user_id}")

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
            # top_topics can be a string or a list/dict depending on how asyncpg parses JSONB
            top_topics_val = row["top_topics"]
            if isinstance(top_topics_val, str):
                topics_str = top_topics_val
            else:
                topics_str = json.dumps(top_topics_val)

            return (
                f"User Analytics Insights:\n"
                f"- Total Interactions: {row['total_interactions']}\n"
                f"- Top Topics: {topics_str}\n"
                f"- Last Updated: {row['last_updated_at']}"
            )
    except Exception as e:
        logger.error(f"Error querying user analytics: {e}")
        return f"Error executing query: {str(e)}"


@tool("rag_knowledge_search")
async def rag_knowledge_search(query: str) -> str:
    """
    Performs a semantic similarity search against the vector knowledge base using the query text
    to retrieve relevant document chunks uploaded by the user.
    """
    user_id = current_user_id.get()
    permissions = current_user_permissions.get()

    logger.info(f"Tool rag_knowledge_search called by user {user_id} with query: '{query}'")

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
        # SentenceTransformer encode is a blocking operation, run in executor
        query_vector = await loop.run_in_executor(
            None,
            lambda: embed_model.encode(query, convert_to_numpy=True).tolist()
        )
        vector_str = "[" + ",".join(map(str, query_vector)) + "]"

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Query pgvector HNSW index for cosine distance (similarity = 1 - cosine_distance)
            # Filter results by the user's documents to enforce data privacy
            rows = await conn.fetch(
                """
                SELECT vk.chunk_text, 1 - (vk.embedding <=> $1::vector) AS similarity
                FROM vector_knowledge vk
                JOIN documents d ON vk.doc_id = d.id
                WHERE d.user_id = $2
                ORDER BY vk.embedding <=> $1::vector
                LIMIT $3
                """,
                vector_str, user_id, 5
            )

            if not rows:
                return "No matching knowledge base documents found."

            results = []
            for idx, row in enumerate(rows):
                results.append(f"Result {idx+1} (Similarity: {row['similarity']:.4f}):\n{row['chunk_text']}")

            return "\n\n".join(results)
    except Exception as e:
        logger.error(f"Error during RAG search: {e}")
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
        
        # We use a structured chat agent which is extremely stable and handles multiple tools well
        _agent_executor = initialize_agent(
            tools=tools,
            llm=llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True
        )
    return _agent_executor


@observe()
async def run_agent(message: str) -> str:
    """
    Executes the LangChain agent with Langfuse tracing.
    """
    # Retrieve the LangChain callback handler registered under the active Langfuse trace
    langfuse_handler = langfuse_context.get_current_langchain_handler()
    callbacks = [langfuse_handler] if langfuse_handler else []

    agent_executor = get_agent_executor()
    
    logger.info(f"Running agent for query: {message}")
    response = await agent_executor.ainvoke(
        {"input": message},
        config={"callbacks": callbacks}
    )
    return response["output"]
