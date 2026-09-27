# MAP / A2L 变量地址匹配工具

## 运行

在 `tool` 目录运行：

```powershell
python app.py
```

依次选择 MAP 和有效 A2L 文件，输入变量名或前缀后点击“查询变量”。工具会显示 A2L 地址、MAP VMA/LMA、Size 和 A-E 匹配等级。

首版使用 Python 标准库和 Tkinter，不需要安装额外依赖。

## Windows 独立软件打包

打包环境只需要安装一次 PyInstaller：

```powershell
python -m pip install pyinstaller
```

在 `tool` 目录执行：

```powershell
PowerShell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

或双击：

```text
build_windows.bat
```

生成文件：

```text
tool\release\MapA2LMatcher.exe
```

该 EXE 已包含 Python 运行时、Tkinter 运行库和本工具模块，目标电脑不需要安装 Python、pytest 或其他 Python 依赖。将 `MapA2LMatcher.exe` 复制到其他 Windows 电脑后即可运行；MAP 和 A2L 仍由用户在界面中选择，不会被打包进 EXE。

首次启动可能需要数秒解压运行时。建议将整个 `release` 目录作为交付目录，并确认目标电脑允许运行未知来源的本地 EXE。
