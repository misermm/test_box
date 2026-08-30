#!/usr/bin/env python3
"""HTTP GET/POST 接口请求工具"""

import json
import time
import urllib.request
import urllib.error


def parse_headers(text):
    """将 'Key: Value' 每行一个 的文本解析为dict，空文本返回None"""
    headers = {}
    for lineno, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"请求头第 {lineno} 行格式错误（应为 Key: Value）: {line}")
        k, v = line.split(":", 1)
        headers[k.strip()] = v.strip()
    return headers or None


def send_request(method, url, headers=None, body=None, timeout=15):
    """
    发送HTTP请求

    参数:
        method: GET / POST
        url: 请求地址
        headers: 请求头dict（可为None）
        body: 请求体文本（可为None）
        timeout: 超时秒数
    返回:
        dict: status / headers / body / elapsed
    网络错误或URL无效时抛出异常
    """
    method = method.upper()
    if method not in ("GET", "POST"):
        raise ValueError(f"不支持的方法: {method}")
    data = body.encode("utf-8") if body else None

    req = urllib.request.Request(url, data=data, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if data and not (headers and any(k.lower() == "content-type" for k in headers)):
        # BUG-05: body 是合法 JSON 时默认用 application/json，避免被服务端误解
        default_ct = "application/x-www-form-urlencoded"
        if body and body.lstrip()[:1] in ("{", "["):
            try:
                json.loads(body)
                default_ct = "application/json"
            except ValueError:
                pass
        req.add_header("Content-Type", default_ct)

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
            resp_headers = dict(resp.getheaders())
    except urllib.error.HTTPError as e:
        # 4xx/5xx 也算有效响应，展示给用户
        raw = e.read()
        status = e.code
        resp_headers = dict(e.headers.items())
    except urllib.error.URLError as e:
        # BUG-06: 超时给出友好提示，与一般网络错误区分
        reason = getattr(e, "reason", e)
        if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower() or "timeout" in str(reason).lower():
            raise ValueError(f"请求超时（{timeout} 秒无响应），可在界面\"超时(秒)\"中调大后重试") from e
        raise
    elapsed = time.time() - start

    charset = None
    ctype = resp_headers.get("Content-Type") or resp_headers.get("content-type") or ""
    if "charset=" in ctype:
        charset = ctype.split("charset=")[-1].split(";")[0].strip().strip('"')
    try:
        text = raw.decode(charset or "utf-8", errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")

    print(f"响应状态: {status}，耗时 {elapsed:.2f}s，{len(raw)} 字节")
    return {
        "status": status,
        "headers": resp_headers,
        "body": text,
        "elapsed": elapsed,
    }


def format_response(resp):
    """将响应dict格式化为可展示文本"""
    lines = [f"HTTP Status: {resp['status']}",
             f"耗时: {resp['elapsed']:.2f}s",
             ""]
    for k, v in resp["headers"].items():
        lines.append(f"{k}: {v}")
    lines.append("")
    body = resp["body"]
    ctype = resp["headers"].get("Content-Type") or resp["headers"].get("content-type") or ""
    stripped = body.lstrip()
    if "json" in ctype.lower() or stripped[:1] in ("{", "["):
        try:
            body = json.dumps(json.loads(body), ensure_ascii=False, indent=2)
        except (ValueError, RecursionError):
            pass
    lines.append(body)
    return "\n".join(lines)


if __name__ == "__main__":
    r = send_request("GET", "https://httpbin.org/get")
    print(format_response(r))
