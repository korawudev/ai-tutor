FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -e .

# 复制代码
COPY shared/ ./shared/
COPY knowledge-agent/ ./knowledge-agent/

# 暴露端口
EXPOSE 8001

# 启动命令
CMD ["uvicorn", "knowledge-agent.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
