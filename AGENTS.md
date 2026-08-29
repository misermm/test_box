# AGENTS.md

## 构建规则

- 使用项目本地虚拟环境 `.venv` 进行打包
- 每次修改代码后都必须重新打包 exe（用户要求，必须遵守）：

```powershell
.venv\Scripts\python.exe -m PyInstaller --onefile --noconsole --name "TestToolbox" `
  --collect-all PIL `
  --collect-all cv2 `
  --collect-all paddle `
  --collect-all pyclipper `
  --collect-all shapely `
  --collect-all paddlex `
  --add-data ".venv\Lib\site-packages\paddle\libs;paddle\libs" `
  --add-data "models;models" `
  toolbox.py
```

- 打包后清理临时文件：删除 `build/` 目录和 `*.spec` 文件
- 产物：`dist/TestToolbox.exe`（单文件可直接运行，约 250MB，模型已内置）
- 表格识别使用本地离线模型：模型预下载在项目 `models/` 目录（不入 git），
  经 `--add-data "models;models"` 打包进 exe；运行时通过环境变量
  `PADDLE_PDX_CACHE_HOME` 选择模型目录（优先存储位置 `<存储位置>\models`
  中自动检查更新下载的模型，否则用 exe 内置模型），识别不联网。
  启动时后台向 BOS（百度 CDN）HEAD 检查模型 ETag，有更新则下载到上述外部目录
  （下次启动生效）；检查/下载失败仅日志提示，继续用本地模型。
- 文件存储位置（`toolbox.py` 的 `_STORAGE_DIR`）：模型、日志、配置文件的
  存放根目录，默认 exe 所在目录（便携式）；OCR 页
  "文件存储位置"可更改（持久化在 exe 同级 `.storage_dir`，仅此一个文件
  在 exe 旁，因为它决定存储位置本身），更改后自动把已有文件迁移到新位置
  并立即生效（模型目录先复制后删除，日志复制，配置文件移动）。
  迁移期间禁止模型下载与新的识别任务，防止文件被误删。
  旧版默认位置 `%LOCALAPPDATA%\TestToolbox` 的数据在 exe 首次启动时由
  `_migrate_legacy_storage` 一次性迁移（模型合并复制保留可选模型，配置/
  日志移动，完成后删除旧目录释放 C 盘；仅未自定义存储位置时执行）。
- 配置文件统一存放在存储位置（`_read_config`/`_write_config`）：
  `.ocr_model`（识别模型选择）、`.ocr_hotkey`（全局快捷键）。
  读取兼容旧版 exe 同级位置：读到旧文件自动迁移到存储位置并删除旧文件。
- OCR 引擎界面可切换（`toolbox.py` 的 `_OCR_MODEL_OPTIONS`）：默认
  PP-OCRv5 mobile 随 exe 内置；v5 server / v4 等可选模型按需联网下载到
  `<存储位置>\models`（持久保存，之后离线可用），选择持久化
  在 `<存储位置>\.ocr_model`。切换通过 `model_dir` 显式路径加载，不打包进 exe
  （否则体积涨回 500MB+）。更新清理逻辑用 `_ALL_KNOWN_MODELS` 白名单，
  不会误删已下载的可选模型。

## 自动维护规则

- 每次打包命令有变动时，必须同步更新 `build.bat` 和 `build.ps1` 中的打包命令
- 每次 AGENTS.md、build.bat、build.ps1、.gitignore 有变动时，必须自动提交 git（无需用户确认）
- 每次代码变动（toolbox.py 等）完成修改后，必须自动提交 git（无需用户确认）
