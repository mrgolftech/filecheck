FileCheck v0.1.1 - Windows 10/11 x64 portable package
====================================================

适用系统
--------
- Windows 10 64 位。
- Windows 11 64 位。
- Windows 7 SP1 64 位请使用单独的 FileCheck-v0.1.1-win7-x64.zip 兼容包。

包内组件
--------
本包无需目标电脑安装 Python，也不要求预先安装 Everything。

目录中应包含：

  FileCheck.exe
  config\rules.json
  tools\Everything.exe   (Everything 1.4.1.1032 x64 portable)
  tools\es.exe           (ES 1.1.0.37 x64)
  THIRD-PARTY-NOTICES.txt
  SHA256SUMS.txt

请保持整个目录结构完整，不要只复制 FileCheck.exe。

FileCheck 会启动名为 FileCheck 的专用 Everything 实例，并把运行时索引放到：

  runtime\everything\Everything.ini
  runtime\everything\Everything.db

扫描结果默认放到：

  scan-results\

专用索引不会依赖或修改用户另行安装的默认 Everything 实例。

运行方式
--------
1. 将整个 ZIP 解压到一个普通目录，不要直接在压缩包内运行。
2. 双击 FileCheck.exe 进入交互式菜单。
3. 也可以在 PowerShell/CMD 中使用高级子命令。

首次使用
--------
推荐先进入：

  1. 环境与索引

然后：
- 选择需要建立索引的磁盘/目录；
- 指定统一备份根目录；
- FileCheck 会自动把程序目录和备份根目录排除在专用索引之外；
- 建立/重建专用 Everything 索引。

推荐操作流程
------------
1. 环境与索引。
2. 扫描文件。
3. 人工核对 scan-results 中生成的 JSON / CSV。
4. 创建目录备份。
5. 用资源管理器人工检查备份目录后，再执行一次完整 verify。
6. 确认无误后，显式进入“删除源文件 / 继续未完成删除”。
7. 将来需要时，从完整备份批次按 manifest 恢复到各自原路径。

目录备份布局
------------
FileCheck v0.1.1 只创建目录备份，不再创建 ZIP 备份。

例如：

  G:\work\ProjectA\报告.pdf

备份为：

  <批次目录>\files\G\work\ProjectA\报告.pdf

不同目录中的同名文件会保持为不同 backup_path，不会拍平或互相覆盖。

每个正式备份批次至少包含：

  manifest.json
  files\...

manifest.json 记录每个文件的：
- source_path
- backup_path
- size
- mtime_ns
- sha256

manifest.json 是备份创建时的不可变恢复清单，不记录 source_removed 状态。

源文件删除状态
--------------
只有显式执行源文件删除后，备份批次目录中才会出现：

  source-removal.json

如果存在未删除文件，还会出现：

  not-deleted.txt

删除逻辑：
- 删除前重新验证整个备份；
- 删除前重新核对全部源文件大小和 SHA-256；
- 全部通过后才允许进入删除阶段；
- 需要一次批次级 YES 确认；
- 只删除 manifest 中明确列出的 source_path；
- 不递归删除父目录，不自动删除空目录；
- 文件被占用/权限不足时跳过该文件并继续处理其他文件；
- 关闭占用程序后可以继续未完成删除；
- 已删除路径后来重新出现时，不会自动再次删除，避免误删新数据。

恢复
----
恢复只接受“已经展开为目录”的备份。

FileCheck v0.1.1 不直接读取 ZIP 文件。如果是 v0.1.0 的旧 ZIP 备份，请先完整解压，再把解压目录交给 FileCheck。旧 manifest 中即使仍写有 mode=zip，只要目录中的 manifest.json 和 files\ 完整，v0.1.1 可以校验和恢复。

恢复前会先完整验证整个备份。冲突策略：

  skip       原路径已存在时跳过（默认/推荐）
  rename     恢复成另一个名称
  overwrite  先写临时文件并校验，成功后再替换原文件

扫描规则
--------
默认规则文件：

  config\rules.json

扫描结果只记录规则文件名和规则 SHA-256，不记录规则绝对路径。
关键词命中仅代表候选，不等于违规或最终分类结论。

安全边界
--------
- scan 不删除文件。
- backup 不删除源文件。
- FileCheck 不清理 Recent、浏览器历史、Office/WPS MRU、USBSTOR、注册表等系统使用痕迹。
- FileCheck 不递归删除目录。
- FileCheck 当前保证普通文件内容、原始路径、大小、SHA-256 和基础 mtime 的备份/恢复；不承诺 ACL、EFS、ADS、硬链接、稀疏文件、重解析点、所有者/审计信息等 Windows 高级文件系统元数据。

第三方组件许可见 THIRD-PARTY-NOTICES.txt。
