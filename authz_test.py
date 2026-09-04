#!/usr/bin/env python3
"""越权测试（IDOR）模块

模型（水平越权）：
- 账号 A、B 分别登录后打开同一页面，各自 F12 复制 curl，分别点「导入(账号A)」「导入(账号B)」
- 工具自动提取双方 Token（无需手动填写）
- 测试时把 B 的 curl 的凭证替换为 A 的 Token 直接重放：
  响应与 B 自己访问的结果一致 → 水平越权；401/403/404 → 安全

垂直越权：
- 导入管理员接口 curl，用低权限账号 A 的 Token 直接调用，2xx → 确认越权

仅供自有授权测试环境使用。
"""

import difflib
import json
import queue
import re
import shlex
import threading
import time
import urllib.request
import urllib.error

import tkinter as tk
from tkinter import ttk


# ==================== curl 解析 ====================

def parse_curl(curl_text):
    """解析 curl 命令为请求 dict。

    支持: curl [url] -X METHOD -H 'K: V' -d/--data/--data-raw 'body' -b/--cookie 'c'
    返回: {method, url, headers, body}
    解析失败抛 ValueError。
    """
    text = curl_text.strip()
    text = re.sub(r"\^$\n?", "", text, flags=re.M)   # Windows ^ 续行
    text = re.sub(r"\\\n", " ", text)                 # bash \ 续行
    text = re.sub(r"`\n", " ", text)                  # PowerShell ` 续行
    text = text.replace("^", " ")
    # 修复：拼接成单行后残留的续行反斜杠会干扰 shlex 分词（\ 转义空格导致 -H 错位）
    text = re.sub(r"\\\s+", " ", text)                # 行尾 \ 后跟空白
    text = re.sub(r"(^|\s)\\(\s|$)", r"\1\2", text)   # 独立的 \
    # 修复：中文输入法/网页复制的弯引号统一转为普通引号
    for lq, rq in (("\u201c", '"'), ("\u201d", '"'),
                   ("\u2018", "'"), ("\u2019", "'")):
        text = text.replace(lq, rq).replace(rq, rq)
    if not text:
        raise ValueError("内容为空")
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()
    if not tokens or tokens[0].rstrip(":").lower() not in ("curl",):
        if re.match(r"https?://", text):
            tokens = ["curl", text]
        else:
            raise ValueError("不是有效的接口命令（应以 curl 开头或直接为 URL）")

    method, url, headers, body = "GET", None, {}, None
    i = 1
    while i < len(tokens):
        t = tokens[i]
        low = t.lower()
        if low in ("-x", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
            i += 2
        elif low in ("-h", "--header") and i + 1 < len(tokens):
            h = tokens[i + 1]
            if ":" in h:
                k, v = h.split(":", 1)
                headers[k.strip()] = v.strip()
            i += 2
        elif low in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode") and i + 1 < len(tokens):
            body = tokens[i + 1]
            if method == "GET":
                method = "POST"
            i += 2
        elif low in ("-b", "--cookie") and i + 1 < len(tokens):
            headers.setdefault("Cookie", tokens[i + 1])
            i += 2
        elif low in ("-a", "--user-agent") and i + 1 < len(tokens):
            headers.setdefault("User-Agent", tokens[i + 1])
            i += 2
        elif low == "--compressed":
            i += 1
        elif low.startswith("-"):
            if low in ("-k", "--insecure", "-s", "--silent", "-l", "--location", "-v", "--verbose",
                       "-g", "--globoff"):
                i += 1
            elif low == "-o":
                i += 2
            else:
                i += 1
        elif re.match(r"https?://", t):
            url = t
            i += 1
        else:
            i += 1
    if not url:
        # 兜底：直接从原文正则提取 URL（处理被特殊字符包裹或 shlex 失败的情况）
        m = re.search(r"https?://[^\s'\"]+", text)
        if m:
            url = m.group(0).rstrip(")").rstrip(",")
    if not url:
        raise ValueError("接口中未找到 URL")
    url = url.strip("'\"")
    if body:
        body = body.replace("'\\''", "'").strip("'\"")
    return {"method": method, "url": url, "headers": headers, "body": body}


# 资源 ID 识别（仅用于界面提示"这条接口含资源 ID，适合越权测试"，不参与测试流程）
_PATH_ID_RE = re.compile(r"/(\d{2,})(?=/|\?|$)")
_BODY_ID_KEY_RE = re.compile(r"\"(\w*[iI]d|\w*No|\w*number)\"\s*:\s*\"?(\d{2,})\"?")




def make_edge_resizable(widget, min_h=1, max_h=30, edge_px=5, line_px=17, on_resize=None):
    """让 Text 等控件可通过上下边缘拖动改变高度（行数）。"""
    state = {"mode": None, "start_y": 0, "start_h": 0, "prev_h": 0}

    def cur_lines():
        return int(widget.cget("height"))

    def on_move(e):
        h = cur_lines()
        near_top = e.y <= edge_px
        near_bottom = e.y >= widget.winfo_height() - edge_px
        if state["mode"] is None:
            if near_top or near_bottom:
                widget.config(cursor="sb_v_double_arrow")
            else:
                widget.config(cursor="")
            return
        if state["mode"] == "top":
            delta_lines = round((state["start_y"] - e.y) / 16)
        else:
            delta_lines = round((e.y - state["start_y"]) / 16)
        widget.config(height=max(min_h, min(max_h, state["start_h"] + delta_lines)))
        if on_resize:
            # 增量联动：只传本次事件相对上一次高度的像素差，避免按起点累计差值被反复累加、把下方列表挤没
            now = int(widget.cget("height"))
            on_resize((now - state["prev_h"]) * line_px)
            state["prev_h"] = now

    def on_press(e):
        if e.y <= edge_px:
            state["mode"] = "top"
        elif e.y >= widget.winfo_height() - edge_px:
            state["mode"] = "bottom"
        else:
            state["mode"] = None
        state["start_y"] = e.y
        state["start_h"] = cur_lines()
        state["prev_h"] = cur_lines()

    def on_release(e):
        state["mode"] = None

    widget.bind("<Motion>", on_move, add="+")
    widget.bind("<ButtonPress-1>", on_press, add="+")
    widget.bind("<ButtonRelease-1>", on_release, add="+")


def find_resource_ids(req):
    """识别请求中的资源 ID（提示用途），返回 [(位置, key, 值)]"""
    found = []
    for m in _PATH_ID_RE.finditer(req["url"]):
        found.append(("path", "URL路径", m.group(1)))
    if req.get("body"):
        for m in _BODY_ID_KEY_RE.finditer(req["body"]):
            found.append(("body", m.group(1), m.group(2)))
    seen, uniq = set(), []
    for f in found:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq


def extract_auth_headers(headers):
    """从请求头中提取凭证头。Token 提取只取 Authorization 头的值；
    仅当没有 Authorization 时才回退用 Cookie，不与 Authorization 混合返回。"""
    headers = headers or {}
    for k, v in headers.items():
        if k.lower() == "authorization" and v:
            return {"Authorization": v}
    for k, v in headers.items():
        if k.lower() == "cookie" and v:
            return {"Cookie": v}
    return {}


# ==================== HTTP 请求 ====================

def send_request(method, url, headers=None, body=None, timeout=15):
    """发送任意方法的 HTTP 请求，返回 {status, headers, body, elapsed}。失败抛异常。"""
    data = body.encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method.upper())
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status, resp_headers = resp.status, dict(resp.getheaders())
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
        resp_headers = dict(e.headers.items())
    elapsed = time.time() - start
    encoding = (resp_headers.get("Content-Encoding")
                or resp_headers.get("content-encoding") or "").strip().lower()
    if encoding == "gzip":
        import gzip
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    text = raw.decode("utf-8", errors="replace")
    return {"status": status, "headers": resp_headers, "body": text, "elapsed": elapsed}


