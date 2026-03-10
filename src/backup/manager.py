"""
数据备份恢复

自动备份和恢复数据库、配置文件等
"""

import asyncio
import json
import logging
import shutil
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BackupManager:
    """
    备份管理器

    功能:
    - 自动备份
    - 定时备份
    - 增量备份
    - 备份恢复
    - 备份清理
    """

    def __init__(
        self,
        backup_dir: str = "backups",
        max_backups: int = 10,
    ):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.max_backups = max_backups
        self.backup_history: list[dict[str, Any]] = []

        self._load_history()
        logger.info(f"BackupManager initialized: {self.backup_dir}")

    def _load_history(self):
        """加载备份历史"""
        history_file = self.backup_dir / "history.json"

        if history_file.exists():
            try:
                with open(history_file, encoding="utf-8") as f:
                    self.backup_history = json.load(f)
            except Exception as e:
                logger.error(f"Load backup history failed: {e}")

    def _save_history(self):
        """保存备份历史"""
        history_file = self.backup_dir / "history.json"

        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(self.backup_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Save backup history failed: {e}")

    async def backup_database(
        self,
        db_path: str,
        backup_name: str | None = None,
    ) -> str:
        """
        备份数据库

        Args:
            db_path: 数据库文件路径
            backup_name: 备份名称（可选）

        Returns:
            备份文件路径
        """
        db_file = Path(db_path)

        if not db_file.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        # 生成备份名称
        if not backup_name:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = f"database_{timestamp}"

        backup_file = self.backup_dir / f"{backup_name}.db"

        # 复制数据库文件
        shutil.copy2(db_file, backup_file)

        # 记录历史
        self.backup_history.append({
            "name": backup_name,
            "type": "database",
            "source": str(db_path),
            "backup_file": str(backup_file),
            "size": backup_file.stat().st_size,
            "created_at": datetime.utcnow().isoformat(),
        })

        self._save_history()
        self._cleanup_old_backups()

        logger.info(f"Database backed up: {backup_file}")

        return str(backup_file)

    async def backup_config(
        self,
        config_files: list[str],
        backup_name: str | None = None,
    ) -> str:
        """
        备份配置文件

        Args:
            config_files: 配置文件列表
            backup_name: 备份名称

        Returns:
            备份文件路径
        """
        if not backup_name:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = f"config_{timestamp}"

        backup_file = self.backup_dir / f"{backup_name}.tar.gz"

        # 创建压缩包
        with tarfile.open(backup_file, "w:gz") as tar:
            for config_file in config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    tar.add(config_path, arcname=config_path.name)

        # 记录历史
        self.backup_history.append({
            "name": backup_name,
            "type": "config",
            "source": config_files,
            "backup_file": str(backup_file),
            "size": backup_file.stat().st_size,
            "created_at": datetime.utcnow().isoformat(),
        })

        self._save_history()
        self._cleanup_old_backups()

        logger.info(f"Config backed up: {backup_file}")

        return str(backup_file)

    async def backup_full(
        self,
        db_path: str,
        config_files: list[str],
        backup_name: str | None = None,
    ) -> str:
        """
        完整备份（数据库 + 配置）

        Args:
            db_path: 数据库文件路径
            config_files: 配置文件列表
            backup_name: 备份名称

        Returns:
            备份文件路径
        """
        if not backup_name:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_name = f"full_{timestamp}"

        backup_file = self.backup_dir / f"{backup_name}.tar.gz"

        # 创建临时目录
        temp_dir = self.backup_dir / f"temp_{backup_name}"
        temp_dir.mkdir(exist_ok=True)

        try:
            # 复制数据库
            db_file = Path(db_path)
            if db_file.exists():
                shutil.copy2(db_file, temp_dir / db_file.name)

            # 复制配置
            for config_file in config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    shutil.copy2(config_path, temp_dir / config_path.name)

            # 创建压缩包
            with tarfile.open(backup_file, "w:gz") as tar:
                for file in temp_dir.iterdir():
                    tar.add(file, arcname=file.name)

            # 记录历史
            self.backup_history.append({
                "name": backup_name,
                "type": "full",
                "source": [db_path] + config_files,
                "backup_file": str(backup_file),
                "size": backup_file.stat().st_size,
                "created_at": datetime.utcnow().isoformat(),
            })

            self._save_history()
            self._cleanup_old_backups()

            logger.info(f"Full backup created: {backup_file}")

            return str(backup_file)

        finally:
            # 清理临时目录
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    async def restore_database(
        self,
        backup_file: str,
        db_path: str,
    ):
        """
        恢复数据库

        Args:
            backup_file: 备份文件路径
            db_path: 数据库文件路径
        """
        backup_path = Path(backup_file)

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_file}")

        # 备份当前数据库
        db_file = Path(db_path)
        if db_file.exists():
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            await self.backup_database(db_path, f"pre_restore_{timestamp}")

        # 恢复数据库
        shutil.copy2(backup_path, db_file)

        logger.info(f"Database restored from: {backup_file}")

    async def restore_config(
        self,
        backup_file: str,
        target_dir: str,
    ):
        """
        恢复配置

        Args:
            backup_file: 备份文件路径
            target_dir: 目标目录
        """
        backup_path = Path(backup_file)

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_file}")

        target_path = Path(target_dir)
        target_path.mkdir(parents=True, exist_ok=True)

        # 解压备份
        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall(target_path)

        logger.info(f"Config restored to: {target_dir}")

    def list_backups(self) -> list[dict[str, Any]]:
        """列出所有备份"""
        return self.backup_history

    def delete_backup(self, backup_name: str):
        """删除备份"""
        backup = next(
            (b for b in self.backup_history if b["name"] == backup_name),
            None,
        )

        if backup:
            backup_file = Path(backup["backup_file"])
            if backup_file.exists():
                backup_file.unlink()

            self.backup_history.remove(backup)
            self._save_history()

            logger.info(f"Backup deleted: {backup_name}")

    def _cleanup_old_backups(self):
        """清理旧备份"""
        if len(self.backup_history) <= self.max_backups:
            return

        # 按时间排序
        sorted_backups = sorted(
            self.backup_history,
            key=lambda b: b["created_at"],
        )

        # 删除最旧的备份
        backups_to_delete = sorted_backups[:len(sorted_backups) - self.max_backups]

        for backup in backups_to_delete:
            self.delete_backup(backup["name"])

    def get_stats(self) -> dict[str, Any]:
        """获取统计"""
        total_size = sum(b["size"] for b in self.backup_history)

        return {
            "total_backups": len(self.backup_history),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / 1024 / 1024,
            "oldest_backup": self.backup_history[0]["created_at"] if self.backup_history else None,
            "newest_backup": self.backup_history[-1]["created_at"] if self.backup_history else None,
        }


