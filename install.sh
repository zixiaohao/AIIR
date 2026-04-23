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
# Docker镜像加速
DOCKER_MIRRORS=(
    "https://docker.1ms.run"
)

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

# 检测网络连接
check_network() {
    log_info "检测网络连接..."
    
    # 测试GitHub连接
    if curl -s --connect-timeout 5 https://github.com > /dev/null 2>&1; then
        log_success "GitHub 连接正常"
        return 0
    fi
    
    # 测试Gitee镜像连接
    if curl -s --connect-timeout 5 https://gitee.com > /dev/null 2>&1; then
        log_warn "GitHub 连接失败，尝试使用 Gitee 镜像..."
        REPO_URL="https://gitee.com/zixiaohao/aiir.git"
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

# 配置Docker镜像加速
setup_docker_mirror() {
    log_info "配置 Docker 镜像加速..."
    
    # 创建Docker配置目录
    mkdir -p ~/.docker
    
    # 尝试添加镜像源
    for mirror in "${DOCKER_MIRRORS[@]}"; do
        if curl -s --connect-timeout 3 "$mirror" > /dev/null 2>&1; then
            log_success "使用镜像: $mirror"
            cat > ~/.docker/daemon.json << EOF
{
    "registry-mirrors": ["$mirror"],
    "dns": ["8.8.8.8", "8.8.4.4"]
}
EOF
            break
        fi
    done
    
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
    
    # 检测网络并选择合适的镜像源
    log_info "检测网络环境..."
    USE_MIRROR=false
    
    # 先测试官方源是否可用
    if ! curl -s --connect-timeout 5 https://download.docker.com/linux/ubuntu/gpg > /dev/null 2>&1; then
        log_warn "官方源连接失败，切换到国内镜像源..."
        USE_MIRROR=true
        
        # 更换apt源为清华镜像
        log_info "配置 apt 镜像源..."
        sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak 2>/dev/null || true
        sudo sed -i 's/cn.archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
        sudo sed -i 's/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
    fi
    
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
    
    if [ "$USE_MIRROR" = true ]; then
        # 使用清华镜像源
        if curl -fsSL https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg 2>/dev/null; then
            log_success "使用清华 Docker 镜像源"
            DOCKER_REPO="deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/ubuntu $(lsb_release -cs) stable"
        else
            # 回退到官方源
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            DOCKER_REPO="deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
        fi
    else
        # 优先使用官方源
        if curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg 2>/dev/null; then
            log_success "使用官方 Docker 源"
            DOCKER_REPO="deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
        else
            # 回退到清华镜像源
            curl -fsSL https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            log_success "使用清华 Docker 镜像源"
            DOCKER_REPO="deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/ubuntu $(lsb_release -cs) stable"
        fi
    fi
    
    # 添加Docker仓库
    echo "$DOCKER_REPO" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # 安装Docker
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
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
        cd "$INSTALL_DIR"
        git pull origin main
    else
        cd "$(dirname "$INSTALL_DIR")"
        git clone "$REPO_URL" "$(basename "$INSTALL_DIR")"
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
        log_info "配置文件已存在，跳过"
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
# 部署服务
# -----------------------------------------------------------------------------

deploy_service() {
    log_info "部署服务..."
    
    cd "$INSTALL_DIR/Server"
    
    # 确保脚本可执行
    chmod +x docker-entrypoint.sh
    
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
# 询问服务器地址
# -----------------------------------------------------------------------------

get_server_url() {
    echo ""
    log_info "=== 配置 Server 地址 ==="
    echo ""
    read -p "请输入 Server 地址 (格式: http://IP:端口，留空使用默认): " server_url
    
    if [ -z "$server_url" ]; then
        # 读取配置文件中的地址
        if [ -f "$CONFIG_DIR/config.json" ]; then
            # 简单提取配置文件中的端口
            port=$(grep -o '"port"[[:space:]]*:[[:space:]]*[0-9]*' "$CONFIG_DIR/config.json" 2>/dev/null | grep -o '[0-9]*$' | head -1)
            if [ -n "$port" ]; then
                server_url="http://localhost:$port"
            else
                server_url="http://localhost:8000"
            fi
        else
            server_url="http://localhost:8000"
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
    
    # 创建输出目录
    mkdir -p "$INSTALL_DIR/dist"
    
    # ==================== Windows 客户端 ====================
    log_info "=== 编译 Windows 客户端 ==="
    
    # 编译标准版
    log_info "编译标准版 windows_check.exe..."
    log_info "注入 Server 地址: $SERVER_URL"
    docker run --rm \
        -v "$INSTALL_DIR/winClient:/app" \
        -w /app \
        golang:1.24.1 \
        sh -c "GOOS=windows GOARCH=amd64 go build -ldflags '-s -w -X main.defaultServerURL=$SERVER_URL' -o /app/windows_check.exe main.go"
    
    # 复制到输出目录
    cp "$INSTALL_DIR/winClient/windows_check.exe" "$INSTALL_DIR/dist/"
    log_success "windows_check.exe 编译完成"
    
    # 编译增强版
    log_info "编译增强版 windows_check_gaint.exe..."
    docker run --rm \
        -v "$INSTALL_DIR/windowsclient_gaint:/app" \
        -w /app \
        golang:1.24.1 \
        sh -c "GOOS=windows GOARCH=amd64 go build -ldflags '-s -w -X main.defaultServerURL=$SERVER_URL' -o /app/windows_check_gaint.exe main_gaint.go"
    
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
    
    # 使用环境变量方式注入Server地址
    if [ -f "$INSTALL_DIR/dist/linuxclient_gaint_temp/client_gaint.sh" ]; then
        # 替换默认Server URL
        sed -i "s|DEFAULT_SERVER_URL=\"\${AIIR_SERVER_URL:-}\"|DEFAULT_SERVER_URL=\"$SERVER_URL\"|g" "$INSTALL_DIR/dist/linuxclient_gaint_temp/client_gaint.sh"
        # 兼容其他可能的占位符格式
        sed -i "s|http://localhost:8000|$SERVER_URL|g" "$INSTALL_DIR/dist/linuxclient_gaint_temp/client_gaint.sh"
        sed -i "s|http://YOUR_SERVER_IP:PORT|$SERVER_URL|g" "$INSTALL_DIR/dist/linuxclient_gaint_temp/client_gaint.sh"
    fi
    
    # 打包
    cd "$INSTALL_DIR/dist/linuxclient_gaint_temp"
    tar -czvf "$INSTALL_DIR/dist/linuxclient_gaint.tar.gz" .
    cd "$INSTALL_DIR"
    rm -rf "$INSTALL_DIR/dist/linuxclient_gaint_temp"
    log_success "linuxclient_gaint.tar.gz 打包完成"
    
    log_info ""
    log_success "所有客户端编译完成！"
    log_info "Server 地址已预置到客户端中"
    log_info "输出目录: $INSTALL_DIR/dist"
    echo ""
    echo "=== 产物列表 ==="
    ls -lh "$INSTALL_DIR/dist/"
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
    
    # 更新源码
    log_info "更新源码..."
    cd "$INSTALL_DIR"
    git pull origin main
    
    # 重建镜像
    log_info "重建 Docker 镜像..."
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
    echo "4. 查看状态"
    echo "5. 卸载"
    echo "0. 退出"
    echo ""
    echo -n "请输入选项 [0-5]: "
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
    # 查root权限
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
                show_status
                ;;
            5)
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