def _similarity(a, b):
    if a == b:
        return 1.0
    sm = difflib.SequenceMatcher(None, a or "", b or "")
    return sm.ratio()


def _tokenize_headers(headers):
    """请求头转规范文本（用于相似度对比，忽略无关头顺序）"""
    return "\n".join("%s: %s" % (k.lower(), v) for k, v in sorted((headers or {}).items()))


# ==================== 判定 ====================

def judge_swap(b_resp, a_on_b_resp):
    """水平越权判定（换 Token 模型）。

    b_resp: 账号 B 自己访问的响应（基线，应该成功）
    a_on_b_resp: 把凭证换成 A 的后重放同一请求的响应
    返回 (状态, 说明)。状态: vuln / suspect / safe / error
    """
    if a_on_b_resp is None:
        return "error", "越权请求失败（网络错误/超时）"
    st = a_on_b_resp["status"]
    if st in (401, 403):
        return "safe", "服务端拒绝（%d）" % st
    if st == 404:
        return "safe", "资源不存在（404）"
    if 200 <= st < 300:
        if b_resp is not None:
            sim = _similarity(b_resp["body"] or "", a_on_b_resp["body"] or "")
            if sim > 0.85:
                return "vuln", "A 的 Token 访问 B 的请求成功，响应与 B 的一致（相似度 %.0f%%）" % (sim * 100)
            if (a_on_b_resp["body"] or "").strip() and sim > 0.5:
                return "suspect", "访问成功但响应与 B 的差异较大（相似度 %.0f%%），建议人工复核" % (sim * 100)
            return "suspect", "访问成功（HTTP %d）但内容需人工确认" % st
        return "suspect", "访问成功（HTTP %d），缺少 B 的基线对比" % st
    return "safe", "服务端返回 %d" % st


