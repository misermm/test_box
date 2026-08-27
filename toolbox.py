#!/usr/bin/env python3
"""
图片工具箱
集成: 图片转PDF / 文件分割 / 文件合并 / 生成指定大小文件
"""

import os
os.environ['PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT'] = '0'

# Monkey-patch: 绕过 paddlex 在 PyInstaller exe 中的依赖检查
# importlib.metadata 在冻结 exe 中找不到包元数据，但依赖实际已安装
import paddlex.utils.deps as _pdx_deps
_pdx_deps.is_extra_available = lambda extra: True
_pdx_deps.is_dep_available = lambda dep, check_version=False: True

import re
import json
import tempfile
import threading
import contextlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageGrab, ImageTk
import cv2

from image_to_pdf import merge_images_to_pdf, convert_images_to_zip
from file_splitter import split_to_zip, merge_zip_files
from generate_file import create_file
from generate_text import generate_text, TEXT_TYPES
from generate_person import generate_person, generate_id_card, generate_name, generate_phone
from url_codec import url_encode, url_decode
from http_client import send_request, parse_headers, format_response
from json_fmt import json_format, json_compact, json_sort, json_diff_spans


# ==================== 截图表格识别模块 ====================

class RegionSelector(tk.Toplevel):
    """全屏遮罩 + 鼠标拖拽选区"""

    def __init__(self, parent=None, callback=None):
        super().__init__(parent)
        self.callback = callback
        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        self._result_image = None

        # 全屏无边框窗口
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.configure(bg="black")
        self.attributes("-alpha", 0.3)

        # Canvas 用于绘制选框
        self.canvas = tk.Canvas(self, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # 提示文字
        self.canvas.create_text(
            self.winfo_screenwidth() // 2,
            30,
            text="拖动鼠标框选表格区域，松开鼠标确认 | 按 ESC 取消",
            fill="white",
            font=("Microsoft YaHei UI", 14, "bold"),
        )

        # 绑定事件
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Escape>", self._on_cancel)

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=2, dash=(5, 3)
        )

    def _on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event):
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)

        width = x2 - x1
        height = y2 - y1

        if width < 10 or height < 10:
            self._on_cancel()
            return

        self.withdraw()
        self.update()

        # 截取选区
        screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        self._result_image = screenshot

        if self.callback:
            self.callback(screenshot)

        self.destroy()

    def _on_cancel(self, event=None):
        self._result_image = None
        if self.callback:
            self.callback(None)
        self.destroy()

    def get_image(self):
        return self._result_image


def capture_region(parent=None, callback=None):
    """弹出区域选择窗口，截图后通过callback返回PIL.Image"""
    selector = RegionSelector(parent=parent, callback=callback)
    return selector


def recognize_table(image_path_or_pil):
    """识别图片中的表格（使用paddlex table_recognition流水线）"""
    os.environ['PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT'] = '0'
    try:
        import cv2
    except ImportError:
        raise ImportError("缺少 opencv-python 库，请运行: pip install opencv-python")
    from paddlex import create_pipeline

    temp_file = None
    if isinstance(image_path_or_pil, Image.Image):
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        image_path_or_pil.save(temp_file.name)
        temp_file.close()
        image_path = temp_file.name
    else:
        image_path = image_path_or_pil

    try:
        print("正在加载识别模型...")
        pipeline = create_pipeline(pipeline='table_recognition')
        print("模型加载完成，开始识别表格...")
        output = list(pipeline.predict(input=image_path))
        print("识别完成，正在解析结果...")

        all_table_data = []
        html_parts = []

        for res in output:
            html_dict = res.html if hasattr(res, 'html') else {}
            if isinstance(html_dict, dict):
                for key, html_str in html_dict.items():
                    if html_str:
                        html_parts.append(html_str)
                        table_data = html_to_table_data(html_str)
                        if table_data:
                            all_table_data.extend(table_data)
            elif isinstance(html_dict, str) and html_dict:
                html_parts.append(html_dict)
                table_data = html_to_table_data(html_dict)
                if table_data:
                    all_table_data.extend(table_data)

        combined_html = "\n".join(html_parts) if html_parts else ""
        return all_table_data, combined_html

    finally:
        if temp_file:
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass


def html_to_table_data(html):
    """将HTML表格转换为二维列表"""
    rows = []
    tr_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
    td_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)

    for tr_match in tr_pattern.finditer(html):
        tr_content = tr_match.group(1)
        cells = []
        for td_match in td_pattern.finditer(tr_content):
            cell_text = td_match.group(1)
            cell_text = re.sub(r"<[^>]+>", "", cell_text)
            cell_text = cell_text.strip()
            cells.append(cell_text)
        if cells:
            rows.append(cells)

    return rows


def table_data_to_html(table_data):
    """将二维列表转换为HTML表格"""
    if not table_data:
        return ""

    html = '<table border="1">\n'
    for i, row in enumerate(table_data):
        html += "  <tr>\n"
        tag = "th" if i == 0 else "td"
        for cell in row:
            html += f"    <{tag}>{cell}</{tag}>\n"
        html += "  </tr>\n"
    html += "</table>"
    return html


def table_data_to_tsv(table_data):
    """将二维列表转换为TSV格式（Tab分隔，可直接粘贴到Excel）"""
    if not table_data:
        return ""

    lines = []
    for row in table_data:
        line = "\t".join(str(cell) for cell in row)
        lines.append(line)
    return "\n".join(lines)


def table_data_to_clipboard(widget, table_data):
    """将表格数据复制到剪贴板（TSV格式）"""
    tsv = table_data_to_tsv(table_data)
    widget.clipboard_clear()
    widget.clipboard_append(tsv)
    return tsv


# ==================== 主程序 ====================

APP_NAME = "测试工具箱"
APP_VERSION = "1.0.0"

