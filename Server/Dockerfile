FROM python:3.11-slim

LABEL maintainer="AIIR Team"
LABEL description="AIIR - AI-driven Incident Response Server"

# 设置工作目录
WORKDIR /app

# 配置DNS（解决构建环境DNS问题）
RUN cat > /etc/apt/apt.conf << 'EOF'
Acquire::Check-Valid-Until "false";
Acquire::http::Proxy "http://8.8.8.8:53";
EOF

# 安装系统依赖 - 尝试多个镜像源
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true && \
    sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true && \
    apt-get update || (sed -i 's/mirrors.tuna.tsinghua.edu.cn/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null && apt-get update) || \
    (sed -i 's/mirrors.tuna.tsinghua.edu.cn/deb.debian.org/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null && apt-get update) || true && \
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