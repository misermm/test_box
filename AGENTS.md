# AGENTS.md

## 构建规则

- 每次修改代码后都必须重新打包 exe（用户要求，必须遵守）：

```powershell
python -m PyInstaller --onefile --noconsole --name "TestToolbox" --collect-all PIL toolbox.py
```

- 打包后清理临时文件：删除 `build/` 目录和 `*.spec` 文件
- 产物：`dist/TestToolbox.exe`
