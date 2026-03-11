#!/bin/bash

# 公网访问问题一键排查脚本
# 用于诊断 Gunicorn/FastAPI 应用无法公网访问的问题

set -e

echo "=========================================="
echo "    公网访问问题一键排查脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查结果统计
ISSUES=0

# 获取本机 IP
LOCAL_IP=$(hostname -I | awk '{print $1}')
HOSTNAME=$(hostname)

echo -e "${YELLOW}[信息]${NC} 服务器信息"
echo "  - 主机名: $HOSTNAME"
echo "  - 本机 IP: $LOCAL_IP"

# 尝试获取公网 IP
echo ""
echo "正在获取公网 IP..."
PUBLIC_IP=$(curl -s --connect-timeout 3 ifconfig.me 2>/dev/null || curl -s --connect-timeout 3 ip.sb 2>/dev/null || echo "获取失败")
echo -e "${YELLOW}[信息]${NC} 公网 IP: $PUBLIC_IP"
echo ""

# ==========================================
# 1. 检查端口监听状态
# ==========================================
echo "=========================================="
echo "1. 检查端口监听状态 (8080)"
echo "=========================================="

if command -v ss &> /dev/null; then
    PORT_STATUS=$(ss -tlnp 2>/dev/null | grep ":8080 " || true)
elif command -v netstat &> /dev/null; then
    PORT_STATUS=$(netstat -tlnp 2>/dev/null | grep ":8080 " || true)
else
    PORT_STATUS=""
fi

if [ -n "$PORT_STATUS" ]; then
    echo "$PORT_STATUS"

    # 检查是否监听所有接口
    if echo "$PORT_STATUS" | grep -q "0.0.0.0:8080\|:::8080"; then
        echo -e "${GREEN}[OK]${NC} 端口正确监听所有接口 (0.0.0.0:8080)"
    elif echo "$PORT_STATUS" | grep -q "127.0.0.1:8080"; then
        echo -e "${RED}[问题]${NC} 端口只监听本地回环地址 (127.0.0.1:8080)"
        echo -e "${YELLOW}[解决]${NC} 需要修改配置绑定 0.0.0.0:8080"
        ((ISSUES++))
    else
        echo -e "${YELLOW}[警告]${NC} 请检查端口监听配置"
    fi
else
    echo -e "${RED}[问题]${NC} 8080 端口未监听"
    echo -e "${YELLOW}[解决]${NC} 请先启动 Gunicorn 服务"
    ((ISSUES++))
fi
echo ""

# ==========================================
# 2. 检查 Gunicorn 进程
# ==========================================
echo "=========================================="
echo "2. 检查 Gunicorn 进程"
echo "=========================================="

GUNICORN_PIDS=$(pgrep -f gunicorn || true)
if [ -n "$GUNICORN_PIDS" ]; then
    echo -e "${GREEN}[OK]${NC} Gunicorn 进程运行中"
    echo "PID 列表: $(echo $GUNICORN_PIDS | tr '\n' ' ')"

    # 检查进程详情
    MASTER_PID=$(echo "$GUNICORN_PIDS" | head -1)
    if [ -n "$MASTER_PID" ]; then
        echo ""
        echo "进程信息:"
        ps -p $MASTER_PID -o pid,ppid,cmd --no-headers 2>/dev/null || true
    fi
else
    echo -e "${RED}[问题]${NC} Gunicorn 进程未运行"
    echo -e "${YELLOW}[解决]${NC} 请启动服务: ./start_production.sh"
    ((ISSUES++))
fi
echo ""

# ==========================================
# 3. 检查本地访问
# ==========================================
echo "=========================================="
echo "3. 检查本地访问"
echo "=========================================="

echo "测试 http://127.0.0.1:8080 ..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 http://127.0.0.1:8080 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "304" ]; then
    echo -e "${GREEN}[OK]${NC} 本地访问正常 (HTTP $HTTP_CODE)"
