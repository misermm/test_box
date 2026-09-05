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

    def __init__(self, cases, token_a_headers, event_queue, timeout=15, mode="horizontal", admin_headers=None, stored_baseline=None):
        super().__init__(daemon=True)
        self.cases = cases
        self.token_a_headers = token_a_headers or {}
        self.admin_headers = admin_headers or {}
        self.stored_baseline = stored_baseline or {}
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
                # 基线对照：只复用「开始基线测试」已保存的响应，越权测试不重发基线请求
                b_resp = None
                baseline_err = None
                if req["url"] in self.stored_baseline:
                    b_resp = self.stored_baseline[req["url"]]
                    self._emit("log", {"msg": "  → 基线对照：复用基线测试结果"})
                else:
                    baseline_err = "未运行基线测试（无基线对照，仅 A Token 重放判定）"
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
                    reason = "%s｜仅 A Token 重放结果: %s" % (baseline_err, reason)
                results.append({**case, "status": st, "reason": reason,
                                "baseline": b_resp, "baseline_err": baseline_err, "authz": authz,
                                "token": "; ".join(self.token_a_headers.values()) or "-",
                                "test_url": test_req["url"], "mode": self.mode})
            else:  # vertical
                v_baseline = None
                v_baseline_err = None
                if req["url"] in self.stored_baseline:
                    v_baseline = self.stored_baseline[req["url"]]
                    self._emit("log", {"msg": "  → 基线对照：复用基线测试结果"})
                else:
                    v_baseline_err = "未运行基线测试（无基线对照，仅普通账号重放判定）"
                self._emit("log", {"msg": "  → 垂直越权：使用 普通账号 的凭证 %s 调用管理员接口" % ("; ".join(self.token_a_headers.values()) or "-")})
                v_req = {"method": req["method"], "url": req["url"],
                         "headers": dict(req.get("headers") or {}), "body": req.get("body")}
                for _hk in list(v_req["headers"].keys()):
                    if _hk.lower() in ("authorization", "cookie"):
                        del v_req["headers"][_hk]
                v_req["headers"].update(self.token_a_headers)
                try:
                    authz = send_request(v_req["method"], v_req["url"],
                                         v_req.get("headers"), v_req.get("body"), self.timeout)
                    st, reason = judge_vertical(authz)
                except Exception as e:
                    authz, st, reason = None, "error", "请求失败: %s" % e
                if v_baseline_err:
                    reason = "%s｜仅普通账号重放结果: %s" % (v_baseline_err, reason)
                results.append({**case, "status": st, "reason": reason,
                                "baseline": v_baseline, "baseline_err": v_baseline_err, "authz": authz,
                                "token": "; ".join(self.token_a_headers.values()) or "-",
                                "test_url": v_req["url"], "mode": self.mode})
            self._emit("progress", {"index": i + 1, "result": results[-1]})
        self._emit("done", {"results": results})


# ==================== 界面 ====================

STATUS_TEXT = {"vuln": "🔴 确认漏洞", "suspect": "🟡 可疑", "safe": "🟢 安全", "error": "⛔ 错误"}


