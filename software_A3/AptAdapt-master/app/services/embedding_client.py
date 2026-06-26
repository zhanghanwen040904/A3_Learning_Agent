"""讯飞星火 Embedding API HTTP 客户端"""
import hashlib
import hmac
import base64
import json
import time
from datetime import datetime
from urllib.parse import urlencode
import requests

from ..config import (
    XFYUN_APPID,
    XFYUN_API_KEY,
    XFYUN_API_SECRET,
    EMBEDDING_HOST,
    EMBEDDING_PATH,
    EMBEDDING_MODEL,
)


class EmbeddingClient:
    """讯飞星火 Embedding API 客户端"""

    def __init__(self):
        self.appid = XFYUN_APPID
        self.api_key = XFYUN_API_KEY
        self.api_secret = XFYUN_API_SECRET
        self.host = EMBEDDING_HOST
        self.path = EMBEDDING_PATH
        self.model = EMBEDDING_MODEL

    def _build_url(self) -> str:
        """生成带鉴权签名的完整 URL"""
        now = time.time()
        date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(now))

        # HMAC-SHA256 签名
        signature_origin = f"host: {self.host}\ndate: {date}\nPOST {self.path} HTTP/1.1"
        signature_sha = hmac.new(
            self.api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_sha).decode()

        # Authorization 头
        authorization_origin = (
            f'api_key="{self.api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode()).decode()

        params = {
            "authorization": authorization,
            "date": date,
            "host": self.host,
        }
        return f"https://{self.host}{self.path}?{urlencode(params)}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        调用讯飞 Embedding API 生成向量

        Args:
            texts: 待向量化的文本列表，单次最多 25 条

        Returns:
            向量列表，每个向量为 float 列表
        """
        url = self._build_url()
        headers = {"Content-Type": "application/json"}

        results = []
        # 讯飞 embedding 接口单次建议不超过 25 条
        batch_size = 25
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {
                "header": {
                    "app_id": self.appid,
                },
                "parameter": {
                    "emb": {
                        "domain": self.model,
                    }
                },
                "payload": {
                    "messages": [
                        {"content": t, "role": "user"} for t in batch
                    ]
                },
            }

            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            body = resp.json()

            if body["header"]["code"] != 0:
                raise RuntimeError(f"Embedding API 错误: {body['header']['message']}")

            # 解析向量
            vectors = body["payload"]["embeddings"]["texts"]
            results.extend(vectors)

        return results

    def embed_single(self, text: str) -> list[float]:
        """对单个文本生成向量"""
        return self.embed([text])[0]


if __name__ == "__main__":
    client = EmbeddingClient()
    vec = client.embed_single("计算机组成原理是计算机科学与技术专业的核心课程")
    print(f"向量维度: {len(vec)}")
    print(f"前 5 维: {vec[:5]}")
