FileCheck Win64
===============

运行方式
--------
1. 建议解压整个 FileCheck-win64.zip 后使用，不要直接在压缩包内运行。
2. 双击 FileCheck.exe 或在 PowerShell/CMD 中运行 FileCheck.exe。
3. 无参数启动时进入交互式菜单；高级用户仍可使用 scan/backup/migrate/verify/restore 等子命令。

Everything / ES CLI
-------------------
FileCheck 依赖本机 Everything 1.4.x 和 ES CLI 1.1.0.37+。
本分发包不内置 es.exe。请将 es.exe 放到：

  tools\es.exe

也可以把 es.exe 加入 PATH，或设置 FILECHECK_ES 环境变量。
Everything 本体需要已经启动并建立索引。

扫描规则
--------
默认规则文件位于：

  config\rules.json

可直接编辑该文件。FileCheck 会把本次使用的规则文件名和 SHA-256 写入扫描结果，不写入规则绝对路径。

如果只复制 FileCheck.exe 而没有 config\rules.json，程序会从 EXE 内置的默认规则初始化到：

  %LOCALAPPDATA%\FileCheck\config\rules.json

运行数据
--------
菜单模式扫描结果默认保存在：

  %LOCALAPPDATA%\FileCheck\

备份位置由用户在菜单中指定。

安全说明
--------
- scan 和 backup 不删除源文件。
- 只有 migrate 会进入源文件移除阶段。
- migrate 在删除前会完整验证备份并重新校验源文件，随后仍要求一次 YES 批次确认。
- 程序不会清理 Recent、浏览器历史、USBSTOR、Office/WPS MRU 或注册表痕迹。
- ZIP 是压缩格式，不是加密格式。
