import json
import re
from typing import Any, Dict


def extract_json_object(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    text = str(raw).strip()
    # 仅在整个模型输出被代码围栏包裹时剥离围栏；资源JSON的content内部可能合法包含Python代码块。
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
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