def judge_vertical(authz_resp):
    """垂直越权判定：低权限凭证调用管理员接口。"""
    if authz_resp is None:
        return "error", "请求失败（网络错误/超时）"
    st = authz_resp["status"]
    if 200 <= st < 300:
        return "vuln", "低权限凭证调用成功（HTTP %d），疑似垂直越权" % st
    if st in (401, 403):
        return "safe", "服务端拒绝（%d）" % st
    if st == 404:
        return "suspect", "404：接口可能存在但无权限提示，建议人工确认"
    return "safe", "服务端返回 %d" % st


# ==================== 测试引擎 ====================

class IdorRunner(threading.Thread):
    """越权批量测试线程（水平=换Token重放 / 垂直=低权限调管理员接口）

    事件通过线程安全 queue 递给 UI。
    水平 cases: [{req(B的curl原样), }]
    垂直 cases: [{req(管理员接口curl原样), }]
    """

    def __init__(self, cases, token_a_headers, event_queue, timeout=15, mode="horizontal"):
        super().__init__(daemon=True)
        self.cases = cases
        self.token_a_headers = token_a_headers or {}
        self.event_queue = event_queue
        self.timeout = timeout
        self.mode = mode  # horizontal / vertical
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def _emit(self, event, data):
        self.event_queue.put((event, data))

    def run(self):
        results = []
        self._emit("start", {"total": len(self.cases), "mode": self.mode})
        for i, case in enumerate(self.cases):
            if self._stop_flag:
                self._emit("stopped", {"results": results})
                return
            req = case["req"]
            self._emit("log", {"msg": "[%d/%d] 接口: %s %s" % (i + 1, len(self.cases), req["method"], req["url"])})
            if self.mode == "horizontal":
                self._emit("log", {"msg": "  → 基线请求：使用 账号B 的凭证 %s" % ("; ".join(extract_auth_headers(req.get("headers")).values()) or "-")})
                # 基线：B 的 curl 原样请求（B 自己访问，应成功）
                b_resp = None
                baseline_err = None
                try:
                    b_resp = send_request(req["method"], req["url"], req.get("headers"),
                                          req.get("body"), self.timeout)
                except Exception as e:
                    # 基线失败不跳过：仍然用 A 的 Token 重放，判定说明里注明基线失败
                    baseline_err = str(e)
                self._emit("log", {"msg": "  → 越权重放：使用 账号A 的凭证 %s" % ("; ".join(self.token_a_headers.values()) or "-")})
                # 越权：同一请求，凭证换成 A 的 Token 重放
                test_req = {"method": req["method"], "url": req["url"],
                            "headers": dict(req.get("headers") or {}), "body": req.get("body")}
                for _hk in list(test_req["headers"].keys()):
                    if _hk.lower() in ("authorization", "cookie"):
                        del test_req["headers"][_hk]
                test_req["headers"].update(self.token_a_headers)
                try:
                    authz = send_request(test_req["method"], test_req["url"],
                                         test_req.get("headers"), test_req.get("body"), self.timeout)
                    st, reason = judge_swap(b_resp, authz)
                except Exception as e:
                    authz, st, reason = None, "error", "越权请求失败: %s" % e
                if baseline_err:
                    reason = "B 基线请求失败(%s)，仅 A Token 重放结果: %s" % (baseline_err, reason)
                results.append({**case, "status": st, "reason": reason,
                                "baseline": b_resp, "baseline_err": baseline_err, "authz": authz,
                                "token": "; ".join(self.token_a_headers.values()) or "-",
                                "test_url": test_req["url"]})
            else:  # vertical
                self._emit("log", {"msg": "  → 垂直越权：使用 账号A 的凭证 %s 调用管理员接口" % ("; ".join(self.token_a_headers.values()) or "-")})
                v_req = {"method": req["method"], "url": req["url"],
                         "headers": dict(req.get("headers") or {}), "body": req.get("body")}
                v_req["headers"].update(self.token_a_headers)
                try:
                    authz = send_request(v_req["method"], v_req["url"],
                                         v_req.get("headers"), v_req.get("body"), self.timeout)
                    st, reason = judge_vertical(authz)
                except Exception as e:
                    authz, st, reason = None, "error", "请求失败: %s" % e
                results.append({**case, "status": st, "reason": reason,
                                "baseline": None, "authz": authz,
                                "token": "; ".join(self.token_a_headers.values()) or "-",
                                "test_url": v_req["url"]})
            self._emit("progress", {"index": i + 1, "result": results[-1]})
        self._emit("done", {"results": results})


