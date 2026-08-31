# Bug 清单（已全部修复 ✅ 2026-08-30）

## 修复 ✅ 点击任意菜单弹出空白 "tk" 窗口（2026-08-31）
- **根因**：`main()` 中启动加载窗 `_create_loading_window()`（`tk.Tk()`）先于主窗口创建，成为 tkinter 默认根窗口；被 `_close_loading_window` 销毁后默认根失效。此后页面构建中不带 master 的 `tk.StringVar` / `messagebox` 调用触发 `_get_default_root()`，隐式新建空白 `Tk()`（标题 "tk"），部分页面还抛 "Too early to create variable: no default root window"（见 page_build_error.log / http_page_build_error.log）
- **修复**：`main()` 中在销毁加载窗后显式执行 `tk._default_root = app`，把默认根窗口指回主窗口
- **修复（2026-08-31 补充，彻底版）**：仅修 main() 末尾不够——`ToolboxApp.__init__` 里的 `IntVar/StringVar`（`_pdf_out_var` 等持久化变量）在创建时仍挂在加载窗上，加载窗销毁后全部失效，导致所有功能页按钮消失。现已在 `ToolboxApp.__init__` 的 `super().__init__()` 后立即执行 `tk._default_root = self`，确保全部变量注册在主窗口上
- **待办**：重新用 PyInstaller 打包 exe（当前 dist/TestToolbox.exe 为旧版）

## 修复 ✅ 生成页重复路径行 + 功能页日志降噪（2026-08-30 第五轮）
- **重复的"输出路径/开始生成"行**：根因是页面构建中途抛异常（如之前的 r4 NameError）后，半成品 frame 被缓存，重进菜单时控件叠加。修复：页面切换改为每次进入都新建 frame 并整体重建（旧缓存引用被覆盖），不会再出现重复控件
- **功能页日志降噪**：`_save_current_log` 保存页面日志时过滤 [构建]/迁移/storage/加载/初始化/[启动] 类启动信息，各功能页只显示对应菜单操作的日志；完整记录仍可在"关于"页后台日志查看

## 新增功能 ✅ 损坏方式悬浮说明（2026-08-30 第四轮）
- "生成指定大小文件"的损坏方式下拉框：鼠标悬停时弹出浅黄色悬浮提示，显示当前选中方式的英文标识 + 中文释义（如 header_tail = 覆盖头部和尾部：用随机数据改写文件开头和结尾各约4KB…）
- **选中后常显说明**：选中某个损坏方式后，下拉框右侧直接以灰色小字显示该方式的中文简述（取释义冒号前的短语），切换选项即时更新
- 切换"正常/损坏"时说明标签随下拉框一起显隐；7 种损坏方式全部配有中文解释

## UI 调整 ✅ 补充（2026-08-30 第三轮）
- 窗口缩小时表格页"添加/删除"按钮被挤出可视区：原因是表格先 pack 且 expand 占满，按钮栏后 pack 被压缩。修复：按钮栏 pack 加 `before=tree`，布局器优先保留按钮空间，缩小窗口时只压缩表格区域（请求头/请求体两处均已修复）

## UI 调整 ✅ 接口请求页（2026-08-30 第二轮）
- header/body 改为水平 PanedWindow：默认各占一半，拖动中间分隔条可手动调节宽度
- 标签页配色改用 clam 主题（Windows 默认 vista 主题会忽略 Tab 颜色配置）：选中=蓝底白字，未选中=灰底黑字
- 表格"添加/删除"按钮改为横向并排、随宽度自适应拉伸


## 新增功能 ✅ 后台日志查看（关于页）
- "关于"页面下方新增后台日志区：记录从启动到当前的所有日志（含页面日志、提示、任务输出、进度行）
- 日志级别可调：DEBUG / INFO / WARNING / ERROR 下拉框，默认 INFO，切换后点"刷新"生效
- 支持刷新 / 清空 / 导出为 .log 文件；缓冲上限 5000 条，超出自动淘汰最旧的

> BUG-01 根因：`My.Notebook` 样式名不符合 ttk 派生规则（ttk 要求样式名从内置控件样式派生，如 `TNotebook`），创建 Notebook 时抛 `Layout My.Notebook not found`，导致页面构建在请求头区中断，后续请求体、cURL 导入区全部消失。修复：5 处统一改名为 `My.TNotebook`。

