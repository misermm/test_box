# AGENTS.md

## 构建规则

- 每次修改代码后都必须重新打包 exe（用户要求，必须遵守）：

```powershell
python -m PyInstaller --onefile --noconsole --name "TestToolbox" `
  --collect-all PIL `
  --collect-all cv2 `
  --collect-all paddle `
  --collect-all pyclipper `
  --collect-all shapely `
  --collect-all paddlex `
  --add-data "C:\Users\X\AppData\Local\Programs\Python\Python313\Lib\site-packages\paddle\libs;paddle\libs" `
  toolbox.py
```

- 打包后清理临时文件：删除 `build/` 目录和 `*.spec` 文件
- 产物：`dist/TestToolbox.exe`

## 自动维护规则

- 每次打包命令有变动时，必须同步更新 `build.bat` 和 `build.ps1` 中的打包命令
- 每次 AGENTS.md、build.bat、build.ps1 有变动时，必须自动提交 git（无需用户确认）
