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

---

# Bug 清单（第二轮探索 2026-09-04，仅列清单与修复方案，未做任何修改 ✅）

> **修复状态（2026-09-04 修复轮）**：BUG-08、BUG-09、BUG-10、BUG-15、BUG-18 已修复 ✅（最小侵入，不改行为）；BUG-16 经评估保留原正则（完整引号分支替换需回归验证，仅加注释说明边缘场景，避免引入回归）；BUG-11、BUG-12、BUG-13、BUG-14、BUG-17 待用户确认预期后再定；BUG-19 暂保留现有 hack（注释级建议）。4 个改动文件已通过 py_compile 编译验证。

## 新增修复（2026-09-04）
- **build.bat 模型路径修复** ✅：第20行检查的路径从 `SLANet_plus_infer` 改为 `SLANet_plus`，与 `download_models.py` 和 `build.ps1` 保持一致

> 探索范围：`toolbox.py`、`http_client.py`、`image_to_pdf.py`、`file_splitter.py`、`generate_file.py`、`generate_person.py`、`generate_text.py`、`json_fmt.py`、`url_codec.py`、`zip_encoder.py`（静态走查；沙箱无显示环境，未实际运行 GUI）
> 修复原则：不做质量降低/破坏性修复，全部为最小侵入式方案，不影响原功能；确认后再动手。

## BUG-08 文件合并 `merge_zip_files` 将全部数据一次性载入内存
- 位置：`file_splitter.py` `merge_zip_files()`（约 127–161 行）
- 问题：`all_data[part_num] = zipf.read(name)` 把所有分片全部读入内存，最后 `merged_data += ...` 又完整复制一份；合并 GB 级文件时内存占用为文件体积的 2 倍以上，可能 OOM/卡死。
- 修复方案（非破坏性）：改为流式合并——按 part_num 排序后逐个 `zipf.open(name)` 并以 1MB 块写入输出文件；原返回值/日志行为不变。

## BUG-09 定时器日志无节流，`_check_timer` 每 2 秒写一条日志
- 位置：`toolbox.py` `_check_timer()`（约 2598 行）：每次轮询都 `self._timer_log(f"检查: now=...")`，`timer_log.txt` 已 76KB 且随运行时间无限增长；弹窗未弹时靠该日志排查，但日常运行膨胀明显。
- 修复方案：仅在"分钟值变化"或有提醒/关机任务激活时记录检查日志；或把"检查"类日志降为 DEBUG 级别并给 timer_log 加轮转上限（如 2MB 截断保留后半）。行为（弹窗触发）完全不变。

## BUG-10 `_timer_match` 的"错过补偿"在跨小时/跨天场景会误触发或漏触发（低概率）
- 位置：`toolbox.py` `_timer_match()`（约 2624 行）
- 问题：补偿窗口用 `now.replace(hour=h, minute=m)` 计算目标时刻，若系统休眠跨过"次日凌晨 0 点后补前一天"或目标时刻在 23:5x 且 now 已跨天，`delta` 计算基于"今天的 h:m"，会得到负 delta → 漏触发；反之"仅一次"提醒跨天后 delta 又恰好落 0~120 秒内时，用的是新一天的日期 key，`_last_fired` 去重失效可能重复弹。
- 修复方案：补偿判断改为"目标时刻 = 与 now 最接近的过去一次 h:m（含昨天）"，即 `delta = (now - target)` 若为负则 target 减一天再算；`_last_fired` 去重 key 加入目标日期。逻辑替换为等价更严格版本，不影响正常到点触发。

## BUG-11 `corrupt_file` 的 `header_tail`/`tail_only` 在文件较小（<8KB）时首尾覆盖重叠（低危）
- 位置：`generate_file.py` `corrupt_file()`（约 66–88 行）：`region = min(4096, total // 2)`，total<8KB 时 head 和 tail 覆盖区间相接甚至重叠，仅提示语不准，功能仍是"损坏"。属行为瑕疵非错误。
- 修复方案：total <= 2*region 时提示"文件过小，头尾覆盖已合并"；或 head 写完后先 `f.seek(total - region)`（当前 header_tail 分支第二段已有 seek，无实际错位，仅文档/提示完善）。可保持现状仅改提示。

## BUG-12 `generate_file.create_image_file` 对大尺寸目标的估算偏差（低危）
- 位置：`generate_file.py` 约 186 行：`approx_pixels = target_size * 0.9 / 3` 后直接 `f.write(header)` 再补随机数据到目标大小——实际产物是"有效图片头 + 尾部随机垃圾"，大多数查看器能打开但 PIL 完整解码可能报错，且 PNG/JPG 尾部数据并非图像内容。
- 修复方案：如果"可用图片查看器正常打开"是硬需求，改为生成多帧/放大真实像素直到达到目标体积（重写编码循环）；若当前"能打开即可"是预期，可不动。需用户确认预期后选择。

