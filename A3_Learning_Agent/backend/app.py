from flask import Flask, jsonify
from flask_cors import CORS

from api.auth_api import auth_bp
from api.chat_api import chat_bp
from api.evaluation_api import evaluation_bp
from api.knowledge_api import knowledge_bp
from api.path_api import path_bp
from api.profile_api import profile_bp
from api.resource_api import resource_bp
from api.system_api import system_bp
from config import config
from db.schema import ensure_extended_tables


def _bootstrap_knowledge_base() -> None:
    try:
        from api.knowledge_api import bootstrap_knowledge_base

        bootstrap_knowledge_base()
    except Exception:
        pass


def create_app() -> Flask:
    """创建 Flask 后端应用。

    功能：初始化 Flask、配置跨域、注册业务蓝图和健康检查接口。
    输入：无。
    输出：可直接运行的 Flask 应用实例。
    """
    app = Flask(__name__)
    app.config.from_object(config)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    if config.AUTO_MIGRATE:
        ensure_extended_tables()
    if config.AUTO_BOOTSTRAP_KNOWLEDGE:
        _bootstrap_knowledge_base()

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(resource_bp, url_prefix="/api/resource")
    app.register_blueprint(path_bp, url_prefix="/api/path")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(knowledge_bp, url_prefix="/api/knowledge")
    app.register_blueprint(evaluation_bp, url_prefix="/api/evaluation")
    app.register_blueprint(system_bp, url_prefix="/api/system")

    @app.get("/health")
    def health_check():
        """健康检查接口。

        功能：用于确认后端服务是否正常启动。
        输入：无。
        输出：服务状态 JSON。
        """
        return jsonify({"code": 200, "msg": "成功", "data": {"status": "ok", "service": config.APP_NAME}})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
