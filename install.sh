#!/bin/bash
# =============================================================================
# AIIR 一键安装脚本
# 功能：Docker安装、源码拉取、exe编译、服务部署与升级
# 适配：中国网络环境，支持代理/镜像加速
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
REPO_URL="https://github.com/zixiaohao/AIIR.git"
INSTALL_DIR="/opt/aiir"
CONFIG_DIR="/etc/aiir"

# Git代理配置
GIT_PROXY=""
# Docker镜像加速 - 统一使用 docker.1ms.run
DOCKER_MIRROR="docker.1ms.run"
DOCKER_DAEMON_MIRROR="https://docker.1ms.run"

# 发行版检测变量（由 detect_os 填充）
OS_ID=""
OS_CODENAME=""
DOCKER_OS=""       # docker repo 用的 OS 名 (ubuntu/debian)
DOCKER_CODENAME="" # docker repo 用的发行版代号

# -----------------------------------------------------------------------------
# 工具函数
# -----------------------------------------------------------------------------

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 未安装，请先安装 $1"
        return 1
    fi
    return 0
}

# -----------------------------------------------------------------------------
# 发行版检测 - 兼容 Debian / Ubuntu / Linux Mint / Pop!_OS / Kali 等
# -----------------------------------------------------------------------------

detect_os() {
    log_info "检测操作系统发行版..."

    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID=$ID
        OS_CODENAME=$VERSION_CODENAME
        # 如果 VERSION_CODENAME 为空，尝试用 UBUNTU_CODENAME
        if [ -z "$OS_CODENAME" ]; then
            OS_CODENAME=$UBUNTU_CODENAME
        fi
    elif command -v lsb_release &> /dev/null; then
        OS_ID=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
        OS_CODENAME=$(lsb_release -cs)
    else
        # 回退检测
        OS_ID="unknown"
        OS_CODENAME="unknown"
    fi

    log_info "检测到系统: $OS_ID ($OS_CODENAME)"

    # 将衍生版映射到上游 Docker 支持的发行版
    case "$OS_ID" in
        # ---- Debian 及其衍生版 ----
        debian)
            DOCKER_OS="debian"
            DOCKER_CODENAME="$OS_CODENAME"
            # Debian trixie (13) / sid 尚未正式发布 Docker 包，回退到 bookworm
            if [ "$OS_CODENAME" = "trixie" ] || [ "$OS_CODENAME" = "sid" ]; then
                log_warn "Debian $OS_CODENAME 检测，使用 Debian bookworm 的 Docker 源"
                DOCKER_CODENAME="bookworm"
            fi
            ;;
        kali)
            # Kali 基于 Debian testing，回退到 bookworm
            DOCKER_OS="debian"
            DOCKER_CODENAME="bookworm"
            log_warn "Kali Linux 检测，使用 Debian bookworm 的 Docker 源"
            ;;
        # ---- Ubuntu 及其衍生版 ----
        ubuntu)
            DOCKER_OS="ubuntu"
            DOCKER_CODENAME="$OS_CODENAME"
            ;;
        linuxmint)
            # Linux Mint 基于 Ubuntu，映射到对应的 Ubuntu 版本
            DOCKER_OS="ubuntu"
            case "$OS_CODENAME" in
                wilma|ulyana|ulyssa|uma|una|vanessa|vera|victoria|virginia) DOCKER_CODENAME="focal" ;;    # 20.x
                elsie|faye) DOCKER_CODENAME="jammy" ;;                                                     # 21.x
                *) DOCKER_CODENAME="noble" ;;                                                              # 默认最新 LTS
            esac
            log_warn "Linux Mint 检测，使用 Ubuntu $DOCKER_CODENAME 的 Docker 源"
            ;;
        pop)
            # Pop!_OS 基于 Ubuntu
            DOCKER_OS="ubuntu"
            DOCKER_CODENAME="$OS_CODENAME"
            log_warn "Pop!_OS 检测，使用 Ubuntu 的 Docker 源"
            ;;
        elementary|neon|zorin)
            # 其他 Ubuntu 衍生版
            DOCKER_OS="ubuntu"
            DOCKER_CODENAME="$OS_CODENAME"
            log_warn "$OS_ID 检测，使用 Ubuntu 的 Docker 源"
            ;;
        *)
            # 未知发行版，默认用 ubuntu focal
            log_warn "未知发行版 ($OS_ID)，默认使用 Ubuntu focal 的 Docker 源"
            DOCKER_OS="ubuntu"
            DOCKER_CODENAME="focal"
            ;;
    esac

    log_info "Docker 源: $DOCKER_OS/$DOCKER_CODENAME"
}

# -----------------------------------------------------------------------------
# 修复 hostname 解析（解决 sudo: unable to resolve host）
# -----------------------------------------------------------------------------

fix_hostname() {
    local host
    host=$(hostname 2>/dev/null || echo "")
    if [ -n "$host" ] && ! grep -qi "$host" /etc/hosts 2>/dev/null; then
        log_info "修复 hostname 解析..."
        echo "127.0.0.1 $host" >> /etc/hosts 2>/dev/null || \
        echo "127.0.0.1 $host" | sudo tee -a /etc/hosts > /dev/null
    fi
}