# ==================== 界面 ====================

STATUS_TEXT = {"vuln": "🔴 确认漏洞", "suspect": "🟡 可疑", "safe": "🟢 安全", "error": "⛔ 错误"}


def build_page(app):
    """在 app.content 上构建越权测试页面；app 为 ToolboxApp 实例"""
    c = app.content
    app._label(c, "检测接口越权（仅供授权测试环境使用）。水平越权：A、B 各复制同一页面接口导入，"
              "工具用 A 的 Token 重放 B 的请求，成功访问 B 的数据即为越权；垂直越权：用低权限 A 的 Token 调管理员接口。").pack(anchor="w", pady=(0, 8))

    # ---- 账号区 ----
    # 顶层垂直 PanedWindow：账号凭证区（含接口导入输入框）可上下拖动调整高度
    app._authz_vpaned = ttk.Panedwindow(c, orient="vertical")
    app._authz_vpaned.pack(fill="both", expand=True)
    acct = tk.LabelFrame(app._authz_vpaned, text="账号凭证（导入接口后自动提取，可手动覆盖）", bg="#f5f6fa",
                         font=("Microsoft YaHei UI", 10, "bold"))
    app._authz_vpaned.add(acct, weight=2)
    app._authz_acct_a_var = tk.StringVar()
    app._authz_acct_b_var = tk.StringVar()
    r1 = app._row(acct)
    app._label(r1, "账号A Token(自动提取):").pack(side="left")
    tk.Entry(r1, textvariable=app._authz_acct_a_var).pack(
        side="left", padx=4, fill="x", expand=True)
    tk.Button(r1, text="导入(账号A)", command=lambda: _import_curls(app, "A"),
              bg="#3498db", fg="white", font=("Microsoft YaHei UI", 10, "bold"),
              width=12).pack(side="left", padx=(2, 0))
    r2 = app._row(acct)
    app._label(r2, "账号B Token(自动提取):").pack(side="left")
    tk.Entry(r2, textvariable=app._authz_acct_b_var).pack(
        side="left", padx=4, fill="x", expand=True)
    tk.Button(r2, text="导入(账号B)", command=lambda: _import_curls(app, "B"),
              bg="#9b59b6", fg="white", font=("Microsoft YaHei UI", 10, "bold"),
              width=12).pack(side="left", padx=(2, 0))
    # curl 粘贴框（A/B 共用，点对应行的导入按钮生效）
    app._authz_curl_text = tk.Text(acct, height=3, font=("Consolas", 10), wrap="word", bg="white")
    app._authz_curl_text.pack(fill="x", padx=4, pady=(4, 2))
    def _sync_lists(delta_px):
        # 输入框高度变化时联动：把分隔条跟随账号区所需高度移动，
        # 增大输入框→下方列表等量缩小，反之亦然；总高度不变。
        # 下限取账号区请求高度（含「清空接口」按钮行），保证按钮始终有空间不被挤没。
        try:
            def _apply():
                try:
                    need = acct.winfo_reqheight()  # 账号区完整所需高度（含按钮行）
                    total = app._authz_vpaned.winfo_height()
                    target = max(need, min(total - 80, need + 0))
                    if total <= 0:
                        target = need
                    app._authz_vpaned.sashpos(0, target)
                except Exception:
                    pass
            app.content.after_idle(_apply)
        except Exception:
            pass
    make_edge_resizable(app._authz_curl_text, on_resize=_sync_lists)  # 上下边缘拖动调整输入框高度，下边缘联动下方列表
    r3 = app._row(acct)
    tk.Button(r3, text="清空接口", command=lambda: _clear_cases(app), width=10).pack(side="left", padx=4)
    app._label(r3, "用法：A、B 各登录后打开同一页面，各自 F12 复制接口粘贴到上面，再点对应账号行的导入按钮").pack(side="left", padx=(8, 0))
    app._authz_case_count = app._label(r3, "A接口: 0 ｜ B用例: 0")
    app._authz_case_count.pack(side="right", padx=8)

    # ---- 用例列表（水平=B 的 curl；垂直=导过的 A 接口） ----
    app._authz_hpaned = ttk.Panedwindow(app._authz_vpaned, orient="horizontal")
    app._authz_vpaned.add(app._authz_hpaned, weight=3)
    lst = tk.LabelFrame(app._authz_hpaned, text="越权用例（来源：账号B的接口；点击选择，Ctrl/Shift 多选；不选则测全部）",
                        bg="#f5f6fa", font=("Microsoft YaHei UI", 10, "bold"))
    app._authz_hpaned.add(lst, weight=3)
    # 固定行高，避免行内文字上下被遮挡只显示一半
    _st = ttk.Style()
    _st.configure("Authz.Treeview", rowheight=28)
    cols = ("method", "url", "has_id")
    app._authz_tree = ttk.Treeview(lst, columns=cols, show="headings", height=8, selectmode="extended", style="Authz.Treeview")
    for cid, txt, w, stretch in (("method", "方法", 70, False), ("url", "URL", 560, True), ("has_id", "含资源ID", 160, True)):
        app._authz_tree.heading(cid, text=txt)
        app._authz_tree.column(cid, width=w, anchor="w", stretch=stretch, minwidth=50)
    app._authz_tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
    vsb = ttk.Scrollbar(lst, orient="vertical", command=app._authz_tree.yview)
    hsb = ttk.Scrollbar(lst, orient="horizontal", command=app._authz_tree.xview)
    vsb.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=4)
    hsb.grid(row=1, column=0, sticky="ew", padx=(4, 0))
    app._authz_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    lst.rowconfigure(0, weight=1)
    lst.columnconfigure(0, weight=1)
    app._authz_cases = []       # B 的 curl 生成的水平越权用例
    app._authz_a_cases = []     # A 导入的接口（垂直越权模式使用）
    app._authz_results = []
    app._authz_event_queue = queue.Queue()
    app._authz_runner = None

    # ---- 执行区 ----
    run = tk.LabelFrame(c, text="执行", bg="#f5f6fa",
                        font=("Microsoft YaHei UI", 10, "bold"))
    run.pack(fill="x", pady=(0, 6))
    rr = app._row(run)
    app._label(rr, "测试类型:").pack(side="left")
    app._authz_type_var = tk.StringVar(value="水平越权（换Token重放）")
    app._authz_type_combo = ttk.Combobox(rr, textvariable=app._authz_type_var, state="readonly", width=22,
                 values=["水平越权（换Token重放）", "垂直越权（管理员接口）"])
    app._authz_type_combo.pack(side="left", padx=(4, 10))
    app._authz_type_combo.bind("<<ComboboxSelected>>", lambda e: _refresh_case_tree(app))
    app._label(rr, "超时(秒):").pack(side="left")
    app._authz_timeout_var = tk.StringVar(value="15")
    tk.Entry(rr, textvariable=app._authz_timeout_var, width=5).pack(side="left", padx=(4, 10))
    tk.Button(rr, text="开始测试", command=lambda: _start_test(app),
              bg="#e67e22", fg="white", font=("Microsoft YaHei UI", 11, "bold"),
              width=12).pack(side="left", padx=(0, 8))
    tk.Button(rr, text="停止", command=lambda: _stop_test(app), width=8).pack(side="left", padx=(0, 8))
    tk.Button(rr, text="清空结果", command=lambda: _clear_results(app), width=8).pack(side="left")

    app._authz_progress = app._label(run, "")
    app._authz_progress.pack(anchor="w", padx=4)


    # ---- 结果区 ----
    res = tk.LabelFrame(app._authz_hpaned, text="测试结果", bg="#f5f6fa",
                        font=("Microsoft YaHei UI", 10, "bold"))
    app._authz_hpaned.add(res, weight=2)
    rcols = ("status", "url", "token", "baseline", "reason")
    app._authz_res_tree = ttk.Treeview(res, columns=rcols, show="headings", height=6, style="Authz.Treeview")
    for cid, txt, w, stretch in (("status", "状态", 110, False), ("url", "接口", 480, True), ("token", "Token", 180, True), ("baseline", "B基线结果", 110, False), ("reason", "判定说明", 300, True)):
        app._authz_res_tree.heading(cid, text=txt)
        app._authz_res_tree.column(cid, width=w, anchor="w", stretch=stretch, minwidth=50)
    app._authz_res_tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
    rsb = ttk.Scrollbar(res, orient="vertical", command=app._authz_res_tree.yview)
    rhsb = ttk.Scrollbar(res, orient="horizontal", command=app._authz_res_tree.xview)
    rsb.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=4)
    rhsb.grid(row=1, column=0, sticky="ew", padx=(4, 0))
    app._authz_res_tree.configure(yscrollcommand=rsb.set, xscrollcommand=rhsb.set)
    res.rowconfigure(0, weight=1)
    res.columnconfigure(0, weight=1)
    app._authz_res_tree.bind("<Double-1>", lambda e: _show_detail(app))
    db = tk.Frame(res, bg="#f5f6fa")
    db.grid(row=0, column=2, rowspan=2, sticky="ns", padx=4)
    tk.Button(db, text="查看详情", command=lambda: _show_detail(app), width=10).pack(pady=2)
    tk.Button(db, text="导出报告", command=lambda: _export_report(app), width=10).pack(pady=2)


