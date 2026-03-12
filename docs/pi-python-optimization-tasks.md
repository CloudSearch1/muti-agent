# PI-Python 优化任务清单

生成时间: 2026-03-12

## 🔴 高优先级（立即修复）

### 1. 替换 print 为日志系统

**位置:**
- `pi_python/extensions/loader.py:86`
- `pi_python/extensions/loader.py:156`
- `pi_python/extensions/loader.py:160`
- `pi_python/extensions/api.py:134`

**建议:**
```python
# 替换前
print(f"Failed to load extension {name}: {e}")

# 替换后
import logging
logger = logging.getLogger(__name__)
logger.error(f"Failed to load extension {name}: {e}")
```

### 2. 拆分长函数

**2.1 `pi_python/ai/types.py:to_openai_messages` (55行)**

建议拆分为:
```python
def _convert_message_to_openai(msg: Message) -> dict:
    """转换单个消息"""
    ...

def _convert_content_to_openai(content: Content) -> dict:
    """转换内容"""
    ...

def to_openai_messages(self) -> list[dict]:
    """转换为 OpenAI 格式"""
    return [_convert_message_to_openai(m) for m in self.messages]
```

**2.2 `pi_python/skills/loader.py:create_builtin_skills` (61行)**

建议拆分为:
```python
def _create_file_skill(name: str, description: str) -> Skill:
    """创建文件操作技能"""
    ...

def _create_shell_skill() -> Skill:
    """创建 shell 技能"""
    ...

def create_builtin_skills() -> list[Skill]:
    """创建所有内置技能"""
    return [
        _create_file_skill(...),
        _create_shell_skill(),
        ...
    ]
```

## 🟡 中优先级（本周完成）

### 3. 消除代码重复

**3.1 注册/获取函数重复**

位置:
- `adapter.py:register` vs `ai/model.py:register_provider`
- `adapter.py:get` vs `ai/model.py:get_provider`
- `adapter.py:list_providers` vs `ai/model.py:list_providers`

建议: 统一使用 `ai/model.py` 的实现

**3.2 格式转换函数重复**

位置:
- `ai/types.py:to_openai_format` vs `to_anthropic_format`

建议: 提取公共部分到 `_convert_content()` 辅助函数

**3.3 EventBuilder 方法重复**

位置:
- `ai/stream.py:text_start/text_end/thinking_start/thinking_end`

建议: 使用工厂函数或元编程减少重复

### 4. 添加文档字符串

**缺少文档字符串的模块:**
- `ai/providers/other.py` - 所有提供商函数
- `agent/tools.py` - 工具执行相关函数
- `extensions/api.py` - API 装饰器

**模板:**
```python
def function_name(param: type) -> return_type:
    """
    简要描述函数功能。
    
    Args:
        param: 参数说明
        
    Returns:
        返回值说明
        
    Raises:
        ExceptionType: 异常情况
        
    Example:
        >>> result = function_name(value)
        >>> print(result)
    """
```

### 5. 完善类型注解

**缺少类型注解的文件:**
- `adapter.py` - 6个位置
- `ai/model.py` - 7个位置
- `agent/session.py` - 4个位置
- `extensions/loader.py` - 5个位置

## 🟢 低优先级（可选）

### 6. 性能优化

**6.1 缓存重复计算**

位置: `ai/types.py:Context.to_openai_messages`

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def _cached_convert(messages_tuple: tuple) -> list[dict]:
    """缓存转换结果"""
    ...
```

**6.2 异步优化**

检查所有 `async def` 函数是否真正需要异步

### 7. 代码风格统一

**7.1 统一导入风格**
```python
# 标准库
import os
from typing import Optional

# 第三方库
import httpx
from pydantic import BaseModel

# 本地模块
from .types import Model
```

**7.2 统一命名规范**
- 函数名: `snake_case`
- 类名: `PascalCase`
- 常量: `UPPER_CASE`

## 📋 执行计划

### 第1天（今天）
- [ ] 替换 print 为日志
- [ ] 拆分 `to_openai_messages` 函数
- [ ] 拆分 `create_builtin_skills` 函数

### 第2天
- [ ] 消除注册/获取函数重复
- [ ] 添加关键文档字符串

### 第3天
- [ ] 完善类型注解
- [ ] 运行测试确保通过

### 第4天
- [ ] 代码审查
- [ ] 提交优化

## 🎯 验收标准

- [ ] ruff 检查 0 错误
- [ ] mypy 检查通过
- [ ] 所有测试通过
- [ ] 代码复杂度 < 10
- [ ] 文档字符串覆盖率 > 80%
- [ ] 类型注解覆盖率 > 90%

## 📝 备注

- 保持向后兼容
- 每次修改后运行测试
- 分阶段提交，便于回滚
- 记录重大设计变更