# 检测网络连接
check_network() {
    log_info "检测网络连接..."

    # 测试GitHub连接
    if curl -s --connect-timeout 5 https://github.com > /dev/null 2>&1; then
        log_success "GitHub 连接正常"
        return 0
    fi

    # 测试ghproxy加速器
    if curl -s --connect-timeout 5 https://ghproxy.net > /dev/null 2>&1; then
        log_warn "GitHub 直连失败，但 ghproxy 加速器可用"
        return 0
    fi

    # 测试Gitee镜像连接
    if curl -s --connect-timeout 5 https://gitee.com > /dev/null 2>&1; then
        log_warn "GitHub 连接失败，但 Gitee 镜像可用"
        return 0
    fi

    log_error "网络连接失败，请检查网络或配置代理"
    return 1
}

# 配置Git代理
setup_git_proxy() {
    read -p "请输入代理地址 (如: http://127.0.0.1:7890，留空跳过): " proxy

    if [ -n "$proxy" ]; then
        git config --global http.proxy "$proxy"
        git config --global https.proxy "$proxy"
        GIT_PROXY="$proxy"
        log_success "Git 代理已配置: $proxy"
    fi
}

# GitHub 加速镜像列表（按优先级排序，全部为免登录公开镜像）
GITHUB_MIRRORS=(
    "https://ghfast.top/https://github.com/zixiaohao/AIIR.git"
    "https://ghproxy.net/https://github.com/zixiaohao/AIIR.git"
    "https://gh-proxy.com/https://github.com/zixiaohao/AIIR.git"
    "https://ghproxy.cc/https://github.com/zixiaohao/AIIR.git"
    "https://mirror.ghproxy.com/https://github.com/zixiaohao/AIIR.git"
    "https://raw.githubusercontent.com/https://github.com/zixiaohao/AIIR.git"
    "https://gitee.com/zixiaohao/aiir.git"
)

# 禁止 git 弹出密码输入框，超时 10 秒
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=echo

# 带加速器回退的 git fetch
# 参数: $1=仓库目录  $2=分支名(默认main)
git_fetch_with_fallback() {
    local repo_dir="${1:-.}"
    local branch="${2:-main}"
    cd "$repo_dir"

    # 保存原始 URL，确保最后一定能恢复
    local original_url
    original_url=$(git remote get-url origin 2>/dev/null)

    # 第一次尝试：当前 origin（可能是 GitHub 直连）
    log_info "尝试从 GitHub 拉取..."
    if timeout 15 git fetch origin "$branch" 2>/dev/null; then
        log_success "GitHub 拉取成功"
        # 确保 origin 是 GitHub 地址
        git remote set-url origin "$REPO_URL" 2>/dev/null
        return 0
    fi

    # 依次尝试加速镜像
    for mirror in "${GITHUB_MIRRORS[@]}"; do
        local mirror_name
        mirror_name=$(echo "$mirror" | cut -d'/' -f3)
        log_warn "尝试加速镜像: $mirror_name ..."
        git remote set-url origin "$mirror"
        if timeout 20 git fetch origin "$branch" 2>/dev/null; then
            log_success "$mirror_name 拉取成功"
            git remote set-url origin "$REPO_URL"
            return 0
        fi
    done

    # 全部失败，恢复原地址
    git remote set-url origin "$REPO_URL"
    log_error "所有拉取方式均失败（已尝试 GitHub + ${#GITHUB_MIRRORS[@]} 个加速镜像）"
    log_error "请检查网络或手动配置代理: https_proxy=http://ip:port install.sh"
    return 1
}

# 带加速器回退的 git clone
# 参数: $1=目标目录
git_clone_with_fallback() {
    local target_dir="$1"

    # 第一次尝试：GitHub 直连
    log_info "尝试从 GitHub 克隆..."
    if timeout 30 git clone "$REPO_URL" "$target_dir" 2>/dev/null; then
        log_success "GitHub 克隆成功"
        return 0
    fi

    # 依次尝试加速镜像
    for mirror in "${GITHUB_MIRRORS[@]}"; do
        local mirror_name
        mirror_name=$(echo "$mirror" | cut -d'/' -f3)
        log_warn "尝试加速镜像: $mirror_name ..."
        if timeout 30 git clone "$mirror" "$target_dir" 2>/dev/null; then
            log_success "$mirror_name 克隆成功"
            # 确保 origin 恢复为 GitHub 地址
            cd "$target_dir" && git remote set-url origin "$REPO_URL"
            return 0
        fi
        # 清理失败的半成品目录
        rm -rf "$target_dir" 2>/dev/null
    done

    log_error "所有克隆方式均失败（已尝试 GitHub + ${#GITHUB_MIRRORS[@]} 个加速镜像）"
    log_error "请检查网络或手动配置代理: https_proxy=http://ip:port install.sh"
    return 1
}

