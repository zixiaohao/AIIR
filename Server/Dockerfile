FROM python:3.11-slim

LABEL maintainer="AIIR Team"
LABEL description="AIIR - AI-driven Incident Response Server"

# 设置工作目录
WORKDIR /app

# 尝试使用官方源，如果失败则切换到国内镜像源
RUN echo '#!/bin/bash\n\
set -e\n\
apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev\n\
' > /tmp/install_deps.sh && \
    bash -c "apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev 2>/dev/null" || \
    (echo "官方源连接失败，切换到国内镜像源..." && \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    true && \
    apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev) && \
    rm -rf /var/lib/apt/lists/* /tmp/install_deps.sh || true

# 如果上面失败，使用备用方法
RUN if ! command -v gcc >/dev/null 2>&1; then \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true && \
    apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev && rm -rf /var/lib/apt/lists/*; \
    fi

# 安装系统依赖（确保成功）
RUN apt-get update || (sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && apt-get update) && \
    apt-get install -y --no-install-recommends gcc libffi-dev && rm -rf /var/lib/apt/lists/*

# 复制并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY server.py .
COPY ai_manager.py .
COPY aescode.py .
COPY attack_patterns.json .
COPY install_deps.sh .

# 创建配置和上传目录
RUN mkdir -p /app/config /app/uploaded_files

# 复制配置模板
COPY config.json.example /app/config.json.example

# 创建入口脚本
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# 暴露服务端口
EXPOSE 8000

# 入口脚本处理首次启动配置
ENTRYPOINT ["docker-entrypoint.sh"]

# 启动Server
CMD ["python3", "server.py", "--host", "0.0.0.0"]