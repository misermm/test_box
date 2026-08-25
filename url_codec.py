#!/usr/bin/env python3
"""URL编码/解码"""

import re
from urllib.parse import quote, unquote

_INVALID_PCT = re.compile(r"%(?![0-9A-Fa-f]{2})")


def url_encode(text, safe=""):
    """URL编码（百分号编码，UTF-8）"""
    return quote(text, safe=safe)


def url_decode(text):
    """URL解码，无效的百分号序列或非法UTF-8会抛出异常"""
    if _INVALID_PCT.search(text):
        raise ValueError(f"无效的URL编码序列: {_INVALID_PCT.search(text).group()}...")
    return unquote(text, errors="strict")


if __name__ == "__main__":
    s = "你好 hello 123!@#"
    e = url_encode(s)
    print(e)
    print(url_decode(e))
