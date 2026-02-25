"""
Streaming Response Handler for LLM
Supports streaming responses from Claude and other LLMs
"""

from typing import AsyncIterator, Optional
import json
import logging
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class StreamingHandler:
    """Handle streaming responses from LLMs"""

    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        self.anthropic_client = None
        self.openai_client = None

    async def stream_anthropic(
        self,
        messages: list,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Stream response from Anthropic Claude"""

        if not self.anthropic_client:
            from app.core.config import get_settings
            settings = get_settings()
            self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        try:
            async with self.anthropic_client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                system=system
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise

    async def stream_openai(
        self,
        messages: list,
        model: str = "gpt-4",
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """Stream response from OpenAI"""

        if not self.openai_client:
            from app.core.config import get_settings
            settings = get_settings()
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        try:
            stream = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise

    async def stream_response(
        self,
        messages: list,
        model: str,
        **kwargs
    ) -> AsyncIterator[str]:
        """Universal streaming interface"""

        if "claude" in model.lower():
            async for chunk in self.stream_anthropic(messages, model, **kwargs):
                yield chunk
        elif "gpt" in model.lower():
            async for chunk in self.stream_openai(messages, model, **kwargs):
                yield chunk
        else:
            raise ValueError(f"Unsupported model for streaming: {model}")


async def stream_json_response(
    handler: StreamingHandler,
    messages: list,
    model: str,
    **kwargs
) -> AsyncIterator[str]:
    """Stream response as Server-Sent Events (SSE)"""

    try:
        async for chunk in handler.stream_response(messages, model, **kwargs):
            # Format as SSE
            data = json.dumps({"type": "content", "data": chunk})
            yield f"data: {data}\n\n"

        # Send completion event
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        # Send error event
        error_data = json.dumps({"type": "error", "error": str(e)})
        yield f"data: {error_data}\n\n"