def build_page(app):
    """在 app.content 上构建越权测试页面；app 为 ToolboxApp 实例"""
    c = app.content
    app._label(c, "检测接口越权（仅供授权测试环境使用）。水平越权：A、B 各复制同一页面接口导入，"
              "工具用 A 的 Token 重放 B 的请求，成功访问 B 的数据即为越权；垂直越权：用低权限 A 的 Token 调管理员接口。").pack(anchor="w", pady=(0, 8))

    # ---- 测试类型选择（最顶部，先选类型再测试） ----
    typ = tk.LabelFrame(c, text="测试类型（请先选择）", bg="#f5f6fa",
                        font=("Microsoft YaHei UI", 10, "bold"))
    typ.pack(fill="x", pady=(0, 6))
    tr = app._row(typ)
    app._authz_type_var = tk.StringVar(value="水平越权（换Token重放）")
    app._authz_type_combo = ttk.Combobox(tr, textvariable=app._authz_type_var, state="readonly", width=22,
                 values=["水平越权（换Token重放）", "垂直越权（管理员接口）"])
    app._authz_type_combo.pack(side="left", padx=(4, 10))
    app._authz_type_combo.bind("<<ComboboxSelected>>", lambda e: _switch_mode_ui(app))

    # ---- 账号区 ----
    # 顶层垂直 PanedWindow：账号凭证区（含接口导入输入框）可上下拖动调整高度
    app._authz_vpaned = ttk.Panedwindow(c, orient="vertical")
    app._authz_vpaned.pack(fill="both", expand=True)
    acct = tk.LabelFrame(app._authz_vpaned, text="账号凭证（导入接口后自动提取，可手动覆盖）", bg="#f5f6fa",
                         font=("Microsoft YaHei UI", 10, "bold"))
    app._authz_vpaned.add(acct, weight=2)
    app._authz_acct_a_var = tk.StringVar()
    app._authz_acct_b_var = tk.StringVar()
    # 账号凭证按测试类型独立保存：切换类型时换存，互不覆盖
    app._authz_cred_store = {"horizontal": {"a": "", "b": "", "curl": ""},
                             "vertical": {"a": "", "b": "", "curl": ""}}
    app._authz_cred_cur = "horizontal"
    r1 = app._row(acct)
    app._authz_lbl_a = app._label(r1, "账号A Token(自动提取):")
    app._authz_lbl_a.pack(side="left")
    tk.Entry(r1, textvariable=app._authz_acct_a_var).pack(
        side="left", padx=4, fill="x", expand=True)
    app._authz_btn_a = tk.Button(r1, text="导入(账号A)", command=lambda: _import_curls(app, "A"),
              bg="#3498db", fg="white", font=("Microsoft YaHei UI", 10, "bold"),
              width=12)
    app._authz_btn_a.pack(side="left", padx=(2, 0))
    r2 = app._row(acct)
    app._authz_lbl_b = app._label(r2, "账号B Token(自动提取):")
    app._authz_lbl_b.pack(side="left")
    tk.Entry(r2, textvariable=app._authz_acct_b_var).pack(
        side="left", padx=4, fill="x", expand=True)
    app._authz_btn_b = tk.Button(r2, text="导入(账号B)", command=lambda: _import_curls(app, "B"),
              bg="#9b59b6", fg="white", font=("Microsoft YaHei UI", 10, "bold"),
              width=12)
    app._authz_btn_b.pack(side="left", padx=(2, 0))
    # curl 粘贴框（A/B 共用，点对应行的导入按钮生效）
    app._authz_curl_text = tk.Text(acct, height=3, font=("Consolas", 10), wrap="word", bg="white")
    app._authz_curl_text.pack(fill="x", padx=4, pady=(4, 2))
    def _sync_lists(delta_px):
        # 输入框高度变化时联动：把分隔条跟随账号区所需高度移动，
        # 增大输入框→下方列表等量缩小，反之亦然；总高度不变。
        # 下限取账号区请求高度（含「清空接口」等按钮行），保证按钮始终有空间不被挤没。
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
    tk.Button(r3, text="清空用例", command=lambda: _clear_cases(app), width=10).pack(side="left", padx=4)
    tk.Button(r3, text="清空接口", command=lambda: _clear_interfaces(app), width=10).pack(side="left", padx=4)
    app._label(r3, "用法：A、B 各登录后打开同一页面，各自 F12 复制接口粘贴到上面，再点对应账号行的导入按钮").pack(side="left", padx=(8, 0))
    app._authz_case_count = app._label(r3, "A接口: 0 ｜ B用例: 0")
    app._authz_case_count.pack(side="right", padx=8)

    # ---- 用例列表（水平=B 的 curl；垂直=导过的 A 接口） ----
    app._authz_hpaned = ttk.Panedwindow(app._authz_vpaned, orient="vertical")  # 用例/结果上下排布
    app._authz_vpaned.add(app._authz_hpaned, weight=3)
    case_paned = ttk.Panedwindow(app._authz_hpaned, orient="horizontal")
    app._authz_hpaned.add(case_paned, weight=3)
    base_lst = tk.LabelFrame(case_paned, text="基线用例",
                        bg="#f5f6fa", font=("Microsoft YaHei UI", 10, "bold"))
    case_paned.add(base_lst, weight=3)
    lst = tk.LabelFrame(case_paned, text="越权用例",
                        bg="#f5f6fa", font=("Microsoft YaHei UI", 10, "bold"))
    case_paned.add(lst, weight=3)
    # 固定行高，避免行内文字上下被遮挡只显示一半
    _st = ttk.Style()
    _st.configure("Authz.Treeview", rowheight=28)
    cols = ("account", "method", "url", "payload", "has_id")
    app._authz_base_tree = ttk.Treeview(base_lst, columns=cols, show="headings", height=8, selectmode="extended", style="Authz.Treeview")
    for cid, txt, w, stretch in (("account", "账号", 90, False), ("method", "方法", 60, False), ("url", "URL", 380, True), ("payload", "Payload", 200, True), ("has_id", "含资源ID", 100, True)):
        app._authz_base_tree.heading(cid, text=txt)
        app._authz_base_tree.column(cid, width=w, anchor="w", stretch=stretch, minwidth=50)
    app._authz_base_tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
    bvsb = ttk.Scrollbar(base_lst, orient="vertical", command=app._authz_base_tree.yview)
    bhsb = ttk.Scrollbar(base_lst, orient="horizontal", command=app._authz_base_tree.xview)
    bvsb.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=4)
    bhsb.grid(row=1, column=0, sticky="ew", padx=(4, 0))
    app._authz_base_tree.configure(yscrollcommand=bvsb.set, xscrollcommand=bhsb.set)
    app._authz_base_tree.bind("<Double-1>", lambda e: _edit_payload(app, "base"))
    base_lst.rowconfigure(0, weight=1)
    base_lst.columnconfigure(0, weight=1)
    app._authz_tree = ttk.Treeview(lst, columns=cols, show="headings", height=8, selectmode="extended", style="Authz.Treeview")
    for cid, txt, w, stretch in (("account", "账号", 90, False), ("method", "方法", 60, False), ("url", "URL", 420, True), ("payload", "Payload", 220, True), ("has_id", "含资源ID", 110, True)):
        app._authz_tree.heading(cid, text=txt)
        app._authz_tree.column(cid, width=w, anchor="w", stretch=stretch, minwidth=50)
    app._authz_tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
    vsb = ttk.Scrollbar(lst, orient="vertical", command=app._authz_tree.yview)
    hsb = ttk.Scrollbar(lst, orient="horizontal", command=app._authz_tree.xview)
    vsb.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=4)
    hsb.grid(row=1, column=0, sticky="ew", padx=(4, 0))
    app._authz_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    app._authz_tree.bind("<Double-1>", lambda e: _edit_payload(app, "case"))
    lst.rowconfigure(0, weight=1)
    lst.columnconfigure(0, weight=1)
    app._authz_cases = []       # B 的 curl 生成的水平越权用例
    app._authz_a_cases = []     # A 导入的接口（垂直越权模式使用）
    app._authz_baseline_cases = []  # 基线用例（B/管理员原样请求）
    app._authz_results = []
    app._authz_baseline_results = []  # 基线测试结果（独立存储）
    app._authz_event_queue = queue.Queue()
    app._authz_runner = None

    # ---- 执行区 ----
    run = tk.LabelFrame(c, text="执行", bg="#f5f6fa",
                        font=("Microsoft YaHei UI", 10, "bold"))
    run.pack(fill="x", pady=(0, 6))
    rr = app._row(run)
    app._label(rr, "超时(秒):").pack(side="left")
    app._authz_timeout_var = tk.StringVar(value="15")
    tk.Entry(rr, textvariable=app._authz_timeout_var, width=5).pack(side="left", padx=(4, 10))
    tk.Button(rr, text="开始基线测试", command=lambda: _start_baseline_test(app),
              bg="#16a085", fg="white", font=("Microsoft YaHei UI", 10, "bold"),
              width=13).pack(side="left", padx=(0, 8))
    tk.Button(rr, text="开始越权测试", command=lambda: _start_test(app),
              bg="#e67e22", fg="white", font=("Microsoft YaHei UI", 11, "bold"),
              width=13).pack(side="left", padx=(0, 8))
    tk.Button(rr, text="停止", command=lambda: _stop_test(app), width=8).pack(side="left", padx=(0, 8))
    tk.Button(rr, text="清空结果", command=lambda: _clear_results(app), width=8).pack(side="left")

    app._authz_progress = app._label(run, "")
    app._authz_progress.pack(anchor="w", padx=4)


    # ---- 结果区 ----
    res_paned = ttk.Panedwindow(app._authz_hpaned, orient="horizontal")
    app._authz_hpaned.add(res_paned, weight=2)
    base_res = tk.LabelFrame(res_paned, text="基线测试结果", bg="#f5f6fa",
                        font=("Microsoft YaHei UI", 10, "bold"))
    res_paned.add(base_res, weight=3)  # 与用例区 3/3 一致，分割线上下对齐
    res = tk.LabelFrame(res_paned, text="越权测试结果", bg="#f5f6fa",
                        font=("Microsoft YaHei UI", 10, "bold"))
    res_paned.add(res, weight=3)
    rcols = ("status", "url", "account", "token", "payload", "baseline", "reason")
    app._authz_base_res_tree = ttk.Treeview(base_res, columns=rcols, show="headings", height=6, style="Authz.Treeview")
    for cid, txt, w, stretch in (("status", "状态", 90, False), ("url", "接口", 300, True), ("account", "账号", 90, False), ("token", "Token", 130, True), ("payload", "Payload", 170, True), ("baseline", "基线结果", 90, False), ("reason", "判定说明", 220, True)):
        app._authz_base_res_tree.heading(cid, text=txt)
        app._authz_base_res_tree.column(cid, width=w, anchor="w", stretch=stretch, minwidth=50)
    app._authz_base_res_tree.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
    brsb = ttk.Scrollbar(base_res, orient="vertical", command=app._authz_base_res_tree.yview)
    brhsb = ttk.Scrollbar(base_res, orient="horizontal", command=app._authz_base_res_tree.xview)
    brsb.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=4)
    brhsb.grid(row=1, column=0, sticky="ew", padx=(4, 0))
    app._authz_base_res_tree.configure(yscrollcommand=brsb.set, xscrollcommand=brhsb.set)
    base_res.rowconfigure(0, weight=1)
    base_res.columnconfigure(0, weight=1)
    app._authz_res_tree = ttk.Treeview(res, columns=rcols, show="headings", height=6, style="Authz.Treeview")
    for cid, txt, w, stretch in (("status", "状态", 100, False), ("url", "接口", 360, True), ("account", "账号", 90, False), ("token", "Token", 150, True), ("payload", "Payload", 200, True), ("baseline", "基线结果", 100, False), ("reason", "判定说明", 260, True)):
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
    app._authz_res_tree.bind("<Double-1>", lambda e: _edit_payload(app, "result"))
    # 查看完整请求/响应详情改为单选后点「详情」按钮（原双击行为让位给 payload 编辑）
    db = tk.Frame(res, bg="#f5f6fa")
    db.grid(row=0, column=2, rowspan=2, sticky="ns", padx=4)
    tk.Button(db, text="查看详情", command=lambda: _show_detail(app), width=10).pack(pady=2)
    tk.Button(db, text="导出报告", command=lambda: _export_report(app), width=10).pack(pady=2)

    # 渲染后强制把用例区与结果区的分割线都设为正中间，保证上下对齐
    def _align_sashes():
        try:
            w = case_paned.winfo_width()
            if w > 10:
                case_paned.sashpos(0, w // 2)
                res_paned.sashpos(0, w // 2)
            else:
                app.after(100, _align_sashes)
        except Exception:
            pass
    app.after(200, _align_sashes)


# ---------- 交互处理 ----------

# ---------- payload 摘要 / 编辑弹窗 / 模式切换 ----------

def _payload_summary(body):
    """payload 截断摘要，用于列表列显示。"""
    b = (body or "").strip()
    if not b:
        return "-"
    return b if len(b) <= 40 else b[:40] + "…"


def _edit_payload(app, kind):
    """双击用例/结果列表弹出 payload 编辑窗口；保存写回对应用例的请求体。"""
    if kind == "base":
        tree = app._authz_base_tree
    elif kind == "case":
        tree = app._authz_tree
    else:
        tree = app._authz_res_tree
    sel = tree.selection()
    if not sel:
        app._notify("请先选择一条记录")
        return
    idx = tree.index(sel[0])
    vertical = app._authz_type_var.get().startswith("垂直越权")
    cur_m = "vertical" if vertical else "horizontal"
    if kind == "base":
        pool = _mode_baseline_cases(app)
        if idx >= len(pool):
            return
        req = pool[idx]
    elif kind == "case":
        pool = [r for r in app._authz_a_cases if r.get("_mode", cur_m) == cur_m] if vertical \
            else [c["req"] for c in app._authz_cases if c.get("mode", cur_m) == cur_m]
        if idx >= len(pool):
            return
        req = pool[idx]
    else:
        pool = _mode_results(app)
        if idx >= len(pool):
            return
        req = pool[idx].get("req")
    if not req:
        return
    win = tk.Toplevel(app)
    win.title("编辑 Payload")
    win.geometry("760x520")
    app._label(win, "接口: %s %s\n（保存后下次测试即使用新的 payload 发送）" % (req["method"], req["url"])).pack(anchor="w", padx=8, pady=(8, 2))
    # 按钮区先固定在窗口底部，文本框再填充剩余空间，避免小窗口时按钮被挤出可视区
    btns = tk.Frame(win)
    btns.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
    txt = tk.Text(win, wrap="word", font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4", insertbackground="#d4d4d4")
    txt.pack(fill="both", expand=True, padx=8, pady=4)
    txt.insert("1.0", req.get("body") or "")
    def _save():
        req["body"] = txt.get("1.0", "end-1c")
        vals = list(tree.item(sel[0], "values"))
        vals[4 if kind == "result" else 3] = _payload_summary(req["body"])
        tree.item(sel[0], values=vals)
        win.destroy()
        app._notify("Payload 已保存，下次测试生效")
    tk.Button(btns, text="保存", command=_save, width=10,
              bg="#27ae60", fg="white", font=("Microsoft YaHei UI", 10, "bold")).pack(side="right", padx=(6, 0))
    tk.Button(btns, text="取消", command=win.destroy, width=10).pack(side="right")


def _switch_mode_ui(app):
    """按测试类型切换账号区文案：水平=A/B；垂直=普通账号/管理员账号。"""
    vertical = app._authz_type_var.get().startswith("垂直越权")
    new_m = "vertical" if vertical else "horizontal"
    # 凭证区按模式独立：先保存当前模式的 Token 与 curl 内容，再载入目标模式的
    store = app._authz_cred_store
    cur = store.setdefault(app._authz_cred_cur, {"a": "", "b": "", "curl": ""})
    cur["a"] = app._authz_acct_a_var.get()
    cur["b"] = app._authz_acct_b_var.get()
    if getattr(app, "_authz_curl_text", None):
        cur["curl"] = app._authz_curl_text.get("1.0", "end-1c")
    tgt = store.setdefault(new_m, {"a": "", "b": "", "curl": ""})
    app._authz_cred_cur = new_m
    app._authz_acct_a_var.set(tgt.get("a", ""))
    app._authz_acct_b_var.set(tgt.get("b", ""))
    if getattr(app, "_authz_curl_text", None):
        app._authz_curl_text.delete("1.0", "end")
        if tgt.get("curl"):
            app._authz_curl_text.insert("1.0", tgt["curl"])
    if vertical:
        app._authz_lbl_a.config(text="普通账号:")
        app._authz_btn_a.config(text="导入(普通账号)")
        app._authz_lbl_b.config(text="管理员账号:")
        app._authz_btn_b.config(text="导入(管理员账号)")
    else:
        app._authz_lbl_a.config(text="账号A Token(自动提取):")
        app._authz_btn_a.config(text="导入(账号A)")
        app._authz_lbl_b.config(text="账号B Token(自动提取):")
        app._authz_btn_b.config(text="导入(账号B)")
    # 切换测试类型：保留两种模式的用例与结果，仅按当前模式过滤显示
    _refresh_case_tree(app)
    _refresh_result_trees(app)
    app._notify("已切换测试类型，两种模式的用例与测试数据独立保留")


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

    水平模式：账号A 提取 Token 作为重放凭证；账号B 的 curl 登记为越权用例（换成 A 的 Token 重放）。
    垂直模式：账号A=普通账号，只提取 Token；账号B=管理员，curl（URL/body）登记为待测管理员接口，
              其 Token 顺带提取（可作为基线凭证）。
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
            # B 的 curl 即越权用例：同一请求换成 A 的 Token 重放（水平）
            # 垂直模式下 B=管理员：curl 登记为待测管理员接口（URL/body 来源）
            vertical_now = app._authz_type_var.get().startswith("垂直越权")
            if vertical_now:
                req["_mode"] = "vertical"
                app._authz_a_cases.append(req)
            else:
                app._authz_cases.append({"req": req, "ids": find_resource_ids(req), "mode": "horizontal"})
            ids = find_resource_ids(req)
            mark = "✔" if ids else "-"
            acct = "管理员接口" if vertical_now else "B"
            app._authz_tree.insert("", "end", values=(acct, req["method"], req["url"], _payload_summary(req.get("body")), mark))
            # 基线用例：同一条 curl 也登记到「基线测试」列表（原样请求作为对照），按模式独立
            base_req = dict(req)
            base_req["_mode"] = "vertical" if vertical_now else "horizontal"
            app._authz_baseline_cases.append(base_req)
            b_acct = "管理员(基线)" if vertical_now else "B(基线)"
            app._authz_base_tree.insert("", "end", values=(b_acct, req["method"], req["url"], _payload_summary(req.get("body")), mark))
        else:
            # 水平：A 的 curl 登记备用（垂直模式旧逻辑保留）；
            # 垂直模式下 A=普通账号：只提取 Token 作为重放凭证，curl 不登记为用例
            if not app._authz_type_var.get().startswith("垂直越权"):
                req["_mode"] = "horizontal"
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


def _cur_mode(app):
    return "vertical" if app._authz_type_var.get().startswith("垂直越权") else "horizontal"


def _mode_baseline_cases(app):
    """当前模式下的基线用例（水平/垂直独立）。"""
    m = _cur_mode(app)
    return [r for r in app._authz_baseline_cases if r.get("_mode", m) == m]


def _mode_results(app):
    """当前模式下的越权测试结果。"""
    m = _cur_mode(app)
    return [r for r in app._authz_results if r.get("mode", m) == m]


def _mode_baseline_results(app):
    """当前模式下的基线测试结果。"""
    m = _cur_mode(app)
    return [r for r in app._authz_baseline_results if r.get("mode", m) == m]


def _refresh_result_trees(app):
    """按当前模式重建两个结果列表显示（数据保留，仅过滤显示）。"""
    vertical = _cur_mode(app) == "vertical"
    res = app._authz_res_tree
    res.delete(*res.get_children())
    for r in _mode_results(app):
        b = r.get("baseline")
        b_txt = ("HTTP %s" % b["status"]) if b and b.get("status") else ("失败" if r.get("baseline_err") or (r.get("baseline") is None and r.get("authz")) else "-")
        acct_txt = "普通账号(重放)" if vertical else "A(重放)"
        res.insert("", "end", values=(
            STATUS_TEXT.get(r["status"], r["status"]),
            r["req"]["url"], acct_txt, r.get("token", "-"),
            _payload_summary(r["req"].get("body")), b_txt, r["reason"]))
    bres = app._authz_base_res_tree
    bres.delete(*bres.get_children())
    for rec in _mode_baseline_results(app):
        resp = rec.get("baseline")
        b_status = ("HTTP %s" % resp["status"]) if resp else "失败"
        b_acct = "管理员(基线)" if vertical else "B(基线)"
        bres.insert("", "end", values=(
            b_status, rec["req"]["url"], b_acct, rec.get("token", "-"),
            _payload_summary(rec["req"].get("body")),
            b_status, rec.get("reason", "-")))


def _refresh_case_tree(app):
    """按当前模式刷新用例列表：水平→B 的用例；垂直→管理员接口。基线用例树同步刷新。"""
    tree = app._authz_tree
    tree.delete(*tree.get_children())
    btree = app._authz_base_tree
    btree.delete(*btree.get_children())
    vertical = _cur_mode(app) == "vertical"
    for req in _mode_baseline_cases(app):
        ids = find_resource_ids(req)
        mark = "✔" if ids else "-"
        b_acct = "管理员(基线)" if vertical else "B(基线)"
        btree.insert("", "end", values=(b_acct, req["method"], req["url"], _payload_summary(req.get("body")), mark))
    vertical = app._authz_type_var.get().startswith("垂直越权")
    if vertical:
        for req in app._authz_a_cases:
            if req.get("_mode", "vertical") != "vertical":
                continue
            ids = find_resource_ids(req)
            mark = "✔" if ids else "-"
            tree.insert("", "end", values=("管理员接口", req["method"], req["url"], _payload_summary(req.get("body")), mark))
    else:
        for c in app._authz_cases:
            if c.get("mode", "horizontal") != "horizontal":
                continue
            req = c["req"]
            ids = c.get("ids") or find_resource_ids(req)
            mark = "✔" if ids else "-"
            tree.insert("", "end", values=("B", req["method"], req["url"], _payload_summary(req.get("body")), mark))


def _clear_interfaces(app):
    """清空接口导入数据与账号凭证：curl 输入框、A/B Token 输入框（含按模式存储）。"""
    app._authz_curl_text.delete("1.0", "end")
    app._authz_acct_a_var.set("")
    app._authz_acct_b_var.set("")
    store = getattr(app, "_authz_cred_store", None)
    if store is not None:
        for m in ("horizontal", "vertical"):
            store[m] = {"a": "", "b": "", "curl": ""}
    app._notify("已清空接口导入数据与账号凭证")


def _clear_cases(app):
    app._authz_cases.clear()
    app._authz_a_cases.clear()
    app._authz_baseline_cases.clear()
    for item in app._authz_tree.get_children():
        app._authz_tree.delete(item)
    for item in app._authz_base_tree.get_children():
        app._authz_base_tree.delete(item)
    app._authz_case_count.config(text="A接口: 0 ｜ B用例: 0")


def _clear_results(app):
    app._authz_results.clear()
    for item in app._authz_res_tree.get_children():
        app._authz_res_tree.delete(item)
    app._authz_progress.config(text="")
    cur_m = _cur_mode(app)
    app._authz_baseline_results[:] = [r for r in app._authz_baseline_results if r.get("mode", cur_m) != cur_m]
    for item in app._authz_base_res_tree.get_children():
        app._authz_base_res_tree.delete(item)


def _selected_cases(app):
    vertical = _cur_mode(app) == "vertical"
    if vertical:
        pool = [r for r in app._authz_a_cases if r.get("_mode", "vertical") == "vertical"]
    else:
        pool = [c for c in app._authz_cases if c.get("mode", "horizontal") == "horizontal"]
    sel = app._authz_tree.selection()
    if sel:
        idxs = [app._authz_tree.index(s) for s in sel]
        return [{"req": pool[i]["req"]} if isinstance(pool[i], dict) and "req" in pool[i] else {"req": pool[i]} for i in idxs if i < len(pool)]
    if vertical:
        return [{"req": r} for r in pool]
    return [dict(c) for c in pool]


def _start_baseline_test(app):
    """独立基线测试：对「基线测试」列表中的用例原样发送请求（不换凭证），结果写入基线结果列表。"""
    runner = getattr(app, "_authz_runner", None)
    if runner and runner.is_alive():
        app._notify("测试正在进行中")
        return
    cases = _mode_baseline_cases(app)
    if not cases:
        app._notify("请先导入接口生成基线用例")
        return
    try:
        timeout = float(app._authz_timeout_var.get())
    except ValueError:
        timeout = 15.0
    app._authz_baseline_results.clear()
    for item in app._authz_base_res_tree.get_children():
        app._authz_base_res_tree.delete(item)
    q = app._authz_event_queue
    while not q.empty():
        q.get_nowait()
    vertical = app._authz_type_var.get().startswith("垂直越权")
    b_acct = "管理员(基线)" if vertical else "B(基线)"

    def worker():
        for i, req in enumerate(cases):
            q.put(("log", {"msg": "[%d/%d][基线] 接口: %s %s" % (i + 1, len(cases), req["method"], req["url"])}))
            q.put(("log", {"msg": "  → 基线请求：原样发送，使用 %s 的凭证 %s" % (b_acct, "; ".join(extract_auth_headers(req.get("headers")).values()) or "-")}))
            try:
                resp = send_request(req["method"], req["url"], req.get("headers"),
                                    req.get("body"), timeout)
                reason = "基线请求（原样访问，作为对照）"
            except Exception as e:
                resp, reason = None, "基线请求失败: %s" % e
            rec = {"req": req, "baseline": resp, "baseline_err": None if resp else reason,
                   "status": "baseline", "mode": "vertical" if vertical else "horizontal",
                   "reason": reason, "token": "; ".join(extract_auth_headers(req.get("headers")).values()) or "-"}
            q.put(("b_progress", {"index": i + 1, "total": len(cases), "record": rec, "b_acct": b_acct}))
        q.put(("b_done", {"total": len(cases)}))

    app._notify("【基线测试】开始，共 %d 条用例（原样发送，不换凭证）" % len(cases))
    t = threading.Thread(target=worker, daemon=True)
    app._authz_baseline_thread = t
    t.start()
    app.after(100, lambda: _poll_events(app))


def _start_test(app):
    runner = getattr(app, "_authz_runner", None)
    if runner and runner.is_alive():
        app._notify("测试正在进行中")
        return
    token_a = app._authz_acct_a_var.get().strip()
    if not token_a:
        app._notify("请先导入接口自动提取 Token，或手动粘贴账号A(普通账号)的 Token")
        return
    token_a_headers = _get_headers_from_token(token_a)
    # 校验：A 的 Token 不能与账号B输入框中的 Token 相同（否则越权重放无意义）
    token_b_val = app._authz_acct_b_var.get().strip()
    if token_b_val and token_a == token_b_val:
        app._notify("[警告] 账号A与账号B的 Token 相同！请确认 A 框里填的是账号A自己的凭证")
        return
    vertical = app._authz_type_var.get().startswith("垂直越权")

    if vertical:
        cases = [{"req": req} for req in app._authz_a_cases if req.get("_mode", "vertical") == "vertical"]
        if not cases:
            app._notify("垂直越权模式请先「导入(管理员账号)」管理员接口 curl")
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
    # 只清当前模式的越权结果，基线结果与另一模式结果独立保留
    cur_m0 = _cur_mode(app)
    app._authz_results[:] = [r for r in app._authz_results if r.get("mode", cur_m0) != cur_m0]
    for item in app._authz_res_tree.get_children():
        app._authz_res_tree.delete(item)
    app._authz_progress.config(text="")
    q = app._authz_event_queue
    while not q.empty():
        q.get_nowait()
    admin_headers = {}
    if vertical and token_b_val:
        admin_headers = _get_headers_from_token(token_b_val)  # 管理员 Token 作为可选基线
    # 已保存的基线响应按 URL 复用，越权测试不再重发基线请求
    stored = {}
    cur_m = "vertical" if vertical else "horizontal"
    for r in app._authz_baseline_results:
        if r.get("mode", cur_m) != cur_m:
            continue
        if r.get("baseline") and r["req"].get("url") not in stored:
            stored[r["req"]["url"]] = r["baseline"]
    app._notify("【越权测试】开始，共 %d 条用例（使用 A 的 Token 重放，基线仅复用已存结果）" % len(cases))
    app._authz_runner = IdorRunner(cases, token_a_headers, q,
                                   timeout=timeout,
                                   mode="vertical" if vertical else "horizontal",
                                   admin_headers=admin_headers,
                                   stored_baseline=stored)
    app._authz_runner.start()
    app.after(100, lambda: _poll_events(app))


def _poll_events(app):
    """UI 主线程轮询消费测试事件"""
    q = app._authz_event_queue
    try:
        while True:
            event, data = q.get_nowait()
            _on_event(app, event, data)
            if event in ("done", "stopped", "b_done"):
                return
    except queue.Empty:
        pass
    runner = getattr(app, "_authz_runner", None)
    bt = getattr(app, "_authz_baseline_thread", None)
    if (runner and runner.is_alive()) or (bt and bt.is_alive()):
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
        # 基线结果由「开始基线测试」独立产生，越权测试不再往基线列表写数据
        acct_txt = "普通账号(重放)" if r.get("mode") == "vertical" else "A(重放)"
        app._authz_res_tree.insert("", "end", values=(
            STATUS_TEXT.get(r["status"], r["status"]),
            r["req"]["url"], acct_txt, r.get("token", "-"),
            _payload_summary(r["req"].get("body")), b_txt, r["reason"]))
        _log(app, "[%s] %s %s | Token: %s | %s" % (
            STATUS_TEXT.get(r["status"], r["status"]), r["req"]["method"], r["req"]["url"],
            r.get("token", "-"), r["reason"]))
        app._authz_progress.config(text="进度: %d 条" % len(app._authz_results))
    elif event == "b_progress":
        rec = data["record"]
        app._authz_baseline_results.append(rec)
        resp = rec.get("baseline")
        b_status = ("HTTP %s" % resp["status"]) if resp else "失败"
        app._authz_base_res_tree.insert("", "end", values=(
            b_status, rec["req"]["url"], data["b_acct"], rec.get("token", "-"),
            _payload_summary(rec["req"].get("body")),
            b_status, rec.get("reason", "-")))
        _log(app, "[基线%s] %s %s | Token: %s | %s" % (
            b_status, rec["req"]["method"], rec["req"]["url"],
            rec.get("token", "-"), rec.get("reason", "-")))
        app._authz_progress.config(text="基线测试进度: %d/%d 条" % (data["index"], data["total"]))
    elif event == "b_done":
        n_ok = sum(1 for r in app._authz_baseline_results if r.get("baseline"))
        n_fail = len(app._authz_baseline_results) - n_ok
        app._authz_progress.config(text="基线测试完成: 成功 %d ｜ 失败 %d" % (n_ok, n_fail))
        app._notify("基线测试完成：成功 %d，失败 %d" % (n_ok, n_fail))
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
    pool = _mode_results(app)
    if idx >= len(pool):
        return
    r = pool[idx]

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
    cur_results = _mode_results(app)
    if not cur_results:
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

    for r in cur_results:
        req = r["req"]
        lines.append("## %s %s" % (req["method"], req["url"]))
        lines.append("- 状态: %s" % STATUS_TEXT.get(r["status"], r["status"]))
        lines.append("- 判定: %s" % r["reason"])
        lines.append("- 账号: %s" % ("普通账号(重放)" if r.get("mode") == "vertical" else "A(重放)"))
        lines.append("- 使用的Token: %s" % r.get("token", "-"))
        lines.append("- Payload: %s" % _payload_summary(req.get("body")))
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
