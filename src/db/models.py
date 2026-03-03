"""
数据库模型

职责：定义 PostgreSQL 数据模型
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship, declarative_base


Base = declarative_base()


class TaskModel(Base):
    """任务数据模型"""
    
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    status = Column(String(50), default="pending")
    priority = Column(String(50), default="normal")
    
    assigned_to = Column(String, nullable=True)
    parent_task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    subtasks = relationship("TaskModel", backref="parent_task", remote_side=[id])


class AgentModel(Base):
    """Agent 数据模型"""
    
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    state = Column(String(50), default="idle")
    enabled = Column(Boolean, default=True)
    
    current_task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    
    # 统计
    tasks_completed = Column(Integer, default=0)
    tasks_failed = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class WorkflowModel(Base):
    """工作流数据模型"""
    
    __tablename__ = "workflows"
    
    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    state = Column(String(50), default="running")
    
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)


class BlackboardEntryModel(Base):
    """黑板条目数据模型"""
    
    __tablename__ = "blackboard_entries"
    
    id = Column(String, primary_key=True)
    key = Column(String(100), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    owner_id = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    expires_at = Column(DateTime, nullable=True)