IMAGE_EXTS = [
    ("图片文件", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.gif"),
    ("所有文件", "*.*"),
]


class LogBuffer:
    """线程安全的标准输出重定向缓冲"""

    def __init__(self):
        self._data = []
        self._lock = threading.Lock()

    def write(self, s):
        with self._lock:
            self._data.append(s)

    def flush(self):
        pass

    def read_and_clear(self):
        with self._lock:
            data = "".join(self._data)
            self._data.clear()
        return data


class ToolboxApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("980x680")
        self.minsize(820, 560)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._buffer = LogBuffer()
        self._poll_job = None
        self._task_thread = None
        self._running = False
        self._page_frames = {}
        self._page_logs = {}
        self._current_menu_index = None
        self._log_owner = None
        self._task_page = None

        # 持久化变量（切换页面时保留值）
        DEFAULT_DATA = r"C:\work\ai\picture_to_pdf\data"
        self._pdf_images = []
        self._pdf_out_var = tk.StringVar(value=DEFAULT_DATA)
        self._zip_images = []
        self._zip_out_var = tk.StringVar(value=DEFAULT_DATA)
        self._split_in_var = tk.StringVar()
        self._split_size_var = tk.StringVar(value="101")
        self._split_out_var = tk.StringVar(value=DEFAULT_DATA)
        self._split_prefix_var = tk.StringVar(value="part")
        self._merge_files = []
        self._merge_out_var = tk.StringVar(value=DEFAULT_DATA)
        self._gen_size_var = tk.StringVar(value="101")
        self._gen_type_var = tk.StringVar(value="zip")
        self._gen_corrupt_var = tk.StringVar(value="正常")
        self._gen_out_var = tk.StringVar(value=DEFAULT_DATA)
        self._text_len_var = tk.StringVar(value="100")
        self._text_type_var = tk.StringVar(value="汉字+英文+中英文标点")
        self._http_url_var = tk.StringVar()

        # OCR表格识别相关变量
        self._ocr_hotkey_var = tk.StringVar(value="Ctrl+Shift+T")
        self._ocr_table_data = []
        self._ocr_image = None
        self._ocr_listener = None

        self._build_ui()
        self._select_menu(0)

    # ---------------- UI 搭建 ----------------
    def _build_ui(self):
        left = tk.Frame(self, bg="#2c3e50", width=200)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="功能菜单", fg="white", bg="#2c3e50",
                 font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(20, 10))

        self.menu_list = tk.Listbox(
            left, bg="#34495e", fg="white", bd=0, highlightthickness=0,
            selectbackground="#1abc9c", font=("Microsoft YaHei UI", 11),
            activestyle="none",
        )
        for item in ["图片转 PDF", "图片批量转ZIP", "文件分割", "文件合并", "生成指定大小文件", "生成指定长度文本", "随机人员信息", "URL编码解码", "接口请求", "JSON格式化", "JSON对比", "截图识别表格", "关于"]:
            self.menu_list.insert("end", item)
        self.menu_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.menu_list.bind("<<ListboxSelect>>", self._on_menu_select)

        right = tk.Frame(self, bg="#f5f6fa")
        right.pack(side="left", fill="both", expand=True)

        self.title_label = tk.Label(right, bg="#f5f6fa", fg="#2c3e50",
                                    font=("Microsoft YaHei UI", 16, "bold"))
        self.title_label.pack(anchor="w", padx=20, pady=(15, 5))

        self.content = None
        self.page_container = tk.Frame(right, bg="#f5f6fa")
        self.page_container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.log_frame = tk.LabelFrame(right, text="运行日志", bg="#f5f6fa",
                                       font=("Microsoft YaHei UI", 10))
        self.log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.log = tk.Text(self.log_frame, height=8, bg="#2d3436", fg="#b2bec3",
                           font=("Consolas", 9), state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=5, pady=5)
        self.log.tag_config("ok", foreground="#2ecc71",
                            font=("Microsoft YaHei UI", 12, "bold"))
        self.log.tag_config("err", foreground="#e74c3c",
                            font=("Microsoft YaHei UI", 12, "bold"))

    # ---------------- 菜单切换 ----------------
    def _on_menu_select(self, _event=None):
        sel = self.menu_list.curselection()
        if sel:
            self._select_menu(sel[0])

    def _page_title(self, index):
        return ["图片转 PDF", "图片批量转 ZIP", "文件分割", "文件合并",
                "生成指定大小文件", "生成指定长度文本", "随机人员信息",
                "URL编码解码", "接口请求", "JSON格式化", "JSON对比", "截图识别表格", "关于"][index]

    def _select_menu(self, index):
        self.menu_list.selection_clear(0, "end")
        self.menu_list.selection_set(index)
        self.menu_list.activate(index)

        self._save_current_log()

        if self.content is not None:
            self.content.pack_forget()

        self._current_menu_index = index
        self._log_owner = index
        self.title_label.config(text=self._page_title(index))

        frame = self._page_frames.get(index)
        if frame is None:
            frame = tk.Frame(self.page_container, bg="#f5f6fa")
            self._page_frames[index] = frame
            self.content = frame
            if index == 0:
                self._show_page_pdf()
            elif index == 1:
                self._show_page_zip()
            elif index == 2:
                self._show_page_split()
            elif index == 3:
                self._show_page_merge()
            elif index == 4:
                self._show_page_generate()
            elif index == 5:
                self._show_page_text()
            elif index == 6:
                self._show_page_person()
            elif index == 7:
                self._show_page_url()
            elif index == 8:
                self._show_page_http()
            elif index == 9:
                self._show_page_json()
            elif index == 10:
                self._show_page_jsondiff()
            elif index == 11:
                self._show_page_ocr_table()
            else:
                self._show_page_about()
        else:
            self.content = frame

        frame.pack(fill="both", expand=True)

        self._restore_log()

    # ---------------- 日志 ----------------
    def _save_current_log(self):
        if self._log_owner is None:
            return
        content = self.log.get("1.0", "end-1c")
        if content.strip():
            self._page_logs[self._log_owner] = content
        else:
            self._page_logs.pop(self._log_owner, None)

    def _restore_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        content = self._page_logs.get(self._log_owner)
        if content:
            for line in content.split("\n"):
                if "任务完成" in line:
                    self.log.insert("end", line + "\n", "ok")
                elif "任务失败" in line:
                    self.log.insert("end", line + "\n", "err")
                else:
                    self.log.insert("end", line + "\n")
            self.log.see("end")
        self.log.config(state="disabled")

    def _append_log_text(self, text):
        """追加任务日志：当前显示的就是任务所属页面时写控件，否则写入该页存储"""
        if self._task_page is None or self._log_owner == self._task_page:
            self.log.insert("end", text)
            self.log.see("end")
            self._save_current_log()
        else:
            stored = self._page_logs.get(self._task_page, "")
            self._page_logs[self._task_page] = stored + text.replace("\r", "\n")

    def _log(self, text):
        self.log.config(state="normal")
        self._append_log_text(text)
        self.log.config(state="disabled")

    def _flush_log(self, data):
        if not data:
            return
        for chunk in data.split("\r"):
            if not chunk:
                continue
            if "\n" in chunk:
                for line in chunk.split("\n"):
                    self._log(line + "\n")
            else:
                # \r 进度行：替换控件中的最后一行
                self.log.config(state="normal")
                self.log.delete("end-1l", "end")
                self._append_log_text(chunk)
                self.log.config(state="disabled")

    def _notify(self, text):
        """用日志代替弹窗提示"""
        self.log.config(state="normal")
        self._append_log_text(f"[提示] {text}\n")
        self.log.config(state="disabled")

    def _start_task(self, func, *args, on_done=None):
        if self._running:
            self._notify("有任务正在运行，请等待完成")
            return
        self._buffer = LogBuffer()
        self._task_page = self._current_menu_index
        self._save_current_log()
        self._page_logs.pop(self._current_menu_index, None)
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        self._running = True
        self._on_done = on_done
        self._result_box = []
        self._task_error = None

        def worker():
            try:
                with contextlib.redirect_stdout(self._buffer):
                    result = func(*args)
                self._result_box.append(result)
            except Exception as e:
                self._buffer.write(f"\n[错误] {e}\n")
                self._task_error = e

        self._task_thread = threading.Thread(target=worker, daemon=True)
        self._task_thread.start()
        self._poll_job = self.after(80, self._poll_log)

    def _poll_log(self):
        if not self._running:
            return
        self._flush_log(self._buffer.read_and_clear())
        if self._task_thread is not None and not self._task_thread.is_alive():
            self._finish_task()
            return
        self._poll_job = self.after(80, self._poll_log)

    def _finish_task(self):
        self._running = False
        if self._poll_job:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        self._flush_log(self._buffer.read_and_clear())
        result = self._result_box[0] if self._result_box else None
        if self._task_error:
            result = None
        self._task_thread = None
        if self._on_done:
            try:
                self._on_done(result)
            except tk.TclError:
                # 任务运行中用户切换了页面，回调涉及的控件已被销毁，忽略
                pass

    def _log_result_banner(self, ok):
        tag = "ok" if ok else "err"
        mark = "√" * 8 if ok else "×" * 8
        text = f" 任务完成 " if ok else " 任务失败 "
        self.log.config(state="normal")
        if self._task_page is None or self._log_owner == self._task_page:
            self.log.insert("end", f"\n{mark}{text}{mark}\n\n", tag)
            self.log.see("end")
            self._save_current_log()
        else:
            stored = self._page_logs.get(self._task_page, "")
            self._page_logs[self._task_page] = stored + f"\n{mark}{text}{mark}\n\n"
        self.log.config(state="disabled")

    def _on_done_success(self, result):
        self._log_result_banner(bool(result))

    # ---------------- 通用控件 ----------------
    def _label(self, parent, text):
        return tk.Label(parent, text=text, bg="#f5f6fa",
                        font=("Microsoft YaHei UI", 10))

    def _row(self, parent):
        row = tk.Frame(parent, bg="#f5f6fa")
        row.pack(fill="x", pady=5)
        return row

    # =============== 页面1: 图片转PDF ===============
    def _show_page_pdf(self):
        self.title_label.config(text="图片转 PDF")

        self._label(self.content, "选择多张图片，按顺序合并为一个 PDF 文件（每张图片一页）。").pack(anchor="w", pady=(0, 8))

        list_frame = tk.Frame(self.content, bg="#f5f6fa")
        list_frame.pack(fill="both", expand=True)

        self._pdf_listbox = tk.Listbox(list_frame, font=("Microsoft YaHei UI", 10))
        self._pdf_listbox.pack(side="left", fill="both", expand=True)

        btn_frame = tk.Frame(list_frame, bg="#f5f6fa")
        btn_frame.pack(side="left", fill="y", padx=(10, 0))
        tk.Button(btn_frame, text="添加图片", command=self._pdf_add, width=12).pack(pady=3)
        tk.Button(btn_frame, text="移除选中", command=self._pdf_remove, width=12).pack(pady=3)
        tk.Button(btn_frame, text="清空列表", command=self._pdf_clear, width=12).pack(pady=3)

        out_row = self._row(self.content)
        self._label(out_row, "输出路径:").pack(side="left")
        tk.Entry(out_row, textvariable=self._pdf_out_var).pack(
            side="left", padx=8, fill="x", expand=True)
        tk.Button(out_row, text="浏览", command=self._pdf_choose_out).pack(side="left")

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="开始转换", command=self._pdf_convert,
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=18).pack(pady=(6, 0))

    def _pdf_add(self):
        files = filedialog.askopenfilenames(title="选择图片", filetypes=IMAGE_EXTS)
        for f in files:
            self._pdf_images.append(f)
            self._pdf_listbox.insert("end", os.path.basename(f))

    def _pdf_remove(self):
        sel = self._pdf_listbox.curselection()
        for i in reversed(sel):
            self._pdf_listbox.delete(i)
            del self._pdf_images[i]

    def _pdf_clear(self):
        self._pdf_listbox.delete(0, "end")
        self._pdf_images.clear()

    def _pdf_choose_out(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self._pdf_out_var.set(d)

    def _pdf_convert(self):
        if not self._pdf_images:
            self._notify("请先添加图片")
            return
        out_dir = self._pdf_out_var.get().strip()
        if not out_dir:
            self._notify("请设置输出路径")
            return
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, "output.pdf")
        self._start_task(merge_images_to_pdf, list(self._pdf_images), out,
                         on_done=self._on_done_success)

    # =============== 页面2: 图片批量转ZIP ===============
    def _show_page_zip(self):
        self.title_label.config(text="图片批量转 ZIP")

        self._label(self.content, "每张图片单独转换为一个 PDF，全部打包到一个 ZIP 压缩包中。").pack(anchor="w", pady=(0, 8))

        list_frame = tk.Frame(self.content, bg="#f5f6fa")
        list_frame.pack(fill="both", expand=True)

        self._zip_listbox = tk.Listbox(list_frame, font=("Microsoft YaHei UI", 10))
        self._zip_listbox.pack(side="left", fill="both", expand=True)

        btn_frame = tk.Frame(list_frame, bg="#f5f6fa")
        btn_frame.pack(side="left", fill="y", padx=(10, 0))
        tk.Button(btn_frame, text="添加图片", command=self._zip_add, width=12).pack(pady=3)
        tk.Button(btn_frame, text="移除选中", command=self._zip_remove, width=12).pack(pady=3)
        tk.Button(btn_frame, text="清空列表", command=self._zip_clear, width=12).pack(pady=3)

        out_row = self._row(self.content)
        self._label(out_row, "输出路径:").pack(side="left")
        tk.Entry(out_row, textvariable=self._zip_out_var).pack(
            side="left", padx=8, fill="x", expand=True)
        tk.Button(out_row, text="浏览", command=self._zip_choose_out).pack(side="left")

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="开始转换", command=self._zip_convert,
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=18).pack(pady=(6, 0))

    def _zip_add(self):
        files = filedialog.askopenfilenames(title="选择图片", filetypes=IMAGE_EXTS)
        for f in files:
            self._zip_images.append(f)
            self._zip_listbox.insert("end", os.path.basename(f))

    def _zip_remove(self):
        sel = self._zip_listbox.curselection()
        for i in reversed(sel):
            self._zip_listbox.delete(i)
            del self._zip_images[i]

    def _zip_clear(self):
        self._zip_listbox.delete(0, "end")
        self._zip_images.clear()

    def _zip_choose_out(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self._zip_out_var.set(d)

    def _zip_convert(self):
        if not self._zip_images:
            self._notify("请先添加图片")
            return
        out_dir = self._zip_out_var.get().strip()
        if not out_dir:
            self._notify("请设置输出路径")
            return
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, "images_pdfs.zip")
        self._start_task(convert_images_to_zip, list(self._zip_images), out,
                         on_done=self._on_done_success)

    # =============== 页面3: 文件分割 ===============
    def _show_page_split(self):
        self.title_label.config(text="文件分割")
        self._label(self.content, "将一个文件按指定大小分割为多个 ZIP 文件。").pack(anchor="w", pady=(0, 8))

        r1 = self._row(self.content)
        self._label(r1, "输入文件:").pack(side="left")
        tk.Entry(r1, textvariable=self._split_in_var).pack(side="left", padx=8, fill="x", expand=True)
        tk.Button(r1, text="浏览", command=self._split_choose_in).pack(side="left")

        r2 = self._row(self.content)
        self._label(r2, "分片大小(MB):").pack(side="left")
        tk.Entry(r2, textvariable=self._split_size_var, width=12).pack(side="left", padx=8)

        r3 = self._row(self.content)
        self._label(r3, "输出目录:").pack(side="left")
        tk.Entry(r3, textvariable=self._split_out_var).pack(side="left", padx=8, fill="x", expand=True)
        tk.Button(r3, text="浏览", command=self._split_choose_out).pack(side="left")

        r4 = self._row(self.content)
        self._label(r4, "文件名前缀:").pack(side="left")
        tk.Entry(r4, textvariable=self._split_prefix_var, width=12).pack(side="left", padx=8)

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="开始分割", command=self._split_run,
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=18).pack(pady=(6, 0))

    def _split_choose_in(self):
        f = filedialog.askopenfilename(title="选择文件")
        if f:
            self._split_in_var.set(f)

    def _split_choose_out(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self._split_out_var.set(d)

    def _split_run(self):
        f = self._split_in_var.get().strip()
        if not f or not os.path.exists(f):
            self._notify("请选择有效的输入文件")
            return
        try:
            size = float(self._split_size_var.get())
        except ValueError:
            self._notify("请输入有效的分片大小")
            return
        if size <= 0:
            self._notify("分片大小必须大于0")
            return
        out = self._split_out_var.get().strip()
        if not out:
            self._notify("请设置输出目录")
            return
        os.makedirs(out, exist_ok=True)
        self._start_task(split_to_zip, f, out, size,
                         self._split_prefix_var.get() or "part",
                         on_done=self._on_done_success)

    # =============== 页面4: 文件合并 ===============
    def _show_page_merge(self):
        self.title_label.config(text="文件合并")

        self._label(self.content, "选择分割生成的多个 ZIP 文件，合并还原为原始文件。").pack(anchor="w", pady=(0, 8))

        list_frame = tk.Frame(self.content, bg="#f5f6fa")
        list_frame.pack(fill="both", expand=True)

        self._merge_listbox = tk.Listbox(list_frame, font=("Microsoft YaHei UI", 10))
        self._merge_listbox.pack(side="left", fill="both", expand=True)

        btn_frame = tk.Frame(list_frame, bg="#f5f6fa")
        btn_frame.pack(side="left", fill="y", padx=(10, 0))
        tk.Button(btn_frame, text="添加ZIP", command=self._merge_add, width=12).pack(pady=3)
        tk.Button(btn_frame, text="移除选中", command=self._merge_remove, width=12).pack(pady=3)
        tk.Button(btn_frame, text="清空列表", command=self._merge_clear, width=12).pack(pady=3)

        out_row = self._row(self.content)
        self._label(out_row, "输出路径:").pack(side="left")
        tk.Entry(out_row, textvariable=self._merge_out_var).pack(side="left", padx=8, fill="x", expand=True)
        tk.Button(out_row, text="浏览", command=self._merge_choose_out).pack(side="left")

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="开始合并", command=self._merge_run,
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=18).pack(pady=(6, 0))

    def _merge_add(self):
        files = filedialog.askopenfilenames(title="选择ZIP文件", filetypes=[("ZIP文件", "*.zip")])
        for f in files:
            self._merge_files.append(f)
            self._merge_listbox.insert("end", os.path.basename(f))

    def _merge_remove(self):
        sel = self._merge_listbox.curselection()
        for i in reversed(sel):
            self._merge_listbox.delete(i)
            del self._merge_files[i]

    def _merge_clear(self):
        self._merge_listbox.delete(0, "end")
        self._merge_files.clear()

    def _merge_choose_out(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self._merge_out_var.set(d)

    def _merge_run(self):
        if not self._merge_files:
            self._notify("请先添加ZIP文件")
            return
        out_dir = self._merge_out_var.get().strip()
        if not out_dir:
            self._notify("请设置输出路径")
            return
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, "merged.bin")
        self._start_task(merge_zip_files, list(self._merge_files), out,
                         on_done=self._on_done_success)

    # =============== 页面5: 生成指定大小文件 ===============
    def _show_page_generate(self):
        self.title_label.config(text="生成指定大小文件")
        self._label(self.content, "生成指定大小和格式的文件（如 101MB 的 ZIP 文件）。").pack(anchor="w", pady=(0, 8))

        r1 = self._row(self.content)
        self._label(r1, "文件大小(MB):").pack(side="left")
        tk.Entry(r1, textvariable=self._gen_size_var, width=12).pack(side="left", padx=8)

        r2 = self._row(self.content)
        self._label(r2, "文件类型:").pack(side="left")
        ttk.Combobox(r2, textvariable=self._gen_type_var, state="readonly",
                     values=["zip", "plain", "pdf", "docx", "xlsx"], width=10).pack(side="left", padx=8)

        r4 = self._row(self.content)
        self._label(r4, "文件状态:").pack(side="left")
        ttk.Combobox(r4, textvariable=self._gen_corrupt_var, state="readonly",
                     values=["正常", "损坏"], width=10).pack(side="left", padx=8)

        r3 = self._row(self.content)
        self._label(r3, "输出目录:").pack(side="left")
        tk.Entry(r3, textvariable=self._gen_out_var).pack(side="left", padx=8, fill="x", expand=True)
        tk.Button(r3, text="浏览", command=self._gen_choose_out).pack(side="left")

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="开始生成", command=self._gen_run,
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=18).pack(pady=(6, 0))

    def _gen_choose_out(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self._gen_out_var.set(d)

    def _gen_run(self):
        try:
            size = float(self._gen_size_var.get())
        except ValueError:
            self._notify("请输入有效的大小")
            return
        if size <= 0:
            self._notify("大小必须大于0")
            return
        ftype = self._gen_type_var.get()
        ext_map = {"zip": "zip", "plain": "bin", "pdf": "pdf", "docx": "docx", "xlsx": "xlsx"}
        ext = ext_map.get(ftype, "bin")
        out_dir = self._gen_out_var.get().strip()
        if not out_dir:
            self._notify("请设置输出目录")
            return
        os.makedirs(out_dir, exist_ok=True)
        corrupted = self._gen_corrupt_var.get() == "损坏"
        suffix = "_corrupted" if corrupted else ""
        out_file = os.path.join(out_dir, f"file_{size:g}{suffix}.{ext}")
        self._start_task(create_file, out_file, size, ftype, corrupted,
                         on_done=self._on_done_success)

    # =============== 页面6: 生成指定长度文本 ===============
    def _show_page_text(self):
        self.title_label.config(text="生成指定长度文本")
        self._label(self.content, "输入长度和类型，生成对应长度的随机文本（可保存为txt）。").pack(anchor="w", pady=(0, 8))

        r1 = self._row(self.content)
        self._label(r1, "文本长度(字符):").pack(side="left")
        tk.Entry(r1, textvariable=self._text_len_var, width=12).pack(side="left", padx=8)

        r2 = self._row(self.content)
        self._label(r2, "类型:").pack(side="left")
        ttk.Combobox(r2, textvariable=self._text_type_var, state="readonly",
                     values=TEXT_TYPES, width=26).pack(side="left", padx=8)

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="生成", command=self._text_run,
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=16).pack(side="left", pady=(6, 0))
        tk.Button(btn_row, text="复制结果", command=self._text_copy, width=12).pack(side="left", padx=(10, 0))

        tk.Label(self.content, text="生成结果:", bg="#f5f6fa",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(8, 3))

        self._text_result = tk.Text(self.content, height=8, font=("Consolas", 10),
                                    wrap="word", bg="white")
        self._text_result.pack(fill="both", expand=True)

    def _text_run(self):
        try:
            length = int(self._text_len_var.get())
        except ValueError:
            self._notify("请输入有效的长度")
            return
        if length < 1:
            self._notify("长度必须大于0")
            return
        text_type = self._text_type_var.get()
        self._text_result.delete("1.0", "end")
        self._text_result.insert("1.0", "正在生成...")
        self._start_task(self._text_generate, length, text_type,
                         on_done=self._text_done)

    def _text_generate(self, length, text_type):
        text = generate_text(length, text_type)
        print(f"已生成 {len(text)} 字符文本")
        return text

    def _text_done(self, result):
        if result:
            self._text_result.delete("1.0", "end")
            self._text_result.insert("1.0", result)
        else:
            self._text_result.delete("1.0", "end")
            self._log_result_banner(False)

    def _text_copy(self):
        text = self._text_result.get("1.0", "end-1c")
        if not text:
            self._notify("没有可复制的内容")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._notify("已复制到剪贴板")

    # =============== 页面7: 随机人员信息 ===============
    def _show_page_person(self):
        self.title_label.config(text="随机人员信息")
        self._label(self.content, "根据输入的年龄和性别，生成随机人员信息（身份证号、姓名、手机号等）。").pack(anchor="w", pady=(0, 8))

        r1 = self._row(self.content)
        self._label(r1, "年龄:").pack(side="left")
        self._person_age_var = tk.StringVar(value="30")
        tk.Entry(r1, textvariable=self._person_age_var, width=8).pack(side="left", padx=8)

        r2 = self._row(self.content)
        self._label(r2, "性别:").pack(side="left")
        self._person_gender_var = tk.StringVar(value="女")
        ttk.Combobox(r2, textvariable=self._person_gender_var, state="readonly",
                     values=["男", "女"], width=8).pack(side="left", padx=8)

        r3 = self._row(self.content)
        self._label(r3, "生成数量:").pack(side="left")
        self._person_count_var = tk.StringVar(value="5")
        tk.Entry(r3, textvariable=self._person_count_var, width=8).pack(side="left", padx=8)

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="生成", command=self._person_run,
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=16).pack(side="left", pady=(6, 0))
        tk.Button(btn_row, text="复制全部", command=self._person_copy, width=12).pack(side="left", padx=(10, 0))

        tk.Label(self.content, text="生成结果:", bg="#f5f6fa",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(8, 3))

        self._person_result = tk.Text(self.content, height=10, font=("Consolas", 10),
                                      wrap="word", bg="white")
        self._person_result.pack(fill="both", expand=True)

    def _person_run(self):
        try:
            age = int(self._person_age_var.get())
        except ValueError:
            self._notify("请输入有效的年龄")
            return
        if age < 1 or age > 150:
            self._notify("年龄应在1-150之间")
            return

        gender = self._person_gender_var.get()

        try:
            count = int(self._person_count_var.get())
        except ValueError:
            self._notify("请输入有效的数量")
            return
        if count < 1 or count > 100:
            self._notify("数量应在1-100之间")
            return

        self._person_result.delete("1.0", "end")
        self._person_result.insert("1.0", "正在生成...")
        self._start_task(self._person_generate, age, gender, count,
                         on_done=self._person_done)

    def _person_generate(self, age, gender, count):
        lines = []
        header = f"{'姓名':<8} {'性别':<4} {'年龄':<4} {'出生日期':<12} {'身份证号':<20} {'手机号':<12}"
        lines.append(header)
        lines.append("-" * 70)

        for _ in range(count):
            person = generate_person(age, gender)
            line = (f"{person['姓名']:<8} {person['性别']:<4} {person['年龄']:<4} "
                    f"{person['出生日期']:<12} {person['身份证号']:<20} {person['手机号']:<12}")
            lines.append(line)

        result = "\n".join(lines)
        print(f"已生成 {count} 条人员信息")
        return result

    def _person_done(self, result):
        if result:
            self._person_result.delete("1.0", "end")
            self._person_result.insert("1.0", result)
        else:
            self._person_result.delete("1.0", "end")
            self._log_result_banner(False)

    def _person_copy(self):
        text = self._person_result.get("1.0", "end-1c")
        if not text:
            self._notify("没有可复制的内容")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._notify("已复制到剪贴板")

    # =============== 页面8: URL编码解码 ===============
    def _show_page_url(self):
        self.title_label.config(text="URL编码解码")
        self._label(self.content, "对文本进行 URL 百分号编码/解码（UTF-8）。").pack(anchor="w", pady=(0, 8))

        tk.Label(self.content, text="输入:", bg="#f5f6fa",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        self._url_input = tk.Text(self.content, height=6, font=("Consolas", 10),
                                  wrap="word", bg="white")
        self._url_input.pack(fill="both", expand=True)

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="编码", command=lambda: self._url_run(True),
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=12).pack(side="left", pady=6)
        tk.Button(btn_row, text="解码", command=lambda: self._url_run(False),
                  bg="#3498db", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=12).pack(side="left", padx=(10, 0))
        tk.Button(btn_row, text="复制结果", command=self._url_copy, width=12).pack(side="left", padx=(10, 0))
        tk.Button(btn_row, text="清空", command=self._url_clear, width=10).pack(side="left", padx=(10, 0))

        tk.Label(self.content, text="结果:", bg="#f5f6fa",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(4, 3))
        self._url_output = tk.Text(self.content, height=6, font=("Consolas", 10),
                                   wrap="word", bg="white")
        self._url_output.pack(fill="both", expand=True)

    def _url_run(self, encode):
        text = self._url_input.get("1.0", "end-1c")
        if not text:
            self._notify("请输入内容")
            return
        self._start_task(self._url_convert, text, encode,
                         on_done=self._url_done)

    def _url_convert(self, text, encode):
        if encode:
            result = url_encode(text)
        else:
            result = url_decode(text)
        print(f"{'编码' if encode else '解码'}完成，{len(text)} -> {len(result)} 字符")
        return result

    def _url_done(self, result):
        if result is None:
            self._log_result_banner(False)
            return
        self._url_output.delete("1.0", "end")
        self._url_output.insert("1.0", result)
        self._log_result_banner(True)

    def _url_copy(self):
        text = self._url_output.get("1.0", "end-1c")
        if not text:
            self._notify("没有可复制的内容")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._notify("已复制到剪贴板")

    def _url_clear(self):
        self._url_input.delete("1.0", "end")
        self._url_output.delete("1.0", "end")

    # =============== 页面9: 接口请求 ===============
    def _show_page_http(self):
        self.title_label.config(text="接口请求")
        self._label(self.content, "发送 GET / POST 请求，查看响应状态、头和内容。").pack(anchor="w", pady=(0, 8))

        r1 = self._row(self.content)
        self._label(r1, "方法:").pack(side="left")
        self._http_method_var = tk.StringVar(value="GET")
        ttk.Combobox(r1, textvariable=self._http_method_var, state="readonly",
                     values=["GET", "POST"], width=6).pack(side="left", padx=(4, 10))
        self._label(r1, "URL:").pack(side="left")
        tk.Entry(r1, textvariable=self._http_url_var).pack(
            side="left", padx=4, fill="x", expand=True)

        tk.Label(self.content, text="请求头 (每行 Key: Value，可空):", bg="#f5f6fa",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(4, 2))
        self._http_headers_text = tk.Text(self.content, height=4, font=("Consolas", 10),
                                          wrap="word", bg="white")
        self._http_headers_text.pack(fill="x")

        tk.Label(self.content, text="请求体 (POST时使用，可空):", bg="#f5f6fa",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(4, 2))
        self._http_body_text = tk.Text(self.content, height=4, font=("Consolas", 10),
                                       wrap="word", bg="white")
        self._http_body_text.pack(fill="x")

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="发送请求", command=self._http_run,
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=14).pack(pady=6)
        tk.Button(btn_row, text="清空响应", command=self._http_clear, width=10).pack(side="left", padx=(10, 0))

        tk.Label(self.content, text="响应:", bg="#f5f6fa",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(4, 3))
        self._http_output = tk.Text(self.content, height=10, font=("Consolas", 10),
                                    wrap="word", bg="white")
        self._http_output.pack(fill="both", expand=True)

    def _http_run(self):
        url = self._http_url_var.get().strip()
        if not url:
            self._notify("请输入URL")
            return
        method = self._http_method_var.get()
        headers_raw = self._http_headers_text.get("1.0", "end-1c")
        body = self._http_body_text.get("1.0", "end-1c").strip() or None
        try:
            headers = parse_headers(headers_raw) if headers_raw else None
        except ValueError as e:
            self._notify(str(e))
            return
        self._start_task(self._http_send, method, url, headers, body,
                         on_done=self._http_done)

    def _http_send(self, method, url, headers, body):
        resp = send_request(method, url, headers=headers, body=body)
        return format_response(resp)

    def _http_done(self, result):
        if result is None:
            self._log_result_banner(False)
            return
        self._http_output.delete("1.0", "end")
        self._http_output.insert("1.0", result)
        self._log_result_banner(True)

    def _http_clear(self):
        self._http_output.delete("1.0", "end")

    # =============== 页面10: JSON格式化 ===============
    def _show_page_json(self):
        self.title_label.config(text="JSON格式化")
        self._label(self.content, "输入 JSON 文本，点击按钮后直接在输入框中原地格式化或压缩。").pack(anchor="w", pady=(0, 8))

        tk.Label(self.content, text="输入:", bg="#f5f6fa",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        self._json_input = tk.Text(self.content, height=16, font=("Consolas", 10),
                                   wrap="word", bg="white")
        self._json_input.pack(fill="both", expand=True)

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="格式化", command=lambda: self._json_run("format"),
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=12).pack(side="left", pady=6)
        tk.Button(btn_row, text="压缩为字符串", command=lambda: self._json_run("compact"),
                  bg="#3498db", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=14).pack(side="left", padx=(10, 0))
        tk.Button(btn_row, text="复制", command=self._json_copy, width=10).pack(side="left", padx=(10, 0))
        tk.Button(btn_row, text="清空", command=self._json_clear, width=8).pack(side="left", padx=(10, 0))

    def _json_run(self, mode):
        text = self._json_input.get("1.0", "end-1c")
        if not text:
            self._notify("请输入JSON内容")
            return
        self._start_task(self._json_convert, text, mode,
                         on_done=self._json_done)

    def _json_convert(self, text, mode):
        if mode == "format":
            result = json_format(text)
        else:
            result = json_compact(text)
        print(f"JSON处理完成（{mode}）")
        return result

    def _json_done(self, result):
        if result is None:
            self._log_result_banner(False)
            return
        self._json_input.delete("1.0", "end")
        self._json_input.insert("1.0", result)
        self._log_result_banner(True)

    def _json_copy(self):
        text = self._json_input.get("1.0", "end-1c")
        if not text:
            self._notify("没有可复制的内容")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._notify("已复制到剪贴板")

    def _json_clear(self):
        self._json_input.delete("1.0", "end")

    # =============== 页面11: JSON对比 ===============
    def _show_page_jsondiff(self):
        self.title_label.config(text="JSON对比")
        self._label(self.content, "点击「排序后对比」：两框 JSON 按统一规则排序，"
                                  "差异行橙色背景，差异字符红色字体。").pack(anchor="w", pady=(0, 8))

        paned = tk.PanedWindow(self.content, orient="horizontal", sashwidth=5,
                               bg="#f5f6fa")
        paned.pack(fill="both", expand=True)

        left = tk.Frame(paned, bg="#f5f6fa")
        tk.Label(left, text="原始JSON:", bg="#f5f6fa",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        self._jd_left = tk.Text(left, font=("Consolas", 10),
                                wrap="word", bg="white")
        self._jd_left.pack(fill="both", expand=True)

        right = tk.Frame(paned, bg="#f5f6fa")
        tk.Label(right, text="对比JSON:", bg="#f5f6fa",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w")
        self._jd_right = tk.Text(right, font=("Consolas", 10),
                                 wrap="word", bg="white")
        self._jd_right.pack(fill="both", expand=True)

        paned.add(left, stretch="always")
        paned.add(right, stretch="always")

        # 输入框内标注标签
        for w in (self._jd_left, self._jd_right):
            w.tag_config("changed_bg", background="#ffeaa7")               # 淡橙色
            w.tag_config("changed_fg", foreground="#d63031",
                         font=("Consolas", 10, "bold"))                    # 红色加粗

        btn_row = self._row(self.content)
        tk.Button(btn_row, text="排序后对比", command=self._jd_compare,
                  bg="#1abc9c", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=14).pack(side="left", pady=6)
        tk.Button(btn_row, text="清空", command=self._jd_clear, width=8).pack(side="left", padx=(10, 0))

    def _jd_compare(self):
        t1 = self._jd_left.get("1.0", "end-1c")
        t2 = self._jd_right.get("1.0", "end-1c")
        if not t1 or not t2:
            self._notify("请输入两段JSON内容")
            return
        # 先校验合法性
        try:
            json.loads(t1)
        except Exception as e:
            self._notify(f"左侧JSON格式错误: {e}")
            return
        try:
            json.loads(t2)
        except Exception as e:
            self._notify(f"右侧JSON格式错误: {e}")
            return
        self._start_task(self._jd_do_compare, t1, t2,
                         on_done=self._jd_done)

    def _jd_do_compare(self, t1, t2):
        s1 = json_sort(t1)
        s2 = json_sort(t2)
        left_spans, right_spans = json_diff_spans(s1, s2)
        print(f"排序完成, 差异标注: 左侧 {len(left_spans)} 处, 右侧 {len(right_spans)} 处")
        return (s1, s2, left_spans, right_spans)

    def _jd_done(self, result):
        if result is None:
            self._log_result_banner(False)
            return
        s1, s2, left_spans, right_spans = result
        # 用排序后的JSON替换两框内容
        self._jd_left.delete("1.0", "end")
        self._jd_left.insert("1.0", s1)
        self._jd_right.delete("1.0", "end")
        self._jd_right.insert("1.0", s2)
        # 清除旧标注后应用新标注
        for w, spans in ((self._jd_left, left_spans), (self._jd_right, right_spans)):
            w.tag_remove("changed_bg", "1.0", "end")
            w.tag_remove("changed_fg", "1.0", "end")
            for (a, b, kind) in spans:
                tag = "changed_bg" if kind == "line" else "changed_fg"
                w.tag_add(tag, f"{a[0]}.{a[1]}", f"{b[0]}.{b[1]}")
        self._log_result_banner(True)

    def _jd_clear(self):
        for w in (self._jd_left, self._jd_right):
            w.delete("1.0", "end")
            w.tag_remove("changed_bg", "1.0", "end")
            w.tag_remove("changed_fg", "1.0", "end")

    # =============== 页面12: 截图识别表格 ===============
    def _show_page_ocr_table(self):
        self.title_label.config(text="截图识别表格")

        self._label(self.content, "点击截图或按快捷键，拖动鼠标框选表格区域，识别后自动显示结果。").pack(anchor="w", pady=(0, 8))

        # 快捷键设置区域
        hotkey_frame = tk.Frame(self.content, bg="#f5f6fa")
        hotkey_frame.pack(fill="x", pady=(0, 8))

        self._label(hotkey_frame, "全局快捷键:").pack(side="left")
        self._ocr_hotkey_entry = tk.Entry(hotkey_frame, textvariable=self._ocr_hotkey_var, width=20)
        self._ocr_hotkey_entry.pack(side="left", padx=8)
        tk.Button(hotkey_frame, text="设置快捷键", command=self._ocr_set_hotkey, width=12).pack(side="left", padx=4)
        self._label(hotkey_frame, "（需重启生效，如 Ctrl+Shift+T）").pack(side="left")

        # 操作按钮区域
        btn_frame = tk.Frame(self.content, bg="#f5f6fa")
        btn_frame.pack(fill="x", pady=(0, 8))

        tk.Button(btn_frame, text="截图", command=self._ocr_capture,
                  bg="#3498db", fg="white",
                  font=("Microsoft YaHei UI", 11, "bold"), width=12).pack(side="left", padx=4)
        tk.Button(btn_frame, text="选择图片文件", command=self._ocr_select_file, width=14).pack(side="left", padx=4)

        # 识别结果表格区域
        result_label = tk.Label(self.content, text="识别结果:", bg="#f5f6fa",
                                 font=("Microsoft YaHei UI", 10, "bold"))
        result_label.pack(anchor="w", pady=(0, 4))

        # 表格容器（带滚动条）
        table_container = tk.Frame(self.content, bg="#f5f6fa")
        table_container.pack(fill="both", expand=True)

        self._ocr_tree_scroll_y = tk.Scrollbar(table_container, orient="vertical")
        self._ocr_tree_scroll_y.pack(side="right", fill="y")

        self._ocr_tree_scroll_x = tk.Scrollbar(table_container, orient="horizontal")
        self._ocr_tree_scroll_x.pack(side="bottom", fill="x")

        self._ocr_tree = ttk.Treeview(
            table_container,
            yscrollcommand=self._ocr_tree_scroll_y.set,
            xscrollcommand=self._ocr_tree_scroll_x.set
        )
        self._ocr_tree.pack(fill="both", expand=True)

        self._ocr_tree_scroll_y.config(command=self._ocr_tree.yview)
        self._ocr_tree_scroll_x.config(command=self._ocr_tree.xview)

        # 底部操作按钮
        bottom_frame = tk.Frame(self.content, bg="#f5f6fa")
        bottom_frame.pack(fill="x", pady=(8, 0))

        tk.Button(bottom_frame, text="复制全部到剪贴板", command=self._ocr_copy,
                  bg="#e67e22", fg="white",
                  font=("Microsoft YaHei UI", 10, "bold"), width=18).pack(side="left", padx=4)
        tk.Button(bottom_frame, text="导出Excel文件", command=self._ocr_export_excel, width=14).pack(side="left", padx=4)
        tk.Button(bottom_frame, text="清空", command=self._ocr_clear, width=10).pack(side="left", padx=4)

        # 初始化快捷键监听
        self._init_ocr_hotkey()

    def _ocr_set_hotkey(self):
        """设置快捷键"""
        hotkey = self._ocr_hotkey_var.get().strip()
        if not hotkey:
            messagebox.showwarning("提示", "请输入快捷键组合")
            return
        # 保存到配置文件（简单实现）
        config_path = os.path.join(os.path.dirname(__file__), ".ocr_hotkey")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(hotkey)
            messagebox.showinfo("提示", f"快捷键已设置为: {hotkey}\n需要重启程序生效")
        except Exception as e:
            messagebox.showerror("错误", f"保存快捷键失败: {e}")

    def _load_ocr_hotkey(self):
        """加载保存的快捷键"""
        config_path = os.path.join(os.path.dirname(__file__), ".ocr_hotkey")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except:
                pass
        return "Ctrl+Shift+T"

    def _init_ocr_hotkey(self):
        """初始化全局快捷键监听"""
        try:
            from pynput import keyboard

            hotkey_str = self._load_ocr_hotkey()
            self._ocr_hotkey_var.set(hotkey_str)

            # 解析快捷键
            key_map = {
                "ctrl": "<ctrl>", "control": "<ctrl>",
                "shift": "<shift>",
                "alt": "<alt>",
                "t": "t", "T": "T",
            }

            # 转换快捷键格式
            keys = hotkey_str.split("+")
            pynput_keys = []
            for key in keys:
                key_lower = key.strip().lower()
                if key_lower in key_map:
                    pynput_keys.append(key_map[key_lower])
                elif len(key.strip()) == 1:
                    pynput_keys.append(f"<{key.strip().lower()}>")
                else:
                    pynput_keys.append(f"<{key.strip().lower()}>")

            hotkey_combo = "+".join(pynput_keys)

            def on_activate():
                self.after(0, self._ocr_capture)

            self._ocr_listener = keyboard.GlobalHotKeys({hotkey_combo: on_activate})
            self._ocr_listener.daemon = True
            self._ocr_listener.start()

        except ImportError:
            self._log("提示: 安装 pynput 可启用全局快捷键 (pip install pynput)\n")
        except Exception as e:
            self._log(f"快捷键设置失败: {e}\n")

    def _ocr_capture(self):
        """截图功能"""
        # 隐藏主窗口
        self.withdraw()
        self.update()
        import time
        time.sleep(0.2)

        def on_region_selected(image):
            # 恢复主窗口
            self.deiconify()
            self.update()

            if image is None:
                return

            self._ocr_image = image
            self._log("截图完成，正在识别表格...\n")
            self._start_task(self._ocr_do_recognize, image,
                             on_done=self._ocr_on_recognize_done)

        capture_region(parent=self, callback=on_region_selected)

    def _ocr_select_file(self):
        """选择图片文件"""
        f = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.gif")]
        )
        if f:
            try:
                image = Image.open(f)
                self._ocr_image = image
                self._log(f"已加载图片: {os.path.basename(f)}，正在识别表格...\n")
                self._start_task(self._ocr_do_recognize, image,
                                 on_done=self._ocr_on_recognize_done)
            except Exception as e:
                messagebox.showerror("错误", f"打开图片失败: {e}")

    def _ocr_do_recognize(self, image):
        """执行表格识别（在后台线程中运行）"""
        table_data, html = recognize_table(image)
        return table_data

    def _ocr_on_recognize_done(self, result):
        """识别完成回调"""
        if result is None:
            self._log("识别失败或未识别到表格\n")
            return

        self._ocr_table_data = result

        if not result:
            self._log("未识别到表格内容\n")
            return

        # 更新Treeview
        self._ocr_update_tree(result)
        self._log(f"识别完成，共 {len(result)} 行\n")

    def _ocr_update_tree(self, table_data):
        """更新Treeview表格显示"""
        # 清空旧数据
        self._ocr_tree.delete(*self._ocr_tree.get_children())

        if not table_data:
            return

        # 设置列（使用第一行作为列标题）
        headers = table_data[0] if table_data else []
        col_count = len(headers) if headers else 0

        if col_count == 0:
            return

        # 配置列
        self._ocr_tree["columns"] = [f"col{i}" for i in range(col_count)]
        self._ocr_tree["show"] = "headings"

        for i, header in enumerate(headers):
            col_id = f"col{i}"
            self._ocr_tree.heading(col_id, text=header, anchor="w")
            self._ocr_tree.column(col_id, width=120, minwidth=80, anchor="w")

        # 插入数据行（跳过第一行表头）
        for row in table_data[1:]:
            # 确保每行列数一致
            values = row + [""] * (col_count - len(row))
            values = values[:col_count]
            self._ocr_tree.insert("", "end", values=values)

    def _ocr_copy(self):
        """复制表格到剪贴板"""
        if not self._ocr_table_data:
            self._notify("没有可复制的数据")
            return

        tsv = table_data_to_tsv(self._ocr_table_data)
        self.clipboard_clear()
        self.clipboard_append(tsv)
        self._notify("已复制到剪贴板，可直接粘贴到Excel")

    def _ocr_export_excel(self):
        """导出为Excel文件"""
        if not self._ocr_table_data:
            self._notify("没有可导出的数据")
            return

        try:
            import openpyxl
        except ImportError:
            # 如果没有openpyxl，生成CSV文件
            return self._ocr_export_csv()

        f = filedialog.asksaveasfilename(
            title="导出Excel文件",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )
        if not f:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "识别结果"

            for row in self._ocr_table_data:
                ws.append(row)

            wb.save(f)
            self._log(f"已导出Excel: {f}\n")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")

    def _ocr_export_csv(self):
        """导出为CSV文件（备选方案）"""
        f = filedialog.asksaveasfilename(
            title="导出CSV文件",
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not f:
            return

        try:
            import csv
            with open(f, "w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.writer(csvfile)
                for row in self._ocr_table_data:
                    writer.writerow(row)
            self._log(f"已导出CSV: {f}\n")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")

    def _ocr_clear(self):
        """清空数据"""
        self._ocr_table_data = []
        self._ocr_image = None
        self._ocr_tree.delete(*self._ocr_tree.get_children())

    # =============== 页面13: 关于 ===============
    def _show_page_about(self):
        self.title_label.config(text="关于")
        info = (
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "功能列表:\n"
            "  1. 图片转 PDF - 将多张图片合并为一个PDF\n"
            "  2. 图片批量转 ZIP - 每张图片单独转PDF并打包为ZIP\n"
            "  3. 文件分割 - 按大小分割为多个ZIP\n"
            "  4. 文件合并 - 还原分割的ZIP文件\n"
            "  5. 生成指定大小文件 - 生成任意大小和格式的文件\n"
            "  6. 生成指定长度文本 - 生成指定长度类型的随机文本\n"
            "  7. 随机人员信息 - 生成随机身份证号、姓名、手机号等\n"
            "  8. URL编码解码 - 文本的URL百分号编码与解码\n"
            "  9. 接口请求 - 发送GET/POST请求查看响应\n"
            "  10. JSON格式化 - JSON美化/压缩为字符串\n"
            "  11. JSON对比 - 排序后逐字符对比，标注差异\n"
            "  12. 截图识别表格 - 截图识别表格并导出到Excel\n\n"
            "使用方法:\n"
            "  左侧选择功能，右侧填写参数后点击开始按钮。\n"
        )
        lbl = tk.Label(self.content, text=info, bg="#f5f6fa", fg="#2c3e50",
                       font=("Microsoft YaHei UI", 11), justify="left", anchor="w")
        lbl.pack(anchor="nw", pady=(10, 0))

    # ---------------- 退出 ----------------
    def _on_close(self):
        if self._running:
            if not messagebox.askyesno("退出", "有任务正在运行，确定退出吗？"):
                return
        # 停止快捷键监听
        if self._ocr_listener:
            try:
                self._ocr_listener.stop()
            except:
                pass
        self.destroy()


def main():
    app = ToolboxApp()
    app.mainloop()


if __name__ == "__main__":
    main()
