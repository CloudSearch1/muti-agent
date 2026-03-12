"""文本处理工具函数"""
import re


def clean_json_from_markdown(text: str) -> str:
    """
    清理 markdown 代码块包装的 JSON

    移除 markdown 代码块标记（```json 或 ```），返回清理后的 JSON 字符串。
    支持多种格式：
    - ```json\\n{...}\\n```
    - ```\\n{...}\\n```
    - 直接的 JSON 字符串

    Args:
        text: 原始文本，可能包含 markdown 代码块标记

    Returns:
        清理后的 JSON 字符串

    Examples:
        >>> clean_json_from_markdown('```json\\n{"key": "value"}\\n```')
        '{"key": "value"}'
        >>> clean_json_from_markdown('```\\n{"key": "value"}\\n```')
        '{"key": "value"}'
        >>> clean_json_from_markdown('{"key": "value"}')
        '{"key": "value"}'
    """
    if not text:
        return text

    cleaned = text.strip()

    # 使用正则表达式移除 markdown 代码块标记
    patterns = [
        (r'^```json\s*', ''),  # 移除开头的 ```json
        (r'^```\s*', ''),       # 移除开头的 ```
        (r'\s*```$', ''),       # 移除结尾的 ```
    ]

    for pattern, replacement in patterns:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.MULTILINE)

    return cleaned.strip()
