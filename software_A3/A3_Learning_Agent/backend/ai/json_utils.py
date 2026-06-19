import json
import re
from typing import Any, Dict


def extract_json_object(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    text = str(raw).strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        return {}
    candidate = text[start:end]
    try:
        return json.loads(candidate)
    except Exception:
        pass
    candidate = candidate.replace("\n", "\\n")
    candidate = re.sub(r",\s*}", "}", candidate)
    candidate = re.sub(r",\s*]", "]", candidate)
    try:
        return json.loads(candidate)
    except Exception:
        return {}
