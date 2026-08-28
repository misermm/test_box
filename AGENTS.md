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
- 产物：`dist/TestToolbox.exe`（单文件可直接运行，约 500MB，模型已内置）
- 表格识别使用本地离线模型：模型预下载在项目 `models/` 目录（不入 git），
  经 `--add-data "models;models"` 打包进 exe；运行时通过环境变量
  `PADDLE_PDX_CACHE_HOME` 选择模型目录（优先 `%LOCALAPPDATA%\TestToolbox\models`
  中自动检查更新下载的模型，否则用 exe 内置模型），识别不联网。
  启动时后台向 BOS（百度 CDN）HEAD 检查模型 ETag，有更新则下载到上述外部目录
  （下次启动生效）；检查/下载失败仅日志提示，继续用本地模型。

## 自动维护规则

- 每次打包命令有变动时，必须同步更新 `build.bat` 和 `build.ps1` 中的打包命令
- 每次 AGENTS.md、build.bat、build.ps1、.gitignore 有变动时，必须自动提交 git（无需用户确认）
- 每次代码变动（toolbox.py 等）完成修改后，必须自动提交 git（无需用户确认）