# 配置Docker镜像加速
setup_docker_mirror() {
    log_info "配置 Docker 镜像加速 ($DOCKER_DAEMON_MIRROR)..."

    # 创建Docker守护进程配置目录（daemon.json 必须在 /etc/docker/ 下）
    sudo mkdir -p /etc/docker

    # 写入daemon.json
    sudo tee /etc/docker/daemon.json > /dev/null << EOF
{
    "registry-mirrors": ["$DOCKER_DAEMON_MIRROR"],
    "dns": ["8.8.8.8", "8.8.4.4"]
}
EOF

    log_success "Docker 镜像加速已配置: $DOCKER_DAEMON_MIRROR"

    # 重启Docker服务
    if command -v systemctl &> /dev/null; then
        sudo systemctl daemon-reload
        sudo systemctl restart docker
    fi
}

# -----------------------------------------------------------------------------
# 安装Docker和Docker Compose
# -----------------------------------------------------------------------------

install_docker() {
    log_info "开始安装 Docker..."

    # 先修复 hostname 避免 sudo 告警
    fix_hostname

    # 检查是否安装
    if command -v docker &> /dev/null; then
        log_warn "Docker 已安装: $(docker --version)"
        read -p "是否重新安装? (y/N): " confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            return 0
        fi
    fi

    # 卸载旧版本
    sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

    # 先检测发行版，用于后续选择 Docker 源
    detect_os

    # 检测网络并选择合适的镜像源
    log_info "检测网络环境..."
    USE_MIRROR=false

    # 先测试官方源是否可用（用检测到的发行版路径）
    if ! curl -s --connect-timeout 5 "https://download.docker.com/linux/$DOCKER_OS/gpg" > /dev/null 2>&1; then
        log_warn "官方源连接失败，切换到国内镜像源..."
        USE_MIRROR=true

        # 更换apt源为清华镜像（兼容 ubuntu/debian sources.list）
        log_info "配置 apt 镜像源..."
        sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak 2>/dev/null || true
        sudo sed -i 's/cn.archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
        sudo sed -i 's/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
        sudo sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
        sudo sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
    fi

    # 清理可能残留的旧 Docker 源列表，避免使用错误的 OS/codename 导致 404
    sudo rm -f /etc/apt/sources.list.d/docker.list

    # 更新apt
    sudo apt-get update

    # 安装依赖
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    # 添加Docker官方GPG密钥
    log_info "添加 Docker GPG 密钥..."

    # 先清理旧 keyring，避免交互提示 Overwrite? (y/N)
    sudo rm -f /usr/share/keyrings/docker-archive-keyring.gpg

    if [ "$USE_MIRROR" = true ]; then
        # 使用清华镜像源
        if curl -fsSL "https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/$DOCKER_OS/gpg" | sudo gpg --dearmor --yes -o /usr/share/keyrings/docker-archive-keyring.gpg 2>/dev/null; then
            log_success "使用清华 Docker 镜像源"
            DOCKER_REPO="deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/$DOCKER_OS $DOCKER_CODENAME stable"
        else
            # 回退到官方源
            log_warn "清华镜像源 GPG 失败，回退到官方源..."
            sudo rm -f /usr/share/keyrings/docker-archive-keyring.gpg
            curl -fsSL "https://download.docker.com/linux/$DOCKER_OS/gpg" | sudo gpg --dearmor --yes -o /usr/share/keyrings/docker-archive-keyring.gpg
            DOCKER_REPO="deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/$DOCKER_OS $DOCKER_CODENAME stable"
        fi
    else
        # 优先使用官方源
        if curl -fsSL "https://download.docker.com/linux/$DOCKER_OS/gpg" | sudo gpg --dearmor --yes -o /usr/share/keyrings/docker-archive-keyring.gpg 2>/dev/null; then
            log_success "使用官方 Docker 源"
            DOCKER_REPO="deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/$DOCKER_OS $DOCKER_CODENAME stable"
        else
            # 回退到清华镜像源
            log_warn "官方源 GPG 失败，回退到清华镜像源..."
            sudo rm -f /usr/share/keyrings/docker-archive-keyring.gpg
            curl -fsSL "https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/$DOCKER_OS/gpg" | sudo gpg --dearmor --yes -o /usr/share/keyrings/docker-archive-keyring.gpg
            log_success "使用清华 Docker 镜像源"
            DOCKER_REPO="deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/$DOCKER_OS $DOCKER_CODENAME stable"
        fi
    fi

    # 添加Docker仓库
    echo "$DOCKER_REPO" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # 安装Docker - 优先安装 docker.io (最简单可靠)
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose || sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # 启动Docker
    sudo systemctl start docker
    sudo systemctl enable docker

    # 配置Docker镜像加速（仅国内环境需要）
    if [ "$USE_MIRROR" = true ]; then
        setup_docker_mirror
    fi

    log_success "Docker 安装完成: $(docker --version)"
}

# -----------------------------------------------------------------------------
# 克隆源码
# -----------------------------------------------------------------------------

clone_source() {
    log_info "开始克隆源码..."

    # 检查网络
    check_network || setup_git_proxy

    # 创建安装目录
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown $(whoami):$(whoami) "$INSTALL_DIR"

    # 检查是否已存在
    if [ -d "$INSTALL_DIR/.git" ]; then
        log_warn "源码已存在，正在更新..."
        git_fetch_with_fallback "$INSTALL_DIR" "main"
        cd "$INSTALL_DIR"
        git reset --hard origin/main
    else
        cd "$(dirname "$INSTALL_DIR")"
        git_clone_with_fallback "$(basename "$INSTALL_DIR")"
        cd "$INSTALL_DIR"
    fi

    log_success "源码已就绪: $INSTALL_DIR"
}

