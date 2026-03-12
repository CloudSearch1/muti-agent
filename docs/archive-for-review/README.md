# 📋 文档清理清单 - 待审查

**创建日期**: 2026-03-12  
**审查人**: 项目维护者  
**操作**: 请审查以下文档，确认后执行相应操作

---

## 🗂️ 待归档/删除的文档清单

### 1️⃣ 历史遗留文档 (项目前期报告)

这些文档是项目早期的技术报告和评估，当前项目已更名为 **IntelliTeam**，这些文档对最终用户价值有限，建议归档。

**文件列表**:
```
docs/pi-python-design.md              (31.91 KB)  - 旧项目设计文档
docs/pi-python-code-review.md          (3.34 KB)  - 代码审查报告
docs/pi-python-completion-report.md    (1.13 KB)  - 完成报告
docs/pi-python-final-report.md         (4.33 KB)  - 最终报告
docs/pi-python-optimization-tasks.md   (4.29 KB)  - 优化任务
docs/pi-python-quality-report.md       (2 KB)     - 质量报告
docs/pi-python-skills-guide.md         (6.43 KB)  - 技能指南
docs/PHASE1_DETAILED_PLAN.md           (36.7 KB)  - 阶段计划
docs/SKILLS_503_ERROR_FIX.md           (3.73 KB)  - 错误修复报告
```

**建议操作**: ➡️ 移动到 `docs/archive/` 目录

---

### 2️⃣ 优化报告 (技术细节)

这些文档是性能优化的详细报告，适合归档保存，但不需要放在主文档目录中。

**文件列表**:
```
docs/local_llm_optimization_report.md      (6.46 KB)
docs/memory_optimization_report.md          (5.48 KB)
docs/OPTIMIZATION_REPORT_LLM_API.md         (7.7 KB)
docs/skills_optimization_report.md          (4.57 KB)
```

**建议操作**: ➡️ 移动到 `docs/archive/optimization-reports/` 目录

---

### 3️⃣ 重复文档 (需要合并)

#### 3.1 部署文档重复

**问题**: 根目录和 docs/ 目录都有部署文档，内容重叠

```
DEPLOY.md (根目录)              - 基础部署教程
docs/DEPLOYMENT.md              - 详细部署指南
```

**建议操作**: 
- 审查两个文档的内容
- 将 DEPLOY.md 中的有价值内容合并到 docs/DEPLOYMENT.md
- ➡️ 将 DEPLOY.md 移动到待删除目录

**合并要点**:
- DEPLOY.md 中的 Gunicorn 配置示例很有价值，建议保留
- DEPLOY.md 中的故障排查部分可以整合
- 统一端口信息为 8000

#### 3.2 路线图重复

**问题**: 根目录和 docs/ 目录都有 ROADMAP.md

```
ROADMAP.md (根目录)             - 项目路线图
docs/ROADMAP.md                 - 同上 (可能重复)
```

**建议操作**:
- 比较两个文件的内容
- 保留最完整的一个在 docs/ 目录
- ➡️ 删除根目录的 ROADMAP.md

---

### 4️⃣ 需要重命名的文档

#### 4.1 中文命名文档

**问题**: 不符合国际化规范

```
docs/公网访问排查指南.md
```

**建议操作**: ➡️ 重命名为 `docs/deployment/network-troubleshooting.md`

#### 4.2 缩写命名文档

**问题**: 不易理解

```
docs/DOCKER_INSTALL.md
```

**建议操作**: ➡️ 重命名为 `docs/deployment/docker-installation.md`

---

## 📊 清理统计

| 类别 | 文件数量 | 总大小 | 操作建议 |
|-----|---------|--------|---------|
| 历史遗留 | 9 | ~95 KB | 归档 |
| 优化报告 | 4 | ~24 KB | 归档 |
| 重复文档 | 2 | ~17 KB | 合并后删除 |
| 待重命名 | 2 | ~10 KB | 重命名 |
| **总计** | **17** | **~146 KB** | **-** |

---

## 🎯 操作步骤

### 第 1 步: 创建归档目录

```bash
cd "M:\AI Agent\muti-agent"
mkdir docs\archive
mkdir docs\archive\optimization-reports
```

### 第 2 步: 移动历史遗留文档

```bash
cd "M:\AI Agent\muti-agent\docs"

move pi-python-*.md archive\
move PHASE1_DETAILED_PLAN.md archive\
move SKILLS_503_ERROR_FIX.md archive\
```

### 第 3 步: 移动优化报告

```bash
cd "M:\AI Agent\muti-agent\docs"

move local_llm_optimization_report.md archive\optimization-reports\
move memory_optimization_report.md archive\optimization-reports\
move OPTIMIZATION_REPORT_LLM_API.md archive\optimization-reports\
move skills_optimization_report.md archive\optimization-reports\
```

### 第 4 步: 合并重复文档

1. **合并 DEPLOY.md**:
   ```bash
   # 手动审查 DEPLOY.md 和 docs/DEPLOYMENT.md
   # 将 DEPLOY.md 中有价值的内容复制到 docs/DEPLOYMENT.md
   # 然后执行:
   move DEPLOY.md docs\archive-for-review\
   ```

2. **处理 ROADMAP.md**:
   ```bash
   # 比较 ROADMAP.md 和 docs/ROADMAP.md
   # 保留完整版本在 docs/ 目录
   # 然后执行:
   move ROADMAP.md docs\archive-for-review\
   ```

### 第 5 步: 重命名文档

```bash
cd "M:\AI Agent\muti-agent\docs"

move 公网访问排查指南.md deployment\network-troubleshooting.md
move DOCKER_INSTALL.md deployment\docker-installation.md
```

---

## ✅ 审查清单

请在执行操作前确认:

- [ ] 已备份重要文档
- [ ] 已通知团队成员
- [ ] 已审查历史遗留文档的内容
- [ ] 已比较重复文档的差异
- [ ] 已确定合并策略

请在执行操作后确认:

- [ ] 所有文件已正确移动
- [ ] 没有破坏现有链接
- [ ] 更新了相关引用
- [ ] 测试了文档中的链接

---

## 📞 需要帮助?

如果在审查过程中发现:

1. **某个文档不应被归档** - 请将其移回原位
2. **需要保留但位置不对** - 请移动到合适的位置
3. **内容有价值但需要更新** - 请更新后保留
4. **不确定如何处理** - 请添加到"待讨论"列表

---

## 📝 待讨论列表

如果发现无法决定的文档，请添加到此处：

```
- [ ] 文件名 - 原因
```

---

**下一步行动**: 
1. 审查以上清单
2. 执行确认的操作
3. 删除 `docs/archive-for-review/` 目录
4. 继续 Phase 2: 创建新的文档结构

*清单创建时间: 2026-03-12*  
*审查人: 待填写*  
*执行状态: 待开始*