# ============ 定时备份 ============

class ScheduledBackup:
    """定时备份"""

    def __init__(
        self,
        backup_manager: BackupManager,
        interval_hours: int = 24,
        db_path: str | None = None,
        config_files: list[str] | None = None,
    ):
        self.backup_manager = backup_manager
        self.interval_hours = interval_hours
        self.db_path = db_path
        self.config_files = config_files or []

        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """启动定时备份"""
        self._running = True
        self._task = asyncio.create_task(self._backup_loop())
        logger.info(f"Scheduled backup started (interval={self.interval_hours}h)")

    async def stop(self):
        """停止定时备份"""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Scheduled backup stopped")

    async def _backup_loop(self):
        """备份循环"""
        while self._running:
            try:
                await asyncio.sleep(self.interval_hours * 3600)

                if self.db_path and self.config_files:
                    await self.backup_manager.backup_full(
                        self.db_path,
                        self.config_files,
                    )
                elif self.db_path:
                    await self.backup_manager.backup_database(self.db_path)
                elif self.config_files:
                    await self.backup_manager.backup_config(self.config_files)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduled backup failed: {e}")


# ============ 全局管理器 ============

_manager: BackupManager | None = None


def get_backup_manager() -> BackupManager:
    """获取备份管理器"""
    global _manager
    if _manager is None:
        _manager = BackupManager()
    return _manager


def init_backup_manager(**kwargs) -> BackupManager:
    """初始化备份管理器"""
    global _manager
    _manager = BackupManager(**kwargs)
    logger.info("Backup manager initialized")
    return _manager