# -----------------------------------------------------------------------------
# 配置服务
# -----------------------------------------------------------------------------

setup_config() {
    log_info "配置服务..."

    # 创建配置目录
    sudo mkdir -p "$CONFIG_DIR"
    sudo mkdir -p "$CONFIG_DIR/uploaded_files"

    # 复制配置文件
    if [ ! -f "$CONFIG_DIR/config.json" ]; then
        sudo cp "$INSTALL_DIR/Server/config.json.example" "$CONFIG_DIR/config.json"
        sudo chown $(whoami):$(whoami) "$CONFIG_DIR/config.json"
        log_warn "配置文件已创建: $CONFIG_DIR/config.json"
        log_warn "请编辑配置文件填入 API 密钥"
    else
        # 校验已有配置文件的JSON格式
        local parse_result
        parse_result=$(python3 -c "
import json, sys
try:
    with open('$CONFIG_DIR/config.json', 'r', encoding='utf-8') as f:
        json.load(f)
    print('OK')
except json.JSONDecodeError as e:
    print(f'ERROR|line {e.lineno}, col {e.colno}: {e.msg}')
except Exception as e:
    print(f'ERROR|{e}')
" 2>&1)

        if [ "$parse_result" = "OK" ]; then
            log_success "配置文件JSON格式正确"
        else
            local error_detail="${parse_result#ERROR|}"
            log_error "配置文件JSON格式错误: $error_detail"
            log_error "文件路径: $CONFIG_DIR/config.json"
            echo ""
            read -p "是否从模板重置配置文件? API密钥需重新配置 (y/N): " reset_confirm
            if [ "$reset_confirm" == "y" ] || [ "$reset_confirm" == "Y" ]; then
                # 备份旧文件
                sudo cp "$CONFIG_DIR/config.json" "$CONFIG_DIR/config.json.bak.$(date +%Y%m%d%H%M%S)"
                sudo cp "$INSTALL_DIR/Server/config.json.example" "$CONFIG_DIR/config.json"
                sudo chown $(whoami):$(whoami) "$CONFIG_DIR/config.json"
                log_warn "配置文件已重置，旧文件已备份为 config.json.bak.*"
                log_warn "请编辑配置文件填入 API 密钥: $CONFIG_DIR/config.json"
            else
                log_warn "请手动修复配置文件后重新部署"
            fi
        fi
    fi
}

# -----------------------------------------------------------------------------
# 检查docker compose可用性
# -----------------------------------------------------------------------------

check_docker_compose() {
    # 优先使用新版 docker compose
    if docker compose version &> /dev/null 2>&1; then
        echo "docker compose"
        return 0
    # 回退到旧版 docker-compose
    elif command -v docker-compose &> /dev/null 2>&1; then
        echo "docker-compose"
        return 0
    else
        return 1
    fi
}

# -----------------------------------------------------------------------------
# 检测网络环境，不可达时自动配置中国镜像加速（Docker Hub + apt + pip）
# -----------------------------------------------------------------------------

configure_docker_hub_mirror() {
    local dockerfile="$1"
    local mirror_prefix="docker.1ms.run/"

    log_info "检测 Docker Hub 可达性..."

    # 测试 registry-1.docker.io 连接（5秒超时）
    if curl -s --connect-timeout 5 -o /dev/null -w "%{http_code}" "https://registry-1.docker.io/v2/" 2>/dev/null | grep -qE "^(200|401)"; then
        log_success "Docker Hub 连接正常，使用官方源"
        return 0
    fi

    log_warn "Docker Hub 连接失败，配置中国镜像加速..."

    # ---- 1. 修改 Dockerfile 的 FROM 行，加上镜像前缀 ----
    if [ -f "$dockerfile" ]; then
        if grep -q "^FROM python:" "$dockerfile"; then
            sed -i "s|^FROM python:|FROM ${mirror_prefix}library/python:|g" "$dockerfile"
            log_info "已修改 Dockerfile FROM 使用镜像: ${mirror_prefix}library/python:3.11-slim"
        fi

        # ---- 2. apt 源替换为清华镜像（python:3.11-slim 基于 Debian bookworm）----
        # 在 apt-get update 之前插入一行 RUN，将 deb.debian.org / security.debian.org 替换为清华源
        # 兼容 bookworm 的 DEB822 格式 (/etc/apt/sources.list.d/debian.sources) 和传统格式 (/etc/apt/sources.list)
        if grep -q "apt-get update" "$dockerfile"; then
            sed -i '/apt-get update/i\RUN sed -i "s|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null; \\' "$dockerfile"
            sed -i '/apt-get update/i\    sed -i "s|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null; \\' "$dockerfile"
            sed -i '/apt-get update/i\    sed -i "s|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g" /etc/apt/sources.list 2>/dev/null; \\' "$dockerfile"
            sed -i '/apt-get update/i\    sed -i "s|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g" /etc/apt/sources.list 2>/dev/null; \\' "$dockerfile"
            sed -i '/apt-get update/i\    true' "$dockerfile"
            log_info "已配置容器内 apt 源: mirrors.tuna.tsinghua.edu.cn"
        fi

        # ---- 3. pip 源替换为清华 PyPI 镜像 ----
        if grep -q "pip install.*-r requirements.txt" "$dockerfile"; then
            sed -i 's|pip install --no-cache-dir -r requirements.txt|pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -r requirements.txt|g' "$dockerfile"
            log_info "已配置容器内 pip 源: pypi.tuna.tsinghua.edu.cn"
        fi
    fi

    # ---- 4. 配置 daemon.json 守护进程级镜像加速 ----
    sudo mkdir -p /etc/docker
    sudo tee /etc/docker/daemon.json > /dev/null << EOF
{
    "registry-mirrors": ["https://docker.1ms.run"],
    "dns": ["8.8.8.8", "8.8.4.4"]
}
EOF
    log_info "已配置 daemon.json 镜像加速"

    # 重启 Docker 使 daemon.json 生效
    if command -v systemctl &> /dev/null; then
        sudo systemctl daemon-reload
        sudo systemctl restart docker 2>/dev/null || true
        # 等待 Docker 启动完成
        sleep 2
    fi

    log_success "中国镜像加速已全部配置完成"
}

# -----------------------------------------------------------------------------
# 部署服务
# -----------------------------------------------------------------------------

deploy_service() {
    log_info "部署服务..."

    cd "$INSTALL_DIR/Server"

    # 确保脚本可执行
    chmod +x docker-entrypoint.sh

    # 检测 Docker Hub 可达性，不可达时自动配置镜像加速
    configure_docker_hub_mirror "$INSTALL_DIR/Server/Dockerfile"

    # 检查docker compose可用性
    COMPOSE_CMD=$(check_docker_compose)
    if [ $? -ne 0 ]; then
        log_warn "docker compose 未安装，尝试安装..."
        sudo apt-get install -y docker-compose-plugin || sudo apt-get install -y docker-compose
        COMPOSE_CMD=$(check_docker_compose)
        if [ $? -ne 0 ]; then
            log_error "无法安装 docker compose，请手动安装后重试"
            return 1
        fi
    fi

    log_info "使用命令: $COMPOSE_CMD"

    # 启动服务
    if [ "$COMPOSE_CMD" = "docker compose" ]; then
        sudo docker compose up -d
    else
        sudo docker-compose up -d
    fi

    log_success "服务已部署!"
    log_info "查看日志: $COMPOSE_CMD logs -f"
    log_info "访问地址: http://localhost:8000"
}

# -----------------------------------------------------------------------------
# 获取公网IP地址
# -----------------------------------------------------------------------------

get_public_ip() {
    local ip=""

    # 依次尝试多个公共服务获取公网IP
    for cmd in \
        "curl -s --connect-timeout 5 https://ifconfig.me" \
        "curl -s --connect-timeout 5 https://ip.sb" \
        "curl -s --connect-timeout 5 https://api.ipify.org" \
        "curl -s --connect-timeout 5 https://checkip.amazonaws.com" \
        "curl -s --connect-timeout 5 https://myip.ipip.net" \
    ; do
        ip=$(eval "$cmd" 2>/dev/null | tr -d '[:space:]')
        # 验证是否为合法IPv4地址
        if [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            echo "$ip"
            return 0
        fi
    done

    # 回退：获取本机IP
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "$ip"
        return 0
    fi

    echo "localhost"
    return 1
}

# -----------------------------------------------------------------------------
# 询问服务器地址
# -----------------------------------------------------------------------------

get_server_url() {
    echo ""
    log_info "=== 配置 Server 地址 ==="

    # 自动获取公网IP作为默认地址
    local public_ip
    public_ip=$(get_public_ip)
    local default_url="http://${public_ip}:8000"

    echo ""
    read -p "请输入 Server 地址 (格式: http://IP:端口，留空使用默认 $default_url): " server_url

    if [ -z "$server_url" ]; then
        # 读取配置文件中的端口，拼接公网IP
        if [ -f "$CONFIG_DIR/config.json" ]; then
            port=$(grep -o '"port"[[:space:]]*:[[:space:]]*[0-9]*' "$CONFIG_DIR/config.json" 2>/dev/null | grep -o '[0-9]*$' | head -1)
            if [ -n "$port" ]; then
                server_url="http://${public_ip}:$port"
            else
                server_url="$default_url"
            fi
        else
            server_url="$default_url"
        fi
    fi

    # 确保地址格式正确
    if [[ ! "$server_url" =~ ^https?:// ]]; then
        server_url="http://$server_url"
    fi

    echo ""
    log_success "将使用 Server 地址: $server_url"
    echo ""
    read -p "确认继续编译? (y/n): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        log_info "取消编译"
        return 1
    fi

    SERVER_URL="$server_url"
}

# -----------------------------------------------------------------------------
# 编译Windows客户端
# -----------------------------------------------------------------------------

build_exe() {
    log_info "开始编译客户端..."

    # 检查Docker
    if ! check_command docker; then
        log_error "请先安装 Docker"
        return 1
    fi

    # 检查源码
    if [ ! -d "$INSTALL_DIR/winClient" ]; then
        log_error "源码目录不存在，请先执行安装"
        return 1
    fi

    # 获取服务器地址
    get_server_url || return 0

    # 检测 Go 模块代理可达性，不可达时使用 goproxy.cn 加速
    GOPROXY_URL="https://proxy.golang.org,direct"
    log_info "检测 Go 模块代理..."
    if ! curl -s --connect-timeout 5 -o /dev/null -w "%{http_code}" "https://proxy.golang.org" 2>/dev/null | grep -qE "^(200|301|302|404)"; then
        GOPROXY_URL="https://goproxy.cn,direct"
        log_warn "proxy.golang.org 不可达，切换到 goproxy.cn"
    else
        log_success "Go 模块代理连接正常"
    fi

    # 创建输出目录
    mkdir -p "$INSTALL_DIR/dist"

    # ==================== Windows 客户端 ====================
    log_info "=== 编译 Windows 客户端 ==="

    # 使用加速器拉取Go镜像并编译
    GOLANG_IMAGE="${DOCKER_MIRROR}/library/golang:1.24.1"
    log_info "使用镜像: $GOLANG_IMAGE"

    # 编译标准版
    log_info "编译标准版 windows_check.exe..."
    log_info "注入 Server 地址: $SERVER_URL"
    docker run --rm \
        -v "$INSTALL_DIR/winClient:/app" \
        -w /app \
        -e GOPROXY="$GOPROXY_URL" \
        "$GOLANG_IMAGE" \
        sh -c "GOOS=windows GOARCH=amd64 go build -ldflags '-s -w -X main.defaultServerURL=$SERVER_URL' -o /app/windows_check.exe main.go"

    # 复制到输出目录
    cp "$INSTALL_DIR/winClient/windows_check.exe" "$INSTALL_DIR/dist/"
    log_success "windows_check.exe 编译完成"

    # 编译增强版
    log_info "编译增强版 windows_check_gaint.exe..."
    docker run --rm \
        -v "$INSTALL_DIR/windowsclient_gaint:/app" \
        -w /app \
        -e GOPROXY="$GOPROXY_URL" \
        "$GOLANG_IMAGE" \
        sh -c "GOOS=windows GOARCH=amd64 go build -ldflags '-s -w -X main.defaultServerURL=$SERVER_URL' -o /app/windows_check_gaint.exe ."

    # 复制到输出目录
    cp "$INSTALL_DIR/windowsclient_gaint/windows_check_gaint.exe" "$INSTALL_DIR/dist/"
    log_success "windows_check_gaint.exe 编译完成"

    # ==================== Linux 客户端打包 ====================
    log_info ""
    log_info "=== 打包 Linux 客户端 ==="

    # 打包标准版 Linux 客户端
    log_info "打包 LinuxClient.tar.gz..."
    cd "$INSTALL_DIR"
    rm -f LinuxClient.tar.gz linuxclient_gaint.tar.gz

    # 复制并修改客户端脚本中的Server地址
    mkdir -p "$INSTALL_DIR/dist/linux_client_temp"
    cp -r "$INSTALL_DIR/LinuxClient/"* "$INSTALL_DIR/dist/linux_client_temp/"

    # 使用环境变量方式注入Server地址
    if [ -f "$INSTALL_DIR/dist/linux_client_temp/client.sh" ]; then
        # 替换默认Server URL
        sed -i "s|DEFAULT_SERVER_URL=\"\${AIIR_SERVER_URL:-}\"|DEFAULT_SERVER_URL=\"$SERVER_URL\"|g" "$INSTALL_DIR/dist/linux_client_temp/client.sh"
        # 兼容其他可能的占位符格式
        sed -i "s|http://localhost:8000|$SERVER_URL|g" "$INSTALL_DIR/dist/linux_client_temp/client.sh"
        sed -i "s|http://YOUR_SERVER_IP:PORT|$SERVER_URL|g" "$INSTALL_DIR/dist/linux_client_temp/client.sh"
    fi

    # 打包
    cd "$INSTALL_DIR/dist/linux_client_temp"
    tar -czvf "$INSTALL_DIR/dist/LinuxClient.tar.gz" .
    cd "$INSTALL_DIR"
    rm -rf "$INSTALL_DIR/dist/linux_client_temp"
    log_success "LinuxClient.tar.gz 打包完成"

    # 打包增强版 Linux 客户端
    log_info "打包 linuxclient_gaint.tar.gz..."
    mkdir -p "$INSTALL_DIR/dist/linuxclient_gaint_temp"
    cp -r "$INSTALL_DIR/linuxclient_gaint/"* "$INSTALL_DIR/dist/linuxclient_gaint_temp/"

    if [ -f "$INSTALL_DIR/dist/linuxclient_gaint_temp/client_gaint.sh" ]; then
        sed -i "s|DEFAULT_SERVER_URL=\"\${AIIR_SERVER_URL:-}\"|DEFAULT_SERVER_URL=\"$SERVER_URL\"|g" "$INSTALL_DIR/dist/linuxclient_gaint_temp/client_gaint.sh"
        sed -i "s|http://localhost:8000|$SERVER_URL|g" "$INSTALL_DIR/dist/linuxclient_gaint_temp/client_gaint.sh"
        sed -i "s|http://YOUR_SERVER_IP:PORT|$SERVER_URL|g" "$INSTALL_DIR/dist/linuxclient_gaint_temp/client_gaint.sh"
    fi

    cd "$INSTALL_DIR/dist/linuxclient_gaint_temp"
    tar -czvf "$INSTALL_DIR/dist/linuxclient_gaint.tar.gz" .
    cd "$INSTALL_DIR"
    rm -rf "$INSTALL_DIR/dist/linuxclient_gaint_temp"
    log_success "linuxclient_gaint.tar.gz 打包完成"

    log_info ""
    log_success "所有客户端编译完成！"
    log_info "Server 地址已预置: $SERVER_URL"
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}         编译产物清单${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo -e "  ${BLUE}Windows 标准版:${NC}   $INSTALL_DIR/dist/windows_check.exe"
    echo -e "  ${BLUE}Windows 增强版:${NC}   $INSTALL_DIR/dist/windows_check_gaint.exe"
    echo -e "  ${BLUE}Linux   标准版:${NC}   $INSTALL_DIR/dist/LinuxClient.tar.gz"
    echo -e "  ${BLUE}Linux   增强版:${NC}   $INSTALL_DIR/dist/linuxclient_gaint.tar.gz"
    echo ""
    echo -e "  ${YELLOW}下载目录:${NC} $INSTALL_DIR/dist/"
    echo ""
    ls -lh "$INSTALL_DIR/dist/"
    echo ""
    log_info "将对应客户端分发到目标机器即可使用，Server 地址已内嵌"
}

# -----------------------------------------------------------------------------
# 升级版本
# -----------------------------------------------------------------------------

upgrade_version() {
    log_info "开始升级版本..."

    # 检查docker compose可用性
    COMPOSE_CMD=$(check_docker_compose)
    if [ $? -ne 0 ]; then
        log_error "docker compose 未安装，请先安装"
        return 1
    fi

    # 停止服务
    log_info "停止服务..."
    cd "$INSTALL_DIR/Server"
    if [ "$COMPOSE_CMD" = "docker compose" ]; then
        sudo docker compose down
    else
        sudo docker-compose down
    fi

    # 重置可能被镜像加速修改过的 Dockerfile，避免 git pull 冲突
    cd "$INSTALL_DIR"
    git checkout -- Server/Dockerfile 2>/dev/null || true

    # 更新源码
    log_info "更新源码..."
    cd "$INSTALL_DIR"
    git_fetch_with_fallback "$INSTALL_DIR" "main"
    git reset --hard origin/main

    # 校验现有配置文件，如有语法错误则提示修复
    setup_config

    # 检测 Docker Hub 可达性，不可达时自动配置镜像加速
    configure_docker_hub_mirror "$INSTALL_DIR/Server/Dockerfile"

    # 重建镜像
    log_info "重建 Docker 镜像..."
    cd "$INSTALL_DIR/Server"
    if [ "$COMPOSE_CMD" = "docker compose" ]; then
        sudo docker compose build --no-cache
    else
        sudo docker-compose build --no-cache
    fi

    # 启动服务
    log_info "启动服务..."
    if [ "$COMPOSE_CMD" = "docker compose" ]; then
        sudo docker compose up -d
    else
        sudo docker-compose up -d
    fi

    log_success "升级完成！"
    log_info "查看日志: $COMPOSE_CMD logs -f"
}

# -----------------------------------------------------------------------------
# 服务控制
# -----------------------------------------------------------------------------

# 获取 compose 命令（内部辅助）
_get_compose_cmd() {
    local cmd
    cmd=$(check_docker_compose)
    if [ $? -ne 0 ]; then
        echo ""
        return 1
    fi
    echo "$cmd"
}

manage_service() {
    local action="$1"

    if [ ! -d "$INSTALL_DIR/Server" ]; then
        log_error "服务未安装，请先执行安装"
        return 1
    fi

    local COMPOSE_CMD
    COMPOSE_CMD=$(_get_compose_cmd)
    if [ -z "$COMPOSE_CMD" ]; then
        log_error "docker compose 未安装"
        return 1
    fi

    cd "$INSTALL_DIR/Server"

    case "$action" in
        start)
            log_info "启动 AIIR Server..."
            sudo $COMPOSE_CMD up -d
            log_success "服务已启动"
            sudo $COMPOSE_CMD ps
            ;;
        stop)
            log_info "停止 AIIR Server..."
            sudo $COMPOSE_CMD down
            log_success "服务已停止"
            ;;
        restart)
            log_info "重启 AIIR Server..."
            sudo $COMPOSE_CMD restart
            log_success "服务已重启"
            sudo $COMPOSE_CMD ps
            ;;
        status)
            echo ""
            echo -e "${BLUE}=== AIIR Server 状态 ===${NC}"
            sudo $COMPOSE_CMD ps
            echo ""
            echo -e "${BLUE}=== 健康检查 ===${NC}"
            curl -s --connect-timeout 3 http://localhost:8000/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "服务未响应（可能正在启动中）"
            ;;
        logs)
            log_info "显示 AIIR Server 日志（Ctrl+C 退出）..."
            sudo $COMPOSE_CMD logs -f --tail=100
            ;;
        *)
            log_error "未知操作: $action"
            return 1
            ;;
    esac
}

