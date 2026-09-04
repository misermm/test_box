# 测试工具箱 (Test Toolbox)

一个功能丰富的 Windows 桌面工具集，提供文件处理、数据生成、开发工具、安全测试等多种实用功能。

## 功能列表

### 文件处理
1. **图片转 PDF** - 将多张图片合并为一个PDF文件，支持常见图片格式（JPG, PNG, BMP, TIFF, GIF等）
2. **图片批量转 ZIP** - 每张图片单独转PDF并打包为ZIP文件
3. **文件分割** - 按指定大小将文件分割为多个ZIP文件
4. **文件合并** - 还原分割的ZIP文件为原始文件
5. **按编码生成压缩包** - 生成ZIP编码压缩包

### 数据生成
6. **生成指定大小文件** - 生成任意大小的ZIP或普通文件
7. **生成指定长度文本** - 生成指定长度类型的随机文本
8. **随机人员信息** - 生成随机身份证号、姓名、手机号等人员信息

### 开发工具
9. **URL编码解码** - 文本的URL百分号编码与解码
10. **接口请求** - 发送GET/POST请求查看响应
11. **JSON格式化** - JSON美化/压缩为字符串
12. **JSON对比** - 排序后逐字符对比，标注差异

### 常用工具
13. **截图识别表格** - 截图识别表格并导出到Excel（使用PP-OCR本地离线模型）
14. **定时工具** - 定时提醒和关机功能

### 安全测试
15. **数据注入** - SQL/XSS/命令/LDAP/NoSQL注入测试代码生成

## 特性

- 🖥️ 现代化GUI界面，支持字体缩放
- 📁 便携式设计，所有配置和数据存储在程序目录
- 🔒 本地离线OCR识别，无需联网
- ⌨️ 全局快捷键支持（截图识别）
- 📊 支持导出Excel/CSV格式
- 🎯 精确的文件大小控制
- 🔄 自动模型更新检查

## 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- Pillow - 图片处理
- openpyxl - Excel文件操作
- requests - HTTP请求
- pynput - 全局快捷键监听
- paddlex - 表格识别（可选）

## 使用方法

### 直接运行

```bash
# 运行主程序
python toolbox.py

# 运行自检
python toolbox.py --selftest
```

### 打包为EXE

```bash
# 使用PyInstaller打包
python -m PyInstaller TestToolbox.spec
```

## 项目结构

```
picture_to_pdf/
├── toolbox.py           # 主程序（GUI界面）
├── image_to_pdf.py      # 图片转PDF脚本
├── file_splitter.py     # 文件分割脚本
├── generate_file.py     # 生成指定大小文件脚本
├── generate_text.py     # 生成指定长度文本脚本
├── generate_person.py   # 随机人员信息脚本
├── url_codec.py         # URL编码解码脚本
├── http_client.py       # 接口请求脚本
├── json_fmt.py          # JSON格式化脚本
├── zip_encoder.py       # ZIP编码压缩包脚本
├── download_models.py   # 模型下载脚本
├── requirements.txt     # Python依赖列表
├── TestToolbox.spec     # PyInstaller打包配置
├── build.bat            # Windows打包脚本
├── build.ps1            # PowerShell打包脚本
├── icon.ico             # 程序图标
├── splash.png           # 启动画面
├── version.txt          # 版本信息
├── README.md            # 使用说明
└── models/              # OCR模型目录（预下载，不入git）
```

## 快速开始

### 1. 图片转PDF

```bash
# 命令行方式
python image_to_pdf.py image1.jpg image2.png -o output.pdf

# GUI方式
python toolbox.py
# 在界面中选择"图片转PDF"，添加图片后点击"开始"
```

### 2. 文件分割

```bash
# 将PDF分割成101MB的ZIP文件
python file_splitter.py split document.pdf -s 101 -o output/

# 合并ZIP文件
python file_splitter.py merge output/part_*.zip -o restored.pdf
```

### 3. 生成测试文件

```bash
# 生成101MB的ZIP文件
python generate_file.py -s 101 -o test.zip

# 生成50MB的普通文件
python generate_file.py -s 50 -o test.bin -t plain
```

## 配置说明

程序配置存储在以下位置（按优先级）：

1. **程序目录/cache/** - 默认存储位置（便携模式）
2. **用户自定义位置** - 可在设置中更改
3. **旧版位置** - `%LOCALAPPDATA%\TestToolbox`（自动迁移）

配置文件包括：
- `.ocr_model` - OCR模型选择
- `.ocr_hotkey` - 全局快捷键设置
- `.storage_dir` - 存储位置配置
- `setting_*` - 各功能页面的设置

## 注意事项

1. **图片处理**：图片将按添加顺序排列，自动转换为RGB模式确保兼容性
2. **文件分割**：使用DEFLATE压缩算法，支持中文文件名
3. **OCR识别**：首次使用会自动下载模型（约100MB），之后离线可用
4. **定时提醒**：程序关闭后提醒会失效，需保持程序运行
5. **存储位置**：更改存储位置会自动迁移已有文件

## 开发说明

### 模型管理

- 模型预下载在 `models/` 目录（不入git）
- 运行时通过 `PADDLE_PDX_CACHE_HOME` 环境变量选择模型目录
- 启动时后台检查模型更新（需联网）

### 构建打包

- 使用项目本地虚拟环境 `.venv` 进行打包
- 构建配置在 `TestToolbox.spec` 文件中
- 产物：`dist/TestToolbox.exe`（约250MB）

## 许可证

本项目仅供学习和研究使用。