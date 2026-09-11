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
COPY gateway/ ./gateway/
# gateway 直接复用 review_agent 的调度逻辑（schedule_manager/spaced_repetition）
COPY review-agent/ ./review_agent/

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "gateway.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