# ---------- 交互处理 ----------

def _get_headers_from_token(token):
    """手动粘贴 Token 时推断请求头：Bearer token / Cookie / 原始 Header"""
    t = token.strip()
    if not t:
        return {}
    if t.lower().startswith("bearer "):
        return {"Authorization": t}
    if "=" in t and ";" in t or t.lower().startswith(("cookie:", "session")):
        return {"Cookie": t.replace("Cookie:", "", 1).strip()}
    if re.match(r"^[\w-]+:\s*", t):
        k, v = t.split(":", 1)
        return {k.strip(): v.strip()}
    return {"Authorization": "Bearer " + t}


def _import_curls(app, which="A"):
    """导入 curl。

    账号A：提取 Token 作为发起凭证，curl 登记为接口（垂直越权模式用）；
    账号B：提取 Token 作为基线身份，curl 直接登记为水平越权用例（换成 A 的 Token 重放）。
    """
    text = app._authz_curl_text.get("1.0", "end-1c")
    ok, fail = 0, []
    tokens = set()
    parsed = []
    # 智能分块：一条 curl 可能占多行（续行以 -H/--data/` 等开头）。
    # 只有以 curl 开头的行才开启新命令，其余行并入当前命令块。
    blocks = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^curl(\s|$|:)", line, re.I) or not blocks:
            blocks.append(line)
        elif re.match(r"^https?://\S+$", line):
            blocks.append(line)  # 纯 URL 单独成块
        else:
            blocks[-1] += " " + line  # 续行并入上一条
    for line in blocks:
        try:
            parsed.append(parse_curl(line))
            ok += 1
        except ValueError as e:
            fail.append(str(e))
    if not parsed:
        app._notify("没有可导入的接口（%s）" % (fail[0] if fail else "内容为空"))
        return
    for req in parsed:
        tokens.update(extract_auth_headers(req.get("headers")).values())
        if which == "B":
            # B 的 curl 即越权用例：同一请求换成 A 的 Token 重放
            app._authz_cases.append({"req": req, "ids": find_resource_ids(req)})
            ids = find_resource_ids(req)
            mark = "✔" if ids else "-"
            app._authz_tree.insert("", "end", values=(req["method"], req["url"], mark))
        else:
            app._authz_a_cases.append(req)
    # Token 自动提取（已有值不覆盖，可手动改）
    var = app._authz_acct_a_var if which == "A" else app._authz_acct_b_var
    if tokens:
        var.set(sorted(tokens)[0])  # 每次导入都更新为最新提取的 Token
    _refresh_case_tree(app)  # 按当前模式刷新用例列表显示
    if which == "B":
        app._authz_case_count.config(
            text="A接口: %d ｜ B用例: %d" % (len(app._authz_a_cases), len(app._authz_cases)))
        msg = "账号B导入 %d 条越权用例" % ok
        if tokens:
            msg += "，Token 已自动提取"
        app._notify(msg)
    else:
        app._authz_case_count.config(
            text="A接口: %d ｜ B用例: %d" % (len(app._authz_a_cases), len(app._authz_cases)))
        msg = "账号A导入 %d 条接口（垂直越权模式使用）" % ok
        if tokens:
            msg += "，Token 已自动提取"
        if fail:
            msg += "；%d 条失败: %s" % (len(fail), fail[0])
        app._notify(msg)


