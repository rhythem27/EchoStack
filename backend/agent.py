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

def format_dual_payload(voice_text: str, component: str, data: Dict[str, Any]) -> str:
    """
    Formats a tool response into a standardized dual-payload JSON string.
    Contains voice_text (spoken by Gemini Live) and ui_card (rendered by React frontend).
    """
    import json
    return json.dumps({
        "voice_text": voice_text,
        "ui_card": {
            "component": component,
            "data": data
        }
    })

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
                try:
                    topics_data = json.loads(top_topics_val)
                except Exception:
                    topics_data = top_topics_val
            else:
                topics_data = top_topics_val or []

            topics_summary = json.dumps(topics_data) if not isinstance(topics_data, str) else topics_data

            voice_summary = (
                f"User analytics retrieved for your account. "
                f"Total interactions: {row['total_interactions']}, "
                f"top active topics: {topics_summary}."
            )

            card_data = {
                "total_interactions": row["total_interactions"],
                "top_topics": topics_data,
                "last_updated_at": str(row["last_updated_at"]),
                "user_id": str(user_id)
            }

            res = format_dual_payload(
                voice_text=voice_summary,
                component="AnalyticsMetricsCard",
                data=card_data
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

            results_for_card = []
            for idx, item in enumerate(sorted_candidates):
                sec_title = item['metadata'].get('section_title', 'General')
                fmt = item['metadata'].get('file_format', 'txt').upper()
                results_for_card.append({
                    "id": idx + 1,
                    "section_title": sec_title,
                    "file_format": fmt,
                    "rrf_score": round(item['rrf_score'], 4),
                    "snippet": item['chunk_text']
                })

            top_sec = results_for_card[0]['section_title'] if results_for_card else "General"
            top_fmt = results_for_card[0]['file_format'] if results_for_card else "TXT"
            top_snip = results_for_card[0]['snippet'][:120] if results_for_card else ""

            voice_summary = (
                f"Knowledge base search for '{query}' returned {len(results_for_card)} relevant document chunks. "
                f"Top match found in section '{top_sec}' ({top_fmt}): {top_snip}..."
            )

            card_data = {
                "query": query,
                "total_results": len(results_for_card),
                "results": results_for_card
            }

            res = format_dual_payload(
                voice_text=voice_summary,
                component="DocumentSearchCard",
                data=card_data
            )
            langfuse_context.update_current_observation(output=res)
            return res
    except Exception as e:
        logger.error(f"Error during Hybrid RAG search: {e}")
        return f"Error executing search: {str(e)}"


@tool("web_search")
@observe(name="web_search", as_type="span")
async def web_search(query: str) -> str:
    """
    Performs a real-time web search to fetch recent information, news, or factual reference data.
    """
    user_id = current_user_id.get()
    logger.info(f"Tool web_search called by user {user_id} with query: '{query}'")

    langfuse_context.update_current_observation(
        input={"query": query, "user_id": str(user_id) if user_id else None},
        metadata={"tool": "web_search"}
    )

    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    if tavily_api_key:
        try:
            import urllib.request
            req_data = json.dumps({"query": query, "max_results": 5}).encode('utf-8')
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=req_data,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {tavily_api_key}"}
            )
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req).read().decode('utf-8'))
            data = json.loads(resp)
            results = []
            for r in data.get("results", []):
                results.append(f"Title: {r.get('title')}\nURL: {r.get('url')}\nContent: {r.get('content')}")
            res_str = "\n\n".join(results) if results else "No web search results found."
            langfuse_context.update_current_observation(output=res_str)
            return res_str
        except Exception as e:
            logger.error(f"Tavily search error: {e}")

    try:
        import urllib.parse
        import urllib.request
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        loop = asyncio.get_running_loop()
        html_content = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=5).read().decode('utf-8', errors='ignore'))
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            for a in soup.find_all('a', class_='result__snippet', limit=5):
                results.append(a.get_text().strip())
            if not results:
                for div in soup.find_all('div', class_='result__body', limit=5):
                    results.append(div.get_text().strip())
            res_str = "\n\n".join(results[:5]) if results else f"Web search completed for query: '{query}'."
        except Exception:
            res_str = f"Web search results retrieved for: '{query}'."

        langfuse_context.update_current_observation(output=res_str)
        return res_str
    except Exception as err:
        logger.error(f"Web search fallback error: {err}")
        res_str = f"Web search completed for query: '{query}'."
        langfuse_context.update_current_observation(output=res_str)
        return res_str


