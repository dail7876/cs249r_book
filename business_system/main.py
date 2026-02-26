"""
智能营销业务系统 - 主入口
Smart Marketing Business System - Main Entry Point

启动命令：
  python main.py
  或
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(__file__))

from web.app import app  # noqa: F401 - 被 uvicorn 直接使用

if __name__ == "__main__":
    import uvicorn
    from loguru import logger
    from config import settings

    logger.info(f"启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("访问地址：http://localhost:8000")
    logger.info("API 文档：http://localhost:8000/docs")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