## BUG-13 `zip_encoder.verify_archive_names` 对 zip 的 cp437 解码假设不完整
- 位置：`zip_encoder.py` `verify_archive_names()`（约 39 行）：只有当 zip 内文件名被以 UTF-8 flag=0（cp437 存储）写入时 `filename.encode('cp437').decode(encoding)` 才成立；若原 zip 已带 UTF-8 flag 或名字含非 cp437 可编码字符，`encode('cp437')` 抛异常走 fallback 返回原名——行为尚可，但 `_encode_name` 侧（`encode(encoding).decode('utf-8')`）生成的文件名在某些解压器中会乱码（Windows 资源管理器按 cp437/系统 ANSI 解）。
- 修复方案：写入时给 `zf.write(..., arcname=...)` 前将 arcname 以 latin-1/cp437 可逆方式编码（Python zipfile 若 arcname 非 ASCII 会自动置 UTF-8 flag，需改用 `ZipInfo` 手工设 flag_bits 去 UTF-8 标志）；或界面上注明"GBK 压缩包请用 WinRAR/Bandizip 等按 ANSI 解码"。方案一为真修，需回归验证 GBK 解压。

## BUG-14 `url_codec.url_decode` 对 `+` 不做空格还原（待确认是否有意）
- 位置：`url_codec.py` 15–19 行：`unquote(text, errors="strict")` 保留 `+` 为字面加号。标准 query-string 解码中 `+` 代表空格；若界面用于解码表单/查询串，结果与用户预期不符。
- 修复方案：新增可选参数 `plus_as_space=False` 保持默认行为不变，界面加"将 + 视为空格"勾选项（默认不勾，兼容原功能）。属增强非必改。

## BUG-15 `http_client.send_request` 未处理 gzip/deflate 响应解压
- 位置：`http_client.py` 约 60–84 行：请求不带 `Accept-Encoding`，但若服务端/代理仍返回 gzip（如用户手动在头里加了 `Accept-Encoding: gzip`），`raw.decode` 会输出乱码。
- 修复方案：当响应头 `Content-Encoding` 为 gzip/deflate 时用 `gzip`/`zlib` 解压后再解码；无该头时行为不变。

## BUG-16 `_import_curl` 对带转义引号的头值解析仍不健壮（BUG-03 残留）
- 位置：`toolbox.py` `_import_curl()`（约 3665 行）`-(?:H|header)\s+(['\"]?)(.*?)\1(?=\s|$)`：非贪婪 `.*?` 遇到值内 `\"` 会提前截断（如 `curl -H "Authorization: Bearer a\"b"`）。多 `-d` 已修（body_parts），此项为剩余边缘场景。
- 修复方案：引号组改为完整的单/双引号分支正则：`-(?:H|header)\s+(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|(\S+))`，并对引号内做 `\"` → `"` 还原。仅影响导入解析，不影响手填请求头路径。

## BUG-17 `image_to_pdf.py` 递归模式下 GIF 动图取第一帧（待确认预期）
- 位置：`image_to_pdf.py` 54/109 行：`Image.open` 后直接 convert('RGB') 保存，动图 GIF 只保留第一帧，多帧信息静默丢失。若产品定位"静态图合并"可接受，属预期说明问题。
- 修复方案：文档/界面注明"动图取第一帧"；或在转换日志中加一条"GIF 为动图，已取第一帧"的提示（不改结果）。

## BUG-18 `merge_images_to_pdf` 打开的图片对象未统一关闭（资源泄漏，低危）
- 位置：`image_to_pdf.py` 107–125 行：图片列表在 `save()` 后未 `close()`/用 with 管理；长会话批量转换会累积文件句柄（Windows 下还可能锁定原文件句柄直到 GC）。
- 修复方案：保存完成后 `finally` 中逐个 `img.close()`（Pillow 的 close 释放文件句柄，不影响已写入的 PDF）；convert_images_to_zip 分支已有 img.close()，对齐即可。

## BUG-19 `tk._default_root = app` 使用私有属性（兼容性风险，前轮修复的遗留）
- 位置：`toolbox.py` `ToolboxApp.__init__` / `main()`：直接赋值 `tk._default_root` 是 CPython 私有实现细节，Python 3.11+ 中 `_support_default_root` 机制未变但无公开契约，未来版本升级可能失效。
- 修复方案（渐进，不影响现状）：根因修法是把加载窗改为 `Toplevel(master)` 挂在主窗下，或所有 `IntVar/StringVar/messagebox` 显式传 master；属重构项，建议保留现有 hack 的同时在该行加注释标注 Python 版本依赖，待有窗口期再做结构性修复。

## 第二轮修复优先级建议
| 编号 | 严重度 | 建议 |
|------|--------|------|
| BUG-08 | 中高（大文件 OOM） | 建议修 |
| BUG-09 | 中（日志膨胀） | 建议修 |
| BUG-10 | 中低 | 可修 |
| BUG-16、BUG-15 | 中低 | 可一并修 |
| BUG-13、BUG-14、BUG-17 | 低 | 视需求，需先确认预期 |
| BUG-11、BUG-12、BUG-18 | 低 | 顺手修 |
| BUG-19 | 代码健康 | 暂保留，加注释 |

确认要修复的编号后我再动手。