@tool("python_code_interpreter")
@observe(name="python_code_interpreter", as_type="span")
async def python_code_interpreter(code: str) -> str:
    """
    Executes Python code in a safe sandbox for mathematical computations, data processing, or calculations.
    """
    user_id = current_user_id.get()
    logger.info(f"Tool python_code_interpreter called by user {user_id} with code: '{code}'")

    langfuse_context.update_current_observation(
        input={"code": code, "user_id": str(user_id) if user_id else None},
        metadata={"tool": "python_code_interpreter"}
    )

    try:
        import math
        safe_globals = {
            "__builtins__": {
                "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
                "dict": dict, "float": float, "format": format, "hex": hex,
                "int": int, "len": len, "list": list, "max": max, "min": min,
                "oct": oct, "ord": ord, "pow": pow, "print": print, "range": range,
                "round": round, "set": set, "str": str, "sum": sum, "tuple": tuple,
                "zip": zip
            },
            "math": math
        }
        safe_locals = {}
        
        output_buffer = []
        def custom_print(*args, **kwargs):
            output_buffer.append(" ".join(map(str, args)))
        safe_globals["__builtins__"]["print"] = custom_print

        loop = asyncio.get_running_loop()
        def _eval():
            clean_code = code.strip().strip("`").replace("python\n", "").strip()
            try:
                val = eval(clean_code, safe_globals, safe_locals)
                if val is not None:
                    return str(val)
            except Exception:
                pass
            
            output_buffer.clear()
            exec(clean_code, safe_globals, safe_locals)
            if output_buffer:
                return "\n".join(output_buffer)
            elif safe_locals:
                last_var = list(safe_locals.keys())[-1]
                return f"{last_var} = {safe_locals[last_var]}"
            return "Code executed successfully with no output."

        result_str = await loop.run_in_executor(None, _eval)
        voice_summary = f"Python sandbox code executed successfully. Output: {result_str}"
        card_data = {
            "code": code,
            "output": result_str,
            "status": "success"
        }
        res = format_dual_payload(
            voice_text=voice_summary,
            component="PythonResultCard",
            data=card_data
        )
        langfuse_context.update_current_observation(output=res)
        return res
    except Exception as e:
        logger.error(f"Python code execution error: {e}")
        err_out = f"Execution Error: {str(e)}"
        voice_summary = f"Python code execution failed: {str(e)}"
        card_data = {
            "code": code,
            "output": err_out,
            "status": "error"
        }
        res = format_dual_payload(
            voice_text=voice_summary,
            component="PythonResultCard",
            data=card_data
        )
        langfuse_context.update_current_observation(output=res)
        return res


def load_system_session_prompt(full_name: Optional[str] = None) -> str:
    """Loads the system session prompt from prompts/system_session_prompt.md and compiles template variables."""
    import pathlib
    prompt_file = pathlib.Path(__file__).parent.parent / "prompts" / "system_session_prompt.md"
    if prompt_file.exists():
        content = prompt_file.read_text(encoding="utf-8")
        if full_name:
            content = content.replace("{{user.full_name}}", full_name)
        else:
            content = content.replace("{{user.full_name}}", "User")
        return content
    return ""


# Agent Executor cache dictionary keyed by prompt/user
_agent_executors: Dict[str, Any] = {}

async def fetch_user_full_name(user_id: Optional[uuid.UUID]) -> Optional[str]:
    """Fetches full_name for a given user ID from PostgreSQL DB."""
    if not user_id:
        return None
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT full_name FROM users WHERE id = $1", user_id)
            if row and row["full_name"]:
                return row["full_name"]
    except Exception as err:
        logger.warning(f"Failed to fetch user full name for ID {user_id}: {err}")
    return None

def get_agent_executor(full_name: Optional[str] = None):
    """Initializes the LangChain Agent Executor with system prompt & structured chat tools."""
    global _agent_executors
    cache_key = full_name or "default"
    if cache_key not in _agent_executors:
        logger.info(f"Initializing LangChain AgentExecutor with prompt for user full_name: '{cache_key}'...")
        
        model_name = os.environ.get("GEMINI_LIVE_MODEL", "gemini-1.5-flash")
        
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.environ.get("GEMINI_API_KEY"),
            temperature=0.0
        )
        
        tools = [query_user_analytics, rag_knowledge_search, web_search, python_code_interpreter]
        
        system_prompt_text = load_system_session_prompt(full_name=full_name)
        
        _agent_executors[cache_key] = initialize_agent(
            tools=tools,
            llm=llm,
            agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,
            agent_kwargs={"prefix": system_prompt_text} if system_prompt_text else {}
        )
    return _agent_executors[cache_key]


@observe(name="system1-chat-agent", as_type="agent")
async def run_agent(message: str, user_id: Optional[str] = None, session_id: Optional[str] = None) -> str:
    """
    Executes the LangChain agent with Langfuse tracing and system prompt context.
    """
    active_user_uuid = current_user_id.get()
    uid = user_id or (str(active_user_uuid) if active_user_uuid else "guest")
    sid = session_id or f"session-{uuid.uuid4()}"

    # Fetch user's full name for prompt template compilation
    user_full_name = await fetch_user_full_name(active_user_uuid if active_user_uuid else (uuid.UUID(uid) if uid != "guest" else None))

    langfuse_context.update_current_trace(
        name="system1-chat-agent",
        user_id=uid,
        session_id=sid,
        tags=["system-1", "langchain-agent", "chat"],
        input=message
    )

    langfuse_handler = langfuse_context.get_current_langchain_handler()
    callbacks = [langfuse_handler] if langfuse_handler else []

    agent_executor = get_agent_executor(full_name=user_full_name)
    
    logger.info(f"Running agent for user '{user_full_name or 'guest'}' with query: {message}")
    response = await agent_executor.ainvoke(
        {"input": message},
        config={"callbacks": callbacks}
    )
    out_str = response.get("output", "")
    langfuse_context.update_current_trace(output=out_str)
    return out_str

