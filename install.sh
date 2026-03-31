#!/bin/bash
#
# ScoreForge 依赖安装脚本 (Linux / macOS)
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1"
}

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

check_python() {
    info "检查 Python 版本..."
    
    if command -v python3 &> /dev/null; then
        PYTHON=python3
    elif command -v python &> /dev/null; then
        PYTHON=python
    else
        error "未找到 Python，请先安装 Python 3.6+"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 6 ]]; then
        error "Python 版本过低: $PYTHON_VERSION，需要 3.6+"
        exit 1
    fi
    
    info "Python 版本: $PYTHON_VERSION ✓"
}

setup_venv() {
    VENV_DIR="piano-trans"
    
    if [[ -d "$VENV_DIR" ]]; then
        warn "虚拟环境已存在: $VENV_DIR"
        read -p "是否重新创建？(y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "跳过虚拟环境创建"
            return
        fi
        rm -rf "$VENV_DIR"
    fi
    
    info "创建虚拟环境: $VENV_DIR"
    $PYTHON -m venv "$VENV_DIR"
    info "虚拟环境创建成功"
}

install_python_deps() {
    info "安装 Python 依赖..."
    
    source piano-trans/bin/activate
    pip install --upgrade pip -q
    
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        info "Python 依赖安装完成"
    else
        error "未找到 requirements.txt"
        exit 1
    fi
}

check_musescore() {
    info "检查 MuseScore..."
    
    if command -v musescore3 &> /dev/null; then
        MUSESCORE_VERSION=$(musescore3 --version 2>&1 | head -n1)
        info "MuseScore 已安装: $MUSESCORE_VERSION ✓"
    elif command -v mscore &> /dev/null; then
        MUSESCORE_VERSION=$(mscore --version 2>&1 | head -n1)
        info "MuseScore 已安装: $MUSESCORE_VERSION ✓"
        warn "检测到 mscore 命令，可能需要在使用时指定 --musescore-path mscore"
    else
        warn "未检测到 MuseScore"
        echo ""
        echo "请手动安装 MuseScore:"
        echo ""
        OS=$(detect_os)
        if [[ "$OS" == "linux" ]]; then
            echo "  Ubuntu/Debian:"
            echo "    sudo apt install musescore3"
            echo ""
            echo "  Fedora:"
            echo "    sudo dnf install musescore"
            echo ""
            echo "  Arch:"
            echo "    sudo pacman -S musescore"
        elif [[ "$OS" == "macos" ]]; then
            echo "  Homebrew:"
            echo "    brew install musescore"
            echo ""
            echo "  或从官网下载: https://musescore.org/"
        else
            echo "  请从官网下载: https://musescore.org/"
        fi
        echo ""
    fi
}

print_usage() {
    echo ""
    echo "=========================================="
    echo "  ScoreForge 安装完成！"
    echo "=========================================="
    echo ""
    echo "使用方式："
    echo ""
    echo "  1. 激活虚拟环境："
    echo "     source piano-trans/bin/activate"
    echo ""
    echo "  2. 命令行使用："
    echo "     python scoreforge.py input.wav"
    echo ""
    echo "  3. 网页界面："
    echo "     streamlit run streamlit_app.py"
    echo ""
    echo "更多用法请查看 README.md"
    echo ""
}

main() {
    echo ""
    echo "=========================================="
    echo "  ScoreForge 依赖安装"
    echo "=========================================="
    echo ""
    
    check_python
    setup_venv
    install_python_deps
    check_musescore
    print_usage
}

main