def _refresh_case_tree(app):
    """按当前模式刷新用例列表：水平→B 的用例；垂直→A 登记的接口。"""
    tree = app._authz_tree
    tree.delete(*tree.get_children())
    vertical = app._authz_type_var.get().startswith("垂直越权")
    if vertical:
        for req in app._authz_a_cases:
            ids = find_resource_ids(req)
            mark = "✔" if ids else "-"
            tree.insert("", "end", values=(req["method"], req["url"], mark))
    else:
        for c in app._authz_cases:
            req = c["req"]
            ids = c.get("ids") or find_resource_ids(req)
            mark = "✔" if ids else "-"
            tree.insert("", "end", values=(req["method"], req["url"], mark))


def _clear_cases(app):
    app._authz_cases.clear()
    app._authz_a_cases.clear()
    for item in app._authz_tree.get_children():
        app._authz_tree.delete(item)
    app._authz_case_count.config(text="A接口: 0 ｜ B用例: 0")


def _clear_results(app):
    app._authz_results.clear()
    for item in app._authz_res_tree.get_children():
        app._authz_res_tree.delete(item)
    app._authz_progress.config(text="")


def _selected_cases(app):
    vertical = app._authz_type_var.get().startswith("垂直越权")
    sel = app._authz_tree.selection()
    if sel:
        idxs = [app._authz_tree.index(s) for s in sel]
        if vertical:
            return [{"req": app._authz_a_cases[i]} for i in idxs if i < len(app._authz_a_cases)]
        return [app._authz_cases[i] for i in idxs if i < len(app._authz_cases)]
    if vertical:
        return [{"req": r} for r in app._authz_a_cases]
    return list(app._authz_cases)