> 探索范围：`toolbox.py`、`http_client.py`（静态走查 + 依赖核对；沙箱无 X 显示，未实际运行 GUI 复现）
> 状态：仅列清单，未做任何修复，等待确认。

## BUG-01 接口请求页：headers / body 输入框与"导入接口"输入框、按钮不显示（已知问题，待复现确认）
- 位置：`toolbox.py` `_show_page_http()`（约 2332–2469 行）
- 现象：界面缺少"请求头"文本框、"请求体"文本框、cURL 导入输入框和"导入接口"按钮
- 代码走查结论：这些控件在代码中**均已创建**（`_http_headers_text`、`_http_body_text`、`_curl_text`、导入按钮都在），且所依赖的方法（`_notify`/`_start_task`/`_sync_text_to_tree` 等）都存在，语法编译通过
- 疑似原因（按可能性排序）：
  1. 页面构建中途抛异常导致后续控件未渲染（需在目标机器上运行抓异常确认）
  2. 正在运行的是旧版打包 exe，未包含最新代码（建议重新打包验证）
  3. PanedWindow 请求区（`req_frame`，minsize=120）在特定窗口尺寸下被压缩为 0 高，输入框被挤到不可见
- 修复方向：先在真实环境复现抓异常；再检查 PanedWindow 尺寸分配，必要时给请求区设固定初始高度

## BUG-02 `_sync_tree_to_text` 中残留调试性 `item.text()` 判断
- 位置：`toolbox.py` 2545 行
- 问题：`item` 是 Treeview 子项 id（字符串），`hasattr(item, 'text')` 恒为 False，属于冗余/误导代码
- 影响：当前不致错，但影响可读性，易在后续改动中引入 bug

## BUG-03 cURL 导入解析不健壮
- 位置：`toolbox.py` `_import_curl()`（2551–2603 行）
- 问题：
  1. `-H` 请求头正则 `(?=\s|$)` 无法处理值内含引号转义的情况，含空格的 User-Agent 截断风险
  2. body 解析只取最后一个 `-d`，多个 `-d` 拼接场景（curl 多段 data）会丢失数据
  3. URL 未包含在引号中且后面紧跟参数时可能把参数并入 URL（`(https?://\S+)` 贪婪匹配，会把 `url -H` 之间内容截进，虽然 `\S+` 遇空格会停，但 `url?x=1'` 类尾随引号会带入）
- 影响：导入结果错误或解析失败（当前有 try/except 兜底提示，不至于崩溃）

## BUG-04 请求头格式错误提示体验差
- 位置：`http_client.py` `parse_headers()` + `toolbox.py` `_http_run()`
- 问题：headers 文本中只要有一行不含 `:` 就整体报错拒发；且 URL 中的 `https://` 若被用户误粘成多行也会报"请求头格式错误"
- 建议：按行报错并指出行号，或忽略空/非法行前先确认

## BUG-05 POST 默认 Content-Type 硬编码
- 位置：`http_client.py` `send_request()` 47–48 行
- 问题：body 非 JSON 时会强制加 `application/x-www-form-urlencoded`，发 JSON 时若用户忘了手动加 Content-Type 会被服务端误解
- 建议：body 以 `{`/`[` 开头时默认 `application/json`

## BUG-06 发送请求超时固定 15 秒且无界面提示
- 位置：`http_client.py` `send_request(timeout=15)`；`_http_run()` 未暴露超时设置
- 问题：慢接口会被强制中断且用户看不到明确的超时原因区分（需要确认 `_start_task` 的异常上报路径是否把 `URLError: timed out` 转成友好提示）

## BUG-07 接口请求页响应区无滚动联动/字体统一问题（低优先级）
- 位置：`_show_page_http()` 响应区 Text 控件
- 问题：响应 body 很大时直接全部插入 Text，无上限保护，可能卡 UI；响应头与响应体分页展示但"原始"页也重复包含全部内容
- 建议：加长度上限或异步分块插入

---

## 修复优先级建议（供确认）
| 编号 | 严重度 | 建议 |
|------|--------|------|
| BUG-01 | 高（功能不可用） | 优先复现并修 |
| BUG-03 | 中 | 建议修 |
| BUG-05、BUG-04 | 中低 | 可一并修 |
| BUG-06、BUG-07 | 低 | 视需求 |
| BUG-02 | 代码清理 | 顺手修 |

请确认要修复哪些编号，我再动手。