# 服务控制子菜单
service_menu() {
    while true; do
        echo ""
        echo -e "${BLUE}============ 服务控制 ============${NC}"
        echo "1. 启动服务"
        echo "2. 停止服务"
        echo "3. 重启服务"
        echo "4. 查看状态"
        echo "5. 查看日志"
        echo "0. 返回主菜单"
        echo ""
        echo -n "请输入选项 [0-5]: "
        read sub_choice

        case $sub_choice in
            1) manage_service start ;;
            2) manage_service stop ;;
            3) manage_service restart ;;
            4) manage_service status ;;
            5) manage_service logs ;;
            0) return ;;
            *) log_error "无效选项" ;;
        esac

        echo ""
        read -p "按 Enter 键继续..." dummy
    done
}

# -----------------------------------------------------------------------------
# 显示状态
# -----------------------------------------------------------------------------

show_status() {
    log_info "=== AIIR 服务状态 ==="

    if systemctl is-active docker &> /dev/null; then
        echo -e "Docker: ${GREEN}运行中${NC}"
    else
        echo -e "Docker: ${RED}未运行${NC}"
    fi

    if [ -d "$INSTALL_DIR" ]; then
        echo -e "安装目录: $INSTALL_DIR"

        if [ -d "$INSTALL_DIR/.git" ]; then
            cd "$INSTALL_DIR"
            echo -e "当前版本: $(git rev-parse --short HEAD)"
            echo -e "最新提交: $(git log -1 --pretty=%s)"
        fi
    fi

    echo ""
    echo -e "=== Docker 容器状态 ==="
    COMPOSE_CMD=$(check_docker_compose)
    if [ $? -eq 0 ] && [ -d "$INSTALL_DIR/Server" ]; then
        cd "$INSTALL_DIR/Server"
        if [ "$COMPOSE_CMD" = "docker compose" ]; then
            sudo docker compose ps 2>/dev/null || echo "服务未部署"
        else
            sudo docker-compose ps 2>/dev/null || echo "服务未部署"
        fi
    else
        echo "服务未部署"
    fi
}