def _start_test(app):
    runner = getattr(app, "_authz_runner", None)
    if runner and runner.is_alive():
        app._notify("测试正在进行中")
        return
    token_a = app._authz_acct_a_var.get().strip()
    if not token_a:
        app._notify("请先「导入(账号A)」接口自动提取 Token，或手动粘贴 A 的 Token")
        return
    token_a_headers = _get_headers_from_token(token_a)
    # 校验：A 的 Token 不能与账号B输入框中的 Token 相同（否则越权重放无意义）
    token_b_val = app._authz_acct_b_var.get().strip()
    if token_b_val and token_a == token_b_val:
        app._notify("[警告] 账号A与账号B的 Token 相同！请确认 A 框里填的是账号A自己的凭证")
        return
    vertical = app._authz_type_var.get().startswith("垂直越权")

    if vertical:
        cases = [{"req": req} for req in app._authz_a_cases]
        if not cases:
            app._notify("垂直越权模式请先「导入(账号A)」管理员接口")
            return
    else:
        cases = _selected_cases(app)
        if not cases:
            app._notify("请先「导入(账号B)」接口生成越权用例")
            return
        # 校验：B 的用例应包含凭证（没有凭证的请求无法体现身份差异）
        no_auth = [c for c in cases if not extract_auth_headers(c["req"].get("headers"))]
        if len(no_auth) == len(cases):
            app._notify("B 的接口中未发现 Token/Cookie，请确认复制的是登录后的请求")
            return

    try:
        timeout = float(app._authz_timeout_var.get())
    except ValueError:
        timeout = 15.0
    _clear_results(app)
    q = app._authz_event_queue
    while not q.empty():
        q.get_nowait()
    app._authz_runner = IdorRunner(cases, token_a_headers, q,
                                   timeout=timeout,
                                   mode="vertical" if vertical else "horizontal")
    app._authz_runner.start()
    app.after(100, lambda: _poll_events(app))


def _poll_events(app):
    """UI 主线程轮询消费测试事件"""
    q = app._authz_event_queue
    try:
        while True:
            event, data = q.get_nowait()
            _on_event(app, event, data)
            if event in ("done", "stopped"):
                return
    except queue.Empty:
        pass
    runner = getattr(app, "_authz_runner", None)
    if runner and runner.is_alive():
        app.after(100, lambda: _poll_events(app))


def _stop_test(app):
    runner = getattr(app, "_authz_runner", None)
    if runner and runner.is_alive():
        runner.stop()
        app._notify("正在停止…")
    else:
        app._notify("没有正在运行的测试")


def _log(app, msg):
    """详细日志统一写入主程序底部「运行日志」区（无[提示]前缀，带时间戳）。"""
    app._notify_raw(msg)


def _on_event(app, event, data):
    if event == "log":
        app._notify(data["msg"])
    elif event == "start":
        mode = "垂直越权" if data.get("mode") == "vertical" else "水平越权"
        app._authz_progress.config(text="开始%s测试，共 %d 条用例…" % (mode, data["total"]))
    elif event == "progress":
        r = data["result"]
        app._authz_results.append(r)
        b = r.get("baseline")
        b_txt = ("HTTP %s" % b["status"]) if b and b.get("status") else ("失败" if r.get("baseline_err") or (r.get("baseline") is None and r.get("authz")) else "-")
        app._authz_res_tree.insert("", "end", values=(
            STATUS_TEXT.get(r["status"], r["status"]),
            r["req"]["url"], r.get("token", "-"), b_txt, r["reason"]))
        _log(app, "[%s] %s %s | Token: %s | %s" % (
            STATUS_TEXT.get(r["status"], r["status"]), r["req"]["method"], r["req"]["url"],
            r.get("token", "-"), r["reason"]))
        app._authz_progress.config(text="进度: %d 条" % len(app._authz_results))
    elif event in ("done", "stopped"):
        results = data["results"]
        n_v = sum(1 for r in results if r["status"] == "vuln")
        n_s = sum(1 for r in results if r["status"] == "suspect")
        n_g = sum(1 for r in results if r["status"] == "safe")
        n_e = sum(1 for r in results if r["status"] == "error")
        app._authz_progress.config(
            text="完成: 确认漏洞 %d ｜ 可疑 %d ｜ 安全 %d ｜ 错误 %d" % (n_v, n_s, n_g, n_e))
        app._notify("越权测试完成：确认漏洞 %d，可疑 %d" % (n_v, n_s))


