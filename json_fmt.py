#!/usr/bin/env python3
"""JSON格式化工具"""

import json


def json_format(text):
    """将JSON文本美化（缩进、换行）"""
    obj = json.loads(text)
    return json.dumps(obj, ensure_ascii=False, indent=2)


def json_compact(text):
    """将JSON压缩为一行字符串"""
    obj = json.loads(text)
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


if __name__ == "__main__":
    s = '{"name":"张三","scores":[98,100,null]}'
    print("美化:")
    print(json_format(s))
    print("\n压缩:")
    print(json_compact(s))
