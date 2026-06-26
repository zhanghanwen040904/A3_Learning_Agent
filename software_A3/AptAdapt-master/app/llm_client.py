"""讯飞星火 Chat API WebSocket 客户端 — 支持普通调用与流式输出"""
import websocket
import hashlib
import hmac
import base64
import json
import time
import ssl
from typing import Generator
from urllib.parse import urlencode

from .config import XFYUN_APPID, XFYUN_API_KEY, XFYUN_API_SECRET

SYSTEM_PROMPT = "你是一个专业的计算机组成原理助教老师，请用通俗易懂的语言回答学生的问题。"


class SparkLLM:
    def __init__(self):
        self.APPID = XFYUN_APPID
        self.API_KEY = XFYUN_API_KEY
        self.API_SECRET = XFYUN_API_SECRET
        self.Host = "spark-api.xf-yun.com"
        self.Path = "/v3.5/chat"
        self.URL = f"wss://{self.Host}{self.Path}"

    def _build_url(self) -> str:
        """生成带鉴权签名的 WebSocket URL"""
        now = time.time()
        date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(now))

        signature_origin = f"host: {self.Host}\ndate: {date}\nGET {self.Path} HTTP/1.1"
        signature_sha = hmac.new(
            self.API_SECRET.encode("utf-8"),
            signature_origin.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_sha).decode()

        authorization_origin = (
            f'api_key="{self.API_KEY}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode()

        params = {"authorization": authorization, "date": date, "host": self.Host}
        return self.URL + "?" + urlencode(params)

    def _build_payload(self, message: str) -> dict:
        return {
            "header": {"app_id": self.APPID, "uid": "user_123"},
            "parameter": {
                "chat": {
                    "domain": "generalv3.5",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                }
            },
            "payload": {
                "message": {
                    "text": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": message},
                    ]
                }
            },
        }

    def chat(self, message: str) -> str:
        """普通调用 — 等完整返回后一次性返回"""
        url = self._build_url()
        ws = websocket.create_connection(url, sslopt={"cert_reqs": ssl.CERT_NONE})
        ws.send(json.dumps(self._build_payload(message)))

        full_response = ""
        try:
            while True:
                res = json.loads(ws.recv())
                if res["header"]["status"] == 2:
                    break
                choices = res["payload"]["choices"]
                if choices and "content" in choices["text"][0]:
                    full_response += choices["text"][0]["content"]
        except Exception as e:
            print(f"接收消息出错: {e}")
        finally:
            ws.close()

        return full_response

    def chat_stream(self, message: str) -> Generator[str, None, None]:
        """
        流式调用 — 逐 token yield，配合 SSE 使用

        用法:
            llm = SparkLLM()
            for token in llm.chat_stream("什么是冯诺依曼结构？"):
                yield f"data: {json.dumps({'content': token})}\n\n"
        """
        url = self._build_url()
        ws = websocket.create_connection(url, sslopt={"cert_reqs": ssl.CERT_NONE})
        ws.send(json.dumps(self._build_payload(message)))

        try:
            while True:
                res = json.loads(ws.recv())
                if res["header"]["status"] == 2:
                    break
                choices = res["payload"]["choices"]
                if choices and "content" in choices["text"][0]:
                    content = choices["text"][0]["content"]
                    yield content
        except Exception as e:
            yield f"[错误] {e}"
        finally:
            ws.close()


if __name__ == "__main__":
    llm = SparkLLM()

    print("=== 普通调用 ===")
    answer = llm.chat("什么是冯诺依曼结构？")
    print("AI回复:", answer)

    print("\n=== 流式调用 ===")
    for token in llm.chat_stream("简单说一下Cache的作用"):
        print(token, end="", flush=True)
    print()