#!/bin/bash
# Skills API 诊断脚本

echo "========== Skills API 诊断 =========="
echo ""

# 测试不同路径
echo "1. 测试 /api/v1/skills (不带斜杠)"
curl -s http://47.253.152.159:8080/api/v1/skills | head -c 200
echo ""
echo ""

echo "2. 测试 /api/v1/skills/ (带斜杠)"
curl -s http://47.253.152.159:8080/api/v1/skills/ | head -c 200
echo ""
echo ""

echo "3. 检查响应头"
echo "不带斜杠："
curl -sI http://47.253.152.159:8080/api/v1/skills | grep -E "HTTP|Content-Type|Location"
echo ""
echo "带斜杠："
curl -sI http://47.253.152.159:8080/api/v1/skills/ | grep -E "HTTP|Content-Type"
echo ""

echo "4. 检查是否有重定向"
echo "访问 /api/v1/skills 的完整响应："
curl -sL http://47.253.152.159:8080/api/v1/skills 2>&1 | head -c 300
echo ""
echo ""

echo "========== 诊断完成 =========="