def _show_detail(app):
    sel = app._authz_res_tree.selection()
    if not sel:
        app._notify("请先选择一条结果")
        return
    idx = app._authz_res_tree.index(sel[0])
    if idx >= len(app._authz_results):
        return
    r = app._authz_results[idx]

    win = tk.Toplevel(app)
    win.title("越权测试详情")
    win.geometry("900x600")
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True)

    def _tab(title, content):
        f = tk.Frame(nb)
        nb.add(f, text=title)
        t = tk.Text(f, wrap="none", font=("Consolas", 10), bg="white")
        t.pack(fill="both", expand=True)
        t.insert("1.0", content if content else "（无）")

    base = r.get("baseline")
    authz = r.get("authz")
    base_title = "B自己访问的响应(基线)" if r.get("baseline") else "响应(基线)"
    _tab(base_title, _fmt_resp(base))
    _tab("A的Token重放后的响应", _fmt_resp(authz))
    if base and authz:
        diff = "\n".join(difflib.unified_diff(
            (base["body"] or "").splitlines(), (authz["body"] or "").splitlines(),
            "B-baseline", "A-replay", lineterm=""))
        _tab("响应 Diff", diff if diff else "（响应完全一致 → 确认越权）")
    info = ("接口: %s %s\n判定: %s\n说明: %s\n重放URL: %s" % (
        r["req"]["method"], r["req"]["url"], STATUS_TEXT.get(r["status"]), r["reason"],
        r.get("test_url", "-")))
    _tab("信息", info)


def _fmt_resp(resp):
    if not resp:
        return "（无响应）"
    return "HTTP %s\n\n%s" % (resp["status"], resp["body"][:20000])


def _export_report(app):
    import datetime
    from tkinter import filedialog
    if not app._authz_results:
        app._notify("没有测试结果可导出")
        return
    path = filedialog.asksaveasfilename(
        defaultextension=".md", initialfile="越权测试报告.md",
        filetypes=[("Markdown", "*.md"), ("文本文件", "*.txt")])
    if not path:
        return
    lines = ["# 越权测试报告", "",
             "生成时间: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""]
    def _fmt_req(req, title):
        ls = ["### %s" % title]
        ls.append("```")
        ls.append("%s %s" % (req["method"], req["url"]))
        for k, v in (req.get("headers") or {}).items():
            ls.append("%s: %s" % (k, v))
        ls.append("")
        if req.get("body"):
            ls.append(req["body"])
        ls.append("```")
        return ls

    def _fmt_resp_full(resp):
        if not resp:
            return ["```", "（无响应）", "```"]
        ls = ["```", "HTTP %s" % resp["status"]]
        for k, v in (resp.get("headers") or {}).items():
            ls.append("%s: %s" % (k, v))
        ls.append("")
        ls.append((resp["body"] or "")[:20000])
        ls.append("```")
        return ls

    for r in app._authz_results:
        req = r["req"]
        lines.append("## %s %s" % (req["method"], req["url"]))
        lines.append("- 状态: %s" % STATUS_TEXT.get(r["status"], r["status"]))
        lines.append("- 判定: %s" % r["reason"])
        lines.append("- 使用的Token: %s" % r.get("token", "-"))
        if r.get("test_url"):
            lines.append("- 重放URL: %s" % r["test_url"])
        lines.append("")
        lines.extend(_fmt_req(req, "原始请求（接口导入的 curl）"))
        if r.get("test_url"):
            replay = dict(req)
            replay["url"] = r["test_url"]
            lines.extend(_fmt_req(replay, "重放请求（凭证已替换为 A 的 Token）"))
        lines.append("### B 基线响应")
        lines.extend(_fmt_resp_full(r.get("baseline")))
        lines.append("")
        lines.append("### A Token 重放响应")
        lines.extend(_fmt_resp_full(r.get("authz")))
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    app._notify("报告已导出: " + path)
