"""
生产级启动入口：使用 Uvicorn（Windows 友好的 ASGI 服务器）。

启动：
    python serve.py
可选环境变量：
    TEA_HOST  监听地址，默认 0.0.0.0（本机 + 局域网）
    TEA_PORT  端口，默认 8080
    TEA_THREADS 保留兼容但不再使用（Uvicorn 单进程）
"""

import os
import socket
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, BACKEND_DIR)

import db  # noqa: E402
from app import app  # noqa: E402


def get_lan_ip():
    """获取本机局域网 IPv4（仅查询出站网卡，不实际发包）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    db.init_db()
    host = os.environ.get("TEA_HOST", "0.0.0.0")
    port = int(os.environ.get("TEA_PORT", "8080"))

    print("服务启动：")
    print(f"  本机访问：   http://127.0.0.1:{port}")
    if host == "0.0.0.0":
        print(f"  局域网访问： http://{get_lan_ip()}:{port}")

    import uvicorn

    print("  ASGI 服务器：Uvicorn，Ctrl+C 停止")
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
