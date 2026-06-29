from .resource_base import StructuredResourceAgent


class DocumentAgent(StructuredResourceAgent):
    resource_type = "doc"
    role = "专业课程讲解文档生成师"
    goal = "把教材知识转化为适合学生当前基础的递进式专业课程讲解"
    default_title = "个性化课程讲解文档"
    requirements = """
必须返回适合前端结构化渲染的 JSON 内容，不要返回 Markdown 正文。
顶层仍按公共协议返回 {"title":"...","content":{...},"knowledge_points":[],"personalization":"...","format":"json"}。
content 必须是对象，字段包括：
- resourcetype: 固定为 doc
- resourcetitle: 文档标题
- knowledgelevel: 学生当前知识基础
- studystyle: 学习偏好
- weakpoints: 薄弱点数组
- studygoal: 学习目标
- studytimepreferred: 学习时间偏好
- courseprogress: 当前课程进度或教材章节
- challengescene: 挑战场景
- preferredresourcetype: 固定为 doc
- profilesummary: {major, minor, weakpoint, studygoal}
- studentcontext: {currentclass, currentunit, currentchapter, currentsection, currentpage}
- learningresources: [{title, source, sectionpath, pages, chunkid, content, images}]
内容必须来自课程知识库依据，learningresources 至少包含 1 个知识片段；不要把 JSON 外层写成代码块。
""".strip()
