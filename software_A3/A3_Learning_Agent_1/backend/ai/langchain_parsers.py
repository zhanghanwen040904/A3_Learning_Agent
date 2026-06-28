from typing import Any, Dict

from ai.json_utils import extract_json_object

try:
    from langchain_core.output_parsers import JsonOutputParser
except ModuleNotFoundError:
    JsonOutputParser = None

_json_parser = JsonOutputParser() if JsonOutputParser is not None else None


def parse_json_with_fallback(raw: Any) -> Dict[str, Any]:
    """Parse model output with LangChain first, then fall back to the local tolerant parser."""
    text = str(raw or "").strip()
    if not text:
        return {}
    if _json_parser is not None:
        try:
            parsed = _json_parser.parse(text)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass
    return extract_json_object(text)
