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

## 自动维护规则

- 每次打包命令有变动时，必须同步更新 `build.bat` 和 `build.ps1` 中的打包命令
- 每次 AGENTS.md、build.bat、build.ps1 有变动时，必须自动提交 git（无需用户确认）
- 每次代码变动（toolbox.py 等）完成修改后，必须自动提交 git（无需用户确认）