elif [ "$HTTP_CODE" = "000" ]; then
    echo -e "${RED}[问题]${NC} 本地连接失败"
    ((ISSUES++))
else
    echo -e "${YELLOW}[警告]${NC} 本地返回 HTTP $HTTP_CODE"
fi

# 测试内网 IP
echo ""
echo "测试 http://$LOCAL_IP:8080 ..."
HTTP_CODE2=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 http://$LOCAL_IP:8080 2>/dev/null || echo "000")

if [ "$HTTP_CODE2" = "200" ] || [ "$HTTP_CODE2" = "304" ]; then
    echo -e "${GREEN}[OK]${NC} 内网 IP 访问正常 (HTTP $HTTP_CODE2)"
elif [ "$HTTP_CODE2" = "000" ]; then
    echo -e "${RED}[问题]${NC} 内网 IP 连接失败 - 可能是防火墙阻止"
    ((ISSUES++))
else
    echo -e "${YELLOW}[警告]${NC} 内网 IP 返回 HTTP $HTTP_CODE2"
fi
echo ""

# ==========================================
# 4. 检查防火墙 (ufw)
# ==========================================
echo "=========================================="
echo "4. 检查防火墙 (ufw)"
echo "=========================================="

if command -v ufw &> /dev/null; then
    UFW_STATUS=$(sudo ufw status 2>/dev/null || echo "无法获取状态")
    echo "$UFW_STATUS"

    if echo "$UFW_STATUS" | grep -q "Status: active"; then
        echo ""
        echo "检查 8080 端口规则..."
        if sudo ufw status | grep -q "8080"; then
            echo -e "${GREEN}[OK]${NC} ufw 已允许 8080 端口"
        else
            echo -e "${RED}[问题]${NC} ufw 未允许 8080 端口"
            echo -e "${YELLOW}[解决]${NC} 执行: sudo ufw allow 8080/tcp"
            ((ISSUES++))
        fi
    else
        echo -e "${GREEN}[OK]${NC} ufw 未启用"
    fi
else
    echo "ufw 未安装 (Ubuntu/Debian 默认防火墙)"
fi
echo ""

# ==========================================
# 5. 检查防火墙 (firewalld)
# ==========================================
echo "=========================================="
echo "5. 检查防火墙 (firewalld)"
echo "=========================================="

if command -v firewall-cmd &> /dev/null; then
    if systemctl is-active firewalld &>/dev/null; then
        echo -e "${YELLOW}[信息]${NC} firewalld 运行中"
        echo ""
        echo "开放的端口:"
        sudo firewall-cmd --list-ports 2>/dev/null || echo "无法获取"

        echo ""
        echo "检查 8080 端口..."
        if sudo firewall-cmd --list-ports 2>/dev/null | grep -q "8080"; then
            echo -e "${GREEN}[OK]${NC} firewalld 已开放 8080 端口"
        else
            echo -e "${RED}[问题]${NC} firewalld 未开放 8080 端口"
            echo -e "${YELLOW}[解决]${NC} 执行: sudo firewall-cmd --permanent --add-port=8080/tcp && sudo firewall-cmd --reload"
            ((ISSUES++))
        fi
    else
        echo -e "${GREEN}[OK]${NC} firewalld 未运行"
    fi
else
    echo "firewalld 未安装 (CentOS/RHEL 默认防火墙)"
fi
echo ""

# ==========================================
# 6. 检查 iptables
# ==========================================
echo "=========================================="
echo "6. 检查 iptables 规则"
echo "=========================================="

if command -v iptables &> /dev/null; then
    IPTABLES_RULES=$(sudo iptables -L INPUT -n 2>/dev/null | grep -E "8080|Chain" || true)

    if [ -n "$IPTABLES_RULES" ]; then
        echo "$IPTABLES_RULES"

        if echo "$IPTABLES_RULES" | grep -q "8080"; then
            echo -e "${GREEN}[OK]${NC} iptables 有 8080 相关规则"
        else
            echo -e "${YELLOW}[注意]${NC} 未找到 8080 端口的 iptables 规则"
            echo -e "${YELLOW}[解决]${NC} 如需添加: sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT"
        fi
    else
        echo "无法获取 iptables 规则 (可能需要 root 权限)"
    fi
