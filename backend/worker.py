import os
import json
import uuid
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from kafka import KafkaConsumer
from docling.document_converter import DocumentConverter
from langchain_text_splitters import MarkdownHeaderTextSplitter
from sentence_transformers import SentenceTransformer

from backend.config import settings
from backend.db import init_db_pool, close_db_pool, get_db_pool

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend-worker")

# Define markdown headers to split on
HEADERS_TO_SPLIT = [
    ("#", "Header_1"),
    ("##", "Header_2"),
    ("###", "Header_3"),
    ("####", "Header_4"),
]

class IngestionWorker:
    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        logger.info("Initializing SentenceTransformer BAAI/bge-small-en-v1.5 on GPU (cuda)...")
        # Explicitly configure device='cuda' to force RTX GPU usage
        self.embed_model = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cuda")
        
        logger.info("Initializing IBM Docling Document Converter...")
        self.doc_converter = DocumentConverter()
        
        logger.info("Initializing Kafka Consumer...")
        self.consumer = KafkaConsumer(
            settings.KAFKA_INGESTION_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
            group_id="document_processors",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=True
        )
        
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=HEADERS_TO_SPLIT,
            strip_headers=False
        )

    async def start(self):
        logger.info("Worker started successfully and listening for ingestion events...")
        try:
            while True:
                # Use non-blocking poll to yield control back to event loop
                msg_pack = self.consumer.poll(timeout_ms=200)
                for tp, messages in msg_pack.items():
                    for message in messages:
                        payload = message.value
                        logger.info(f"Received ingestion event: {payload}")
                        await self.process_event(payload)
                # Yield execution thread briefly
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Worker cancelled, exiting loop...")
        finally:
            self.consumer.close()

    async def process_event(self, payload: dict):
        doc_id_str = payload.get("doc_id")
        user_id_str = payload.get("user_id")
        file_path = payload.get("file_path")
        file_name = payload.get("file_name")

        if not all([doc_id_str, user_id_str, file_path]):
            logger.error(f"Incomplete event payload ignored: {payload}")
            return

        doc_uuid = uuid.UUID(doc_id_str)
        pool = await get_db_pool()

        # 1. Update status to PROCESSING
        logger.info(f"Setting status of document {doc_id_str} to PROCESSING...")
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE documents SET status = 'PROCESSING' WHERE id = $1",
                doc_uuid
            )

        try:
            # 2. Extract layout-aware markdown via Docling (executed on thread pool)
            logger.info(f"Running Docling converter on PDF: {file_path}...")
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found at: {file_path}")

            conversion_result = await self.loop.run_in_executor(
                self.executor,
                self.doc_converter.convert,
                file_path
            )
            
            markdown_text = conversion_result.document.export_to_markdown()
            
            # 3. Chunk using MarkdownHeaderTextSplitter
            logger.info("Splitting document content into markdown-header aware chunks...")
            chunks = self.markdown_splitter.split_text(markdown_text)
            
            if not chunks:
                logger.warning(f"No chunks extracted from document: {file_name}. Inserting full text as single chunk.")
                from langchain_core.documents import Document
                chunks = [Document(page_content=markdown_text)]

            # 4. Generate BGE small embeddings on GPU
            logger.info(f"Generating {len(chunks)} embeddings on GPU via BAAI/bge-small-en-v1.5...")
            texts = [chunk.page_content for chunk in chunks]
            
            # Compute embeddings in executor to prevent freezing the event loop
            embeddings = await self.loop.run_in_executor(
                self.executor,
                lambda: self.embed_model.encode(texts, convert_to_numpy=True).tolist()
            )

            # 5. Insert chunks & embeddings in PostgreSQL via asyncpg
            logger.info(f"Persisting vectors & chunks in Postgres vector_knowledge table...")
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for chunk, embedding in zip(chunks, embeddings):
                        # Convert float list to pgvector string format '[v1, v2, ...]'
                        vector_str = "[" + ",".join(map(str, embedding)) + "]"
                        await conn.execute(
                            """
                            INSERT INTO vector_knowledge (doc_id, chunk_text, embedding)
                            VALUES ($1, $2, $3::vector)
                            """,
                            doc_uuid, chunk.page_content, vector_str
                        )
                    
                    # 6. Update status to COMPLETE
                    await conn.execute(
                        "UPDATE documents SET status = 'COMPLETE' WHERE id = $1",
                        doc_uuid
                    )
            
            logger.info(f"Ingestion pipeline completed successfully for document {doc_id_str}.")

        except Exception as e:
            logger.error(f"Ingestion processing failed for document {doc_id_str}: {e}")
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE documents SET status = 'FAILED' WHERE id = $1",
                    doc_uuid
                )
        finally:
            # Clean up the temp file to save disk space
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Removed temporary upload file: {file_path}")
                except Exception as cleanup_err:
                    logger.error(f"Failed to remove temp file {file_path}: {cleanup_err}")

async def main():
    await init_db_pool()
    worker = IngestionWorker()
    try:
        await worker.start()
    finally:
        await close_db_pool()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker shut down by keyboard interrupt.")
