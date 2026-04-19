import asyncio
import os
import tempfile
from pathlib import Path
from backboard import BackboardClient
from backboard.models import Document
from app.core.monitoring import structured_logger, cost_tracker, TracingContext, trace


class BackboardClientWrapper:
    """
    Wrapper around the official backboard-sdk that maintains compatibility
    with the existing codebase interface.
    """

    def __init__(self, api_key, timeout: int = None):
        timeout = timeout or int(os.getenv("BACKBOARD_TIMEOUT", "1800"))
        print(f"Timeout: "+ str(timeout))
        self.client = BackboardClient(api_key=api_key, timeout=timeout)
        self.llm_provider = os.getenv("BACKBOARD_LLM_PROVIDER", "openai")
        self.model_name = os.getenv("BACKBOARD_MODEL_NAME", "gpt-5-mini")

    async def create_assistant(self, name, system_prompt=None):
        async with TracingContext() as ctx:
            ctx.start_span("create_assistant", {"name": name})
            try:
                assistant = await self.client.create_assistant(
                    name=name,
                    system_prompt=system_prompt
                )
                structured_logger.info(f"Created assistant: {assistant.assistant_id}")
                return assistant.assistant_id
            except Exception as e:
                structured_logger.error(f"Failed to create assistant: {str(e)}")
                raise

    async def create_thread(self, assistant_id):
        async with TracingContext() as ctx:
            ctx.start_span("create_thread", {"assistant_id": assistant_id})
            try:
                thread = await self.client.create_thread(assistant_id=assistant_id)
                structured_logger.info(f"Created thread: {thread.thread_id}")
                return thread.thread_id
            except Exception as e:
                structured_logger.error(f"Failed to create thread: {str(e)}")
                raise

    async def get_document_status(self, document_id):
        try:
            return await self.client.get_document_status(document_id)
        except Exception as e:
            if "Input should be" in str(e) and "status" in str(e):
                structured_logger.warning(f"Document status validation failed for {document_id}, treating as failed")
                class FailedDoc:
                    def __init__(self, doc_id, msg):
                        self.document_id = doc_id
                        self.filename = "unknown"
                        self.status = "failed"
                        self.status_message = msg
                        self.chunk_count = 0
                        self.total_tokens = 0
                return FailedDoc(document_id, f"Status validation error: {str(e)}")
            raise

    async def upload_document(self, file, metadata=None, assistant_id=None, poll_timeout: int = 1800, poll_interval: int = 2):
        if assistant_id is None:
            raise ValueError("assistant_id is required to upload a document")

        async def _do_upload():
            suffix = Path(file.filename).suffix if file.filename else ""
            content = await file.read()
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(content)
                    tmp_path = Path(tmp.name)
            except Exception as e:
                raise IOError(f"Failed to write temporary file: {e}") from e

            try:
                doc = await self.client.upload_document_to_assistant(
                    assistant_id=assistant_id,
                    file_path=tmp_path
                )

                elapsed = 0
                while elapsed < poll_timeout:
                    status = await self.client.get_document_status(doc.document_id)
                    if status.status == "indexed":
                        return {
                            "id": doc.document_id,
                            "status": status.status,
                            "filename": doc.filename,
                            "chunk_count": status.chunk_count,
                            "total_tokens": status.total_tokens
                        }
                    elif status.status == "failed":
                        return {
                            "id": doc.document_id,
                            "status": status.status,
                            "error": status.status_message
                        }
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval
                
                raise TimeoutError(f"Document {doc.document_id} indexing timed out after {poll_timeout}s")
            finally:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)

        async with TracingContext() as ctx:
            ctx.start_span("upload_document", {"assistant_id": assistant_id})
            try:
                result = await _do_upload()
                structured_logger.info(f"Uploaded document: {result.get('id')}")
                return result
            except Exception as e:
                structured_logger.error(f"Failed to upload document: {str(e)}")
                raise

    async def chat(self, thread_id, content, web_search="Auto", memory="Auto"):
        async def _do_chat():
            response = await self.client.add_message(
                thread_id=thread_id,
                content=content,
                stream=False,
                web_search=web_search,
                llm_provider=self.llm_provider,
                model_name=self.model_name,
                memory=memory
            )
            
            usage = getattr(response, "usage", None)
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", 0) or getattr(usage, "prompt_token_count", 0) or 0
                completion_tokens = getattr(usage, "completion_tokens", 0) or getattr(usage, "completion_token_count", 0) or 0
                total_tokens = getattr(usage, "total_tokens", 0) or getattr(usage, "total_token_count", 0) or 0
            
            if prompt_tokens or completion_tokens or total_tokens:
                cost_tracker.record(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    model=self.model_name
                )
                structured_logger.info(
                    f"LLM Request completed",
                    model=self.model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens
                )
            else:
                structured_logger.warning("No token usage data found in response")
            
            return {"content": response.content, "run_id": response.run_id}

        async with TracingContext() as ctx:
            ctx.start_span("chat", {"thread_id": thread_id, "web_search": web_search})
            try:
                result = await _do_chat()
                return result
            except Exception as e:
                structured_logger.error(f"Chat failed: {str(e)}")
                raise

    async def web_search(self, thread_id, content, memory="Auto"):
        return await self.chat(thread_id, content, web_search="Auto", memory=memory)

    async def chat_no_search(self, thread_id, content, memory="Auto"):
        return await self.chat(thread_id, content, web_search="off", memory=memory)

    async def add_message(self, thread_id, content, memory="Auto", stream=False):
        async def _do_add_message():
            response = await self.client.add_message(
                thread_id=thread_id,
                content=content,
                memory=memory,
                stream=stream,
                llm_provider=self.llm_provider,
                model_name=self.model_name
            )
            
            usage = getattr(response, "usage", None)
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", 0) or getattr(usage, "prompt_token_count", 0) or 0
                completion_tokens = getattr(usage, "completion_tokens", 0) or getattr(usage, "completion_token_count", 0) or 0
                total_tokens = getattr(usage, "total_tokens", 0) or getattr(usage, "total_token_count", 0) or 0
            
            if prompt_tokens or completion_tokens or total_tokens:
                cost_tracker.record(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    model=self.model_name
                )
            
            return {"content": response.content, "run_id": response.run_id}

        async with TracingContext() as ctx:
            ctx.start_span("add_message", {"thread_id": thread_id, "memory": memory})
            try:
                return await _do_add_message()
            except Exception as e:
                structured_logger.error(f"add_message failed: {str(e)}")
                raise

    async def add_memory(self, assistant_id, content, metadata=None):
        async with TracingContext() as ctx:
            ctx.start_span("add_memory", {"assistant_id": assistant_id})
            try:
                result = await self.client.add_memory(
                    assistant_id=assistant_id,
                    content=content,
                    metadata=metadata
                )
                structured_logger.info(
                    f"Added memory to assistant",
                    assistant_id=assistant_id,
                    model=self.model_name
                )
                return result
            except Exception as e:
                structured_logger.error(f"add_memory failed: {str(e)}")
                raise

    async def close(self):
        if hasattr(self.client, 'close'):
            await self.client.close()
        elif hasattr(self.client, 'aclose'):
            await self.client.aclose()
        structured_logger.info("Backboard client closed")