else
    echo "iptables 未安装"
fi
echo ""

# ==========================================
# 7. 检查 SELinux
# ==========================================
echo "=========================================="
echo "7. 检查 SELinux (仅 CentOS/RHEL)"
echo "=========================================="

if command -v getenforce &> /dev/null; then
    SELINUX_STATUS=$(getenforce 2>/dev/null || echo "Unknown")
    echo "SELinux 状态: $SELINUX_STATUS"

    if [ "$SELINUX_STATUS" = "Enforcing" ]; then
        echo -e "${YELLOW}[注意]${NC} SELinux 处于 Enforcing 模式"
        echo -e "${YELLOW}[解决]${NC} 临时关闭: sudo setenforce 0"
        echo -e "${YELLOW}[解决]${NC} 或允许端口: sudo semanage port -a -t http_port_t -p tcp 8080"
    else
        echo -e "${GREEN}[OK]${NC} SELinux 未阻止"
    fi
else
    echo "SELinux 未安装 (仅 CentOS/RHEL)"
fi
echo ""

# ==========================================
# 8. 检查安全组提示
# ==========================================
echo "=========================================="
echo "8. 云服务器安全组检查"
echo "=========================================="

if echo "$HOSTNAME" | grep -q "iZ"; then
    echo -e "${YELLOW}[重要]${NC} 检测到阿里云服务器"
    echo ""
    echo "请确保阿里云安全组已配置以下规则："
    echo "  - 协议类型: TCP"
    echo "  - 端口范围: 8080/8080"
    echo "  - 授权对象: 0.0.0.0/0"
    echo ""
    echo "配置路径："
    echo "  阿里云控制台 → 云服务器 ECS → 实例详情 → 安全组 → 配置规则 → 入方向 → 添加规则"
    echo ""
    echo -e "${YELLOW}[提示]${NC} 90% 的公网访问问题都是因为安全组未配置！"
fi

if echo "$HOSTNAME" | grep -q "i-"; then
    echo -e "${YELLOW}[重要]${NC} 检测到可能是 AWS 服务器"
    echo ""
    echo "请确保 AWS Security Group 已配置以下规则："
    echo "  - Type: Custom TCP"
    echo "  - Port: 8080"
    echo "  - Source: 0.0.0.0/0"
fi
echo ""

# ==========================================
# 总结
# ==========================================
echo "=========================================="
echo "排查总结"
echo "=========================================="
echo ""

if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}[OK]${NC} 未检测到本地配置问题"
    echo ""
    if echo "$HOSTNAME" | grep -q "iZ"; then
        echo -e "${YELLOW}[最可能的原因]${NC} 阿里云安全组未开放 8080 端口"
        echo ""
        echo "请按以下步骤操作："
        echo "1. 登录阿里云控制台: https://ecs.console.aliyun.com/"
        echo "2. 找到实例: $HOSTNAME"
        echo "3. 点击「安全组」→「配置规则」"
        echo "4. 在「入方向」添加规则: TCP 8080 允许 0.0.0.0/0"
    fi
else
    echo -e "${RED}[问题]${NC} 检测到 $ISSUES 个问题需要解决"
    echo ""
    echo "请根据上述提示逐一解决。"
fi
echo ""

# ==========================================
# 快速测试命令
# ==========================================
echo "=========================================="
echo "快速测试命令"
echo "=========================================="
echo ""
echo "在服务器执行:"
echo "  curl -I http://127.0.0.1:8080"
echo "  curl -I http://$LOCAL_IP:8080"
echo ""
echo "在本地电脑执行:"
echo "  curl -I http://$PUBLIC_IP:8080"
echo "  telnet $PUBLIC_IP 8080"
echo ""
echo "=========================================="
echo "排查完成"
echo "=========================================="