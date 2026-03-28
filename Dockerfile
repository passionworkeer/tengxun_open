FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 安装基础系统依赖与 uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# 先安装依赖，便于利用 Docker 构建缓存
COPY requirements.txt ./
RUN uv pip install --system -r requirements.txt

# 再复制项目源码
COPY . .

CMD ["bash"]
