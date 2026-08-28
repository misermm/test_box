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
  toolbox.py
```

- 打包后清理临时文件：删除 `build/` 目录和 `*.spec` 文件
- 产物：`dist/TestToolbox.exe`
- 表格识别使用本地离线模型：模型预下载在项目 `models/` 目录（不入 git），
  运行时通过环境变量 `PADDLE_PDX_CACHE_HOME` 指向 exe 同级的 `models/` 目录，
  不联网。分发时 `TestToolbox.exe` 必须与 `models/` 文件夹放在同一目录。
  若 `models/` 缺失，会自动从 BOS（百度 CDN）联网下载兜底。

## 自动维护规则

- 每次打包命令有变动时，必须同步更新 `build.bat` 和 `build.ps1` 中的打包命令
- 每次 AGENTS.md、build.bat、build.ps1、.gitignore 有变动时，必须自动提交 git（无需用户确认）
- 每次代码变动（toolbox.py 等）完成修改后，必须自动提交 git（无需用户确认）
