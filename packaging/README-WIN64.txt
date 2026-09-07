FileCheck v0.1.0 - Windows 10/11 x64 package
=============================================

适用系统
--------
- Windows 10 64 位。
- Windows 11 64 位。
- Windows 7 SP1 64 位请使用单独的 FileCheck-v0.1.0-win7-x64.zip 兼容包。

运行方式
--------
1. 建议解压整个 FileCheck-v0.1.0-win10plus-x64.zip 后使用，不要直接在压缩包内运行。
2. 双击 FileCheck.exe 或在 PowerShell/CMD 中运行 FileCheck.exe。
3. 无参数启动时进入交互式菜单；高级用户仍可使用 scan/backup/migrate/verify/restore 等子命令。

Everything / ES CLI
-------------------
FileCheck 依赖本机 Everything 1.4.x 和 ES CLI 1.1.0.37+。
V0.1.0 Windows 10/11 x64 发布包已经内置官方 ES CLI 1.1.0.37 x64：

  tools\es.exe

请保持 FileCheck.exe、tools、config 等目录结构完整。即使从其他工作目录启动 FileCheck.exe，程序也会优先查找 EXE 所在目录下的 tools\es.exe。
也可以通过 PATH 或 FILECHECK_ES 环境变量显式使用其他 ES 1.1.0.37+ 版本。
Everything 本体仍需在 Windows 上安装并启动，且完成索引。
ES 为 voidtools 项目，按 MIT License 再分发，许可说明见 THIRD-PARTY-NOTICES.txt。

正式使用前准备
--------------
以下操作会删除 Windows 的临时文件、最近项目快捷方式/跳转列表记录。请先确认这些记录不再需要，并按本单位制度执行。

1. 清空 Windows 回收站。
2. Win + R 输入 %temp%，清理当前用户临时目录；无法删除的占用文件直接跳过。
3. Win + R 输入 C:\Windows\Temp，清理系统级临时目录；无法删除的占用文件直接跳过。
4. Win + R 输入 recent，清理最近使用快捷方式目录。
5. 清理 %APPDATA%\Microsoft\Windows\Recent\AutomaticDestinations。
6. 清理 %APPDATA%\Microsoft\Windows\Recent\CustomDestinations。

Everything 索引准备
-------------------
1. 打开 Everything -> 工具/选项 -> 排除列表。
2. 勾选“排除隐藏文件和目录”“排除系统文件和目录”。
3. 确认待检查/备份目录没有被误加入排除列表。
4. 如果待检查目录没有由现有 NTFS 索引覆盖，可在“索引 -> 文件夹”中添加该目录。
5. 在“索引”选项卡中重建/强制重建索引，确保本次扫描基于最新索引。

推荐操作流程
------------
1. 启动 FileCheck.exe。
2. 主菜单选择 1“检查 Everything / ES 环境”，确认环境正常。
3. 主菜单选择 2“扫描并处理”。扫描范围建议选 1“Everything 当前已索引的全部范围”。
4. “关键词是否同时匹配目录路径”建议选择 N。
5. 扫描完成后会生成 scan-results-*.json。若准备按“扫描 -> 备份 -> 再验证 -> 删除源文件”分步执行，在扫描后处理菜单选择“只保存扫描结果，暂不处理”，记下 JSON 完整路径。
6. 回到主菜单选择 3“使用已有扫描结果批量备份”，输入刚生成的 JSON 完整路径，选择备份目标目录。推荐使用目录方式备份，程序会逐个复制并在完成后进行全量 SHA-256 校验。
7. 备份完成后，主菜单选择 5“验证已有备份”，输入刚生成的备份批次目录，再次执行完整校验。
8. 确认校验通过且人工检查备份目录无误后，主菜单选择 7“删除已验证备份对应的源文件”。真正删除前程序仍会重新验证备份，并重新核对源文件大小和 SHA-256；任一异常都会阻止删除阶段启动。
9. 删除源文件后，回到 Everything 的“选项 -> 索引”，强制重建索引并再次检查。
10. 妥善保存整个备份批次目录，不要只保存其中部分文件；后续恢复必须依赖 manifest.json 和备份文件。

恢复
----
后续需要恢复时：

1. 启动 FileCheck.exe。
2. 主菜单选择 6“从备份恢复到原路径”。
3. 输入完整备份批次目录（或 ZIP 备份）路径。
4. 程序会先完整验证备份，再根据 manifest.json 恢复到原始路径。

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
- 推荐先目录方式批量备份，再独立验证已有备份，最后再选择删除源文件。
- 独立删除功能不会仅相信此前的验证结果；真正删除前仍会重新完整验证备份并逐个复核源文件。
- 只删除 manifest 中明确列出的源文件，不递归删除目录，也不会删除同目录中的其他文件。
- migrate 仍保留，适用于希望把“备份 -> 验证 -> 源文件删除”一次连续完成的场景。
- 源文件删除前要求一次 YES 批次确认。
- FileCheck 程序本身不会自动清理 Recent、浏览器历史、USBSTOR、Office/WPS MRU 或注册表痕迹；上面的 Windows 临时/Recent 清理是独立的人工准备步骤。
- ZIP 是压缩格式，不是加密格式。
