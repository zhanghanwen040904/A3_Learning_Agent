from typing import Any, List, Optional

from ai.llm_api import llm_chat

try:
    from langchain_core.language_models.llms import LLM
except ModuleNotFoundError:
    LLM = None


if LLM is not None:
    class PlatformLLM(LLM):
        """LangChain LLM adapter for the current platform model client."""

        @property
        def _llm_type(self) -> str:
            return "platform_llm"

        def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs: Any) -> str:
            return call_llm_with_stop(prompt, stop)
else:
    class PlatformLLM:
        """Fallback adapter used before LangChain dependencies are installed."""

        def invoke(self, prompt: Any, *args: Any, **kwargs: Any) -> str:
            return call_llm_with_stop(str(prompt), kwargs.get("stop"))


def call_llm_with_stop(prompt: str, stop: Optional[List[str]] = None) -> str:
    text = llm_chat(prompt)
    if stop:
        for token in stop:
            index = text.find(token)
            if index >= 0:
                text = text[:index]
                break
    return text