# -----------------------------------------------------------------------------
# 主菜单
# -----------------------------------------------------------------------------

show_menu() {
    clear
    echo "============================================"
    echo "         AIIR 一键安装脚本"
    echo "         AI驱动的安全应急响应分析系统"
    echo "============================================"
    echo ""
    echo "1. 部署服务端 (Docker安装 + 源码部署)"
    echo "2. 编译客户端 (exe编译 + Linux打包)"
    echo "3. 更新版本 (停止服务 + 拉取代码 + 重建)"
    echo "4. 服务控制 (启动/停止/重启/日志)"
    echo "5. 查看状态"
    echo "6. 卸载"
    echo "0. 退出"
    echo ""
    echo -n "请输入选项 [0-6]: "
}

# 卸载
uninstall() {
    log_warn "即将卸载 AIIR 服务..."
    read -p "确认卸载? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "取消卸载"
        return
    fi

    log_info "停止服务..."
    COMPOSE_CMD=$(check_docker_compose)
    if [ $? -eq 0 ] && [ -d "$INSTALL_DIR/Server" ]; then
        cd "$INSTALL_DIR/Server"
        if [ "$COMPOSE_CMD" = "docker compose" ]; then
            sudo docker compose down 2>/dev/null || true
        else
            sudo docker-compose down 2>/dev/null || true
        fi
    fi

    log_info "删除安装目录..."
    sudo rm -rf "$INSTALL_DIR"

    log_info "删除配置目录..."
    sudo rm -rf "$CONFIG_DIR"

    log_success "卸载完成!"
}

# -----------------------------------------------------------------------------
# 主程序
# -----------------------------------------------------------------------------

main() {
    # 检查root权限
    if [ "$EUID" -ne 0 ]; then
        log_warn "建议使用 sudo 运行此脚本以获得完整功能"
    fi

    while true; do
        show_menu
        read choice

        case $choice in
            1)
                install_docker
                clone_source
                setup_config
                deploy_service
                echo ""
                read -p "是否立即编译 exe? (y/N): " confirm
                if [ "$confirm" == "y" ] || [ "$confirm" == "Y" ]; then
                    build_exe
                fi
                ;;
            2)
                if [ ! -d "$INSTALL_DIR" ]; then
                    log_error "请先安装源码"
                    continue
                fi
                build_exe
                ;;
            3)
                if [ ! -d "$INSTALL_DIR" ]; then
                    log_error "请先安装"
                    continue
                fi
                upgrade_version
                ;;
            4)
                service_menu
                ;;
            5)
                show_status
                ;;
            6)
                uninstall
                ;;
            0)
                log_info "再见!"
                exit 0
                ;;
            *)
                log_error "无效选项"
                ;;
        esac

        echo ""
        read -p "按 Enter 键继续..." dummy
    done
}

# 运行主程序
main "$@"
