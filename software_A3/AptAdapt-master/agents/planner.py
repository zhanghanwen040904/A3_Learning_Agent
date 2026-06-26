"""Planner Agent — 基于知识点 DAG 生成个性化学习路径"""
import json
import os
from collections import deque
from .state import AgentState

SYSTEM_PROMPT = """你是学习路径规划智能体。请根据知识点 DAG（有向无环图）的先修依赖关系和学生画像中的 weak_points，生成个性化学习路径。

规划规则：
1. 遵循先修关系：必须先学完前置知识点才能进入后续知识
2. 薄弱点优先：将学生的 weak_points 相关知识点提前
3. 为薄弱点增加补充学习节点
"""


def load_dag() -> dict:
    """加载知识点 DAG 配置文件"""
    dag_path = os.path.join(os.path.dirname(__file__), "dag", "knowledge_dag.json")
    try:
        with open(dag_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"nodes": [], "edges": []}


def topological_sort(dag: dict, weak_points: list) -> list:
    """拓扑排序生成学习路径，薄弱点优先"""
    nodes = {n["id"]: n for n in dag.get("nodes", [])}
    edges = dag.get("edges", [])

    # 构建邻接表和入度
    adj = {nid: [] for nid in nodes}
    in_degree = {nid: 0 for nid in nodes}
    for edge in edges:
        src, tgt = edge["from"], edge["to"]
        if src in adj and tgt in adj:
            adj[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

    # Kahn 算法 + 薄弱点优先
    # 优先队列：薄弱点排在前面
    queue = deque()
    for nid, deg in in_degree.items():
        if deg == 0:
            queue.append(nid)

    path = []
    while queue:
        # 优先取薄弱点
        weak_found = None
        for nid in queue:
            if nid in weak_points or nodes.get(nid, {}).get("title", "") in weak_points:
                weak_found = nid
                break
        if weak_found:
            queue.remove(weak_found)
            current = weak_found
        else:
            current = queue.popleft()

        path.append(nodes.get(current, {"id": current, "title": current}))

        for neighbor in adj.get(current, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return path


def planner_node(state: AgentState) -> AgentState:
    """规划学习路径"""
    dag = load_dag()
    profile = state.get("profile", {})
    weak_points = profile.get("weak_points", [])

    path = topological_sort(dag, weak_points)

    # 为薄弱点添加补充学习标记
    for node in path:
        if node.get("title") in weak_points or node.get("id") in weak_points:
            node["priority"] = "high"
            node["note"] = "薄弱点，建议重点学习"
        else:
            node["priority"] = "normal"

    state["learning_path"] = path
    state["next_step"] = "end"
    return state
