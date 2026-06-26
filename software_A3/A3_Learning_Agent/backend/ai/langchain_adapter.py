from typing import Any, List, Optional

from ai.spark_api import spark_chat

try:
    from langchain_core.language_models.llms import LLM
except ModuleNotFoundError:
    LLM = None


if LLM is not None:
    class SparkLLM(LLM):
        """LangChain LLM adapter for the existing Xunfei Spark client."""

        @property
        def _llm_type(self) -> str:
            return "xunfei_spark"

        def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs: Any) -> str:
            return call_spark_with_stop(prompt, stop)
else:
    class SparkLLM:
        """Fallback adapter used before LangChain dependencies are installed."""

        def invoke(self, prompt: Any, *args: Any, **kwargs: Any) -> str:
            return call_spark_with_stop(str(prompt), kwargs.get("stop"))


def call_spark_with_stop(prompt: str, stop: Optional[List[str]] = None) -> str:
    text = spark_chat(prompt)
    if stop:
        for token in stop:
            index = text.find(token)
            if index >= 0:
                text = text[:index]
                break
    return text
