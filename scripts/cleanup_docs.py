#!/usr/bin/env python3
"""
文档清理脚本 - Phase 1
清理历史遗留文档和重复文档
"""

import os
import shutil
from pathlib import Path

def main():
    project_root = Path("M:/AI Agent/muti-agent")
    docs_dir = project_root / "docs"
    archive_dir = docs_dir / "archive" / "20260312"
    
    print("📁 创建归档目录...")
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # 需要归档的文件列表
    files_to_archive = [
        # pi-python 系列文档
        "pi-python-design.md",
        "pi-python-code-review.md",
        "pi-python-completion-report.md",
        "pi-python-final-report.md",
        "pi-python-optimization-tasks.md",
        "pi-python-quality-report.md",
        "pi-python-skills-guide.md",
        # 其他历史文档
        "PHASE1_DETAILED_PLAN.md",
        "SKILLS_503_ERROR_FIX.md",
        # 优化报告
        "local_llm_optimization_report.md",
        "memory_optimization_report.md",
        "OPTIMIZATION_REPORT_LLM_API.md",
        "skills_optimization_report.md",
    ]
    
    print("📦 归档历史文档...")
    archived_count = 0
    for filename in files_to_archive:
        file_path = docs_dir / filename
        if file_path.exists():
            try:
                shutil.move(str(file_path), str(archive_dir))
                print(f"  ✓ 已归档: {filename}")
                archived_count += 1
            except Exception as e:
                print(f"  ✗ 归档失败: {filename} - {e}")
        else:
            print(f"  - 跳过: {filename} (不存在)")
    
    print(f"\n📊 归档完成: {archived_count} 个文件已归档到 {archive_dir}")
    
    # 合并 DEPLOY.md 到 docs/DEPLOYMENT.md
    print("\n🔄 合并部署文档...")
    deploy_root = project_root / "DEPLOY.md"
    deploy_docs = docs_dir / "DEPLOYMENT.md"
    
    if deploy_root.exists() and deploy_docs.exists():
        try:
            # 读取 DEPLOY.md 内容
            deploy_content = deploy_root.read_text(encoding='utf-8')
            
            # 读取 DEPLOYMENT.md 内容
            deployment_content = deploy_docs.read_text(encoding='utf-8')
            
            # 合并内容 (简单追加)
            merged_content = deployment_content + "\n\n" + "="*60 + "\n\n" + deploy_content
            
            # 备份原文件
            shutil.copy(str(deploy_docs), str(deploy_docs) + ".backup")
            
            # 写入合并后的内容
            deploy_docs.write_text(merged_content, encoding='utf-8')
            
            # 移动原文件到归档目录
            shutil.move(str(deploy_root), str(archive_dir / "DEPLOY.md"))
            
            print("  ✓ DEPLOY.md 已合并到 docs/DEPLOYMENT.md")
            print("  ✓ 原 DEPLOY.md 已归档")
        except Exception as e:
            print(f"  ✗ 合并失败: {e}")
    else:
        print("  - DEPLOY.md 或 docs/DEPLOYMENT.md 不存在")
    
    # 移动 ROADMAP.md
    print("\n🔄 移动 ROADMAP.md...")
    roadmap_root = project_root / "ROADMAP.md"
    roadmap_docs = docs_dir / "ROADMAP.md"
    
    if roadmap_root.exists():
        try:
            if roadmap_docs.exists():
                # 备份已有的 docs/ROADMAP.md
                shutil.copy(str(roadmap_docs), str(roadmap_docs) + ".backup")
            
            # 移动文件
            shutil.move(str(roadmap_root), str(roadmap_docs))
            print("  ✓ ROADMAP.md 已移动到 docs/ 目录")
        except Exception as e:
            print(f"  ✗ 移动失败: {e}")
    else:
        print("  - ROADMAP.md 不存在")
    
    print("\n✅ Phase 1 完成！")
    print(f"📂 归档目录: {archive_dir}")
    print("📝 下一步: 执行 Phase 2 - 创建目录结构和组织文档")

if __name__ == "__main__":
    main()
