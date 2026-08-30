#!/bin/bash
# ═══════════════════════════════════════════
#  Ops Bundle 一键部署脚本
#  用法: bash /opt/ttdazi/ops/deploy.sh
# ═══════════════════════════════════════════
set -e

OPS_DIR="/opt/ttdazi/ops"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🛡️  Ops Bundle 部署开始"
echo "═══════════════════════════"

# 1. 安装依赖
echo ""
echo "📦 安装Python依赖..."
pip3 install numpy pymysql pyyaml -q 2>/dev/null || \
pip install numpy pymysql pyyaml -q 2>/dev/null || \
echo "⚠️ pip安装失败，请手动安装: pip3 install numpy pymysql pyyaml"

# 2. 检查MySQL
echo ""
echo "🗄️  检查MySQL..."
if command -v mysql &>/dev/null; then
    echo "  ✅ mysql客户端已安装"
else
    echo "  ⚠️ mysql客户端未安装，部分功能不可用"
fi

# 3. 检查openssl/curl/dig
echo ""
echo "🔧 检查工具..."
for tool in openssl curl dig; do
    if command -v $tool &>/dev/null; then
        echo "  ✅ $tool"
    else
        echo "  ⚠️ $tool 未安装"
    fi
done

# 4. 创建目录结构
echo ""
echo "📁 创建目录..."
mkdir -p "$OPS_DIR"/{data,state,logs,auto_tools,rules}

# 5. 设置权限
echo ""
echo "🔐 设置权限..."
chmod +x "$OPS_DIR"/*.py 2>/dev/null || true
chmod +x "$OPS_DIR"/deploy.sh 2>/dev/null || true

# 6. 安装systemd服务
echo ""
echo "⚙️  安装systemd服务..."
if [ -w /etc/systemd/system/ ]; then
    cat > /etc/systemd/system/ops-engine.service << 'EOF'
[Unit]
Description=Ops自治引擎 - YAML规则驱动自动检测+修复
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/ttdazi/ops/engine.py --daemon 60
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable ops-engine.service 2>/dev/null
    echo "  ✅ ops-engine服务已安装"
else
    echo "  ⚠️ 需要sudo权限安装systemd服务"
    echo "  运行: sudo bash $0"
fi

# 7. 采集初始数据（给智能分析用）
echo ""
echo "📊 采集初始数据..."
for i in $(seq 1 10); do
    python3 "$OPS_DIR/intelligence.py" --collect > /dev/null 2>&1
    sleep 0.3
done
echo "  ✅ 采集了10个数据点"

# 8. 启动引擎
echo ""
echo "🚀 启动引擎..."
if systemctl is-active ops-engine &>/dev/null; then
    systemctl restart ops-engine
    echo "  ✅ 引擎已重启"
elif systemctl list-unit-files | grep -q ops-engine; then
    systemctl start ops-engine
    echo "  ✅ 引擎已启动"
else
    echo "  ⚠️ 引擎未安装（需要sudo）"
fi

# 9. 验证
echo ""
echo "✅ 验证..."
echo "  opsctl状态:"
python3 "$OPS_DIR/opsctl.py" status 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'    {d.get(\"summary\",\"?\")}')" 2>/dev/null || echo "    ⚠️ opsctl运行异常"

echo "  引擎状态:"
systemctl is-active ops-engine 2>/dev/null && echo "    ✅ 运行中" || echo "    ⚠️ 未运行"

echo ""
echo "═══════════════════════════"
echo "✅ 部署完成！"
echo ""
echo "常用命令:"
echo "  python3 $OPS_DIR/opsctl.py status      # 全站状态"
echo "  python3 $OPS_DIR/opsctl.py health      # 健康检查"
echo "  python3 $OPS_DIR/opsctl.py --help      # 帮助"
echo "  python3 $OPS_DIR/engine.py --status    # 引擎状态"
echo "  python3 $OPS_DIR/intelligence.py --analyze  # 智能报告"
echo "  python3 $OPS_DIR/autopilot.py --report # 自动开发建议"
