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

目录备份布局
------------
目录备份默认保留源盘符、目录层级和原始文件名，便于人工直接检查。例如：

  G:\work\ProjectA\报告.pdf

备份为：

  <批次目录>\files\G\work\ProjectA\报告.pdf

manifest.json 同时记录 source_path、backup_path、大小、mtime 和 SHA-256。
程序不会把文件改成哈希文件名或全部拍平到一个目录。
Windows 实际文件 I/O 使用长路径兼容处理；极深目录在部分旧版资源管理器/第三方工具中仍可能显示受限。

安全说明
--------
- scan 和 backup 不删除源文件。
- 可以先使用“目录方式批量备份全部候选”，再独立“验证已有备份”，最后选择“删除已验证备份对应的源文件”。
- 独立删除功能不会仅相信此前的验证结果；真正删除前仍会重新完整验证备份并逐个复核源文件。
- 只删除 manifest 中明确列出的源文件，不递归删除目录，也不会删除同目录中的其他文件。
- migrate 仍保留，适用于希望把“备份→验证→源文件删除”一次连续完成的场景。
- 源文件删除前要求一次 YES 批次确认。
- 程序不会清理 Recent、浏览器历史、USBSTOR、Office/WPS MRU 或注册表痕迹。
- ZIP 是压缩格式，不是加密格式。
