"""
IntelliTeam 工具函数模块

提供通用工具函数
"""

from datetime import datetime
from typing import Any, Dict, List
import hashlib
import random
import string


def generate_id(prefix: str = "") -> str:
    """
    生成唯一 ID
    
    Args:
        prefix: ID 前缀
        
    Returns:
        唯一 ID 字符串
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    unique_id = f"{prefix}{timestamp}{random_suffix}" if prefix else f"{timestamp}{random_suffix}"
    return unique_id


def hash_password(password: str) -> str:
    """
    密码哈希
    
    Args:
        password: 原始密码
        
    Returns:
        哈希后的密码
    """
    return hashlib.sha256(password.encode()).hexdigest()


def format_duration(seconds: float) -> str:
    """
    格式化时长
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化后的时长字符串
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.2f}h"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截断文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 后缀字符串
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    # 保留 max_length - len(suffix) 个字符，然后添加后缀
    return text[:max_length] + suffix


def safe_get(dictionary: Dict, key: str, default: Any = None) -> Any:
    """
    安全获取字典值
    
    Args:
        dictionary: 字典
        key: 键名
        default: 默认值
        
    Returns:
        字典值或默认值
    """
    try:
        return dictionary.get(key, default)
    except:
        return default


def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """
    合并字典
    
    Args:
        dict1: 字典 1
        dict2: 字典 2
        
    Returns:
        合并后的字典
    """
    return {**dict1, **dict2}


def filter_dict(dictionary: Dict, keys: List[str]) -> Dict:
    """
    过滤字典，只保留指定键
    
    Args:
        dictionary: 原始字典
        keys: 要保留的键列表
        
    Returns:
        过滤后的字典
    """
    return {key: dictionary[key] for key in keys if key in dictionary}


def is_valid_email(email: str) -> bool:
    """
    验证邮箱格式
    
    Args:
        email: 邮箱地址
        
    Returns:
        是否有效
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_valid_url(url: str) -> bool:
    """
    验证 URL 格式
    
    Args:
        url: URL 地址
        
    Returns:
        是否有效
    """
    import re
    pattern = r'^https?://[^\s]+$'
    return bool(re.match(pattern, url))
