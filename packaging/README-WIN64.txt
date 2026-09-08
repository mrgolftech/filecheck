FileCheck v0.1.1 - Windows 10/11 x64 portable package
====================================================

适用系统
--------
- Windows 10 64 位
- Windows 11 64 位
- Windows 7 SP1 64 位请使用 FileCheck-v0.1.1-win7-x64.zip

包内组件
--------
本包无需安装 Python，也不要求预先安装 Everything。

目录中应包含：

  FileCheck.exe
  config\rules.json
  tools\Everything.exe   (Everything 1.4.1.1032 x64 portable)
  tools\es.exe           (ES 1.1.0.37 x64)
  THIRD-PARTY-NOTICES.txt
  SHA256SUMS.txt

请保持整个目录结构完整，不要只复制 FileCheck.exe。

运行数据默认保存在程序目录：

  runtime\everything\Everything.ini
  runtime\everything\Everything-FileCheck.db
  runtime\everything\index-config.json
  runtime\operations\
  scan-results\

FileCheck 使用独立的 Everything 实例“FileCheck”，不会依赖或修改用户另行安装的默认 Everything，也不会安装永久 Windows 服务。

运行方式
--------
1. 将 ZIP 完整解压到普通目录，不要直接在压缩包内运行。
2. 推荐右键 FileCheck.exe -> 以管理员身份运行。
3. 无参数启动进入交互式菜单；高级功能也可在 CMD/PowerShell 中通过子命令运行。

主菜单
------

  1. 环境检查与索引创建
  2. 扫描文件列表
  3. 核对扫描结果
  4. 创建备份 / 继续未完成的备份任务
  5. 检查备份
  6. 删除源文件 / 继续未完成的删除任务
  7. 恢复备份文件到源路径
  0. 退出

推荐操作流程
------------
1. 菜单 1：选择索引磁盘并设置统一备份根目录。
2. 菜单 2：扫描；程序会先显示当前关键词、扩展名和 config\rules.json 路径。
3. 菜单 3：人工核对 JSON / CSV。
4. 菜单 4：创建目录备份；如复制曾中断，也从这里继续未完成任务。
5. 用资源管理器人工检查备份目录。
6. 菜单 5：再次完整验证备份。
7. 确认无误后，菜单 6：显式删除源文件。
8. 需要恢复时，菜单 7：按 manifest 恢复到原路径。

目录备份
--------
V0.1.1 新建备份只使用目录方式，不创建 ZIP。

例如：

  G:\work\ProjectA\报告.pdf

备份为：

  <批次目录>\files\G\work\ProjectA\报告.pdf

不同目录中的同名文件不会互相覆盖。

正式备份批次：

  FC-...\
    manifest.json
    files\...

manifest.json 记录 source_path、backup_path、size、mtime_ns、sha256，是不可变恢复清单，不记录 source_removed。

删除源文件
----------
删除是独立显式操作，backup 本身永远不会删除源文件。

第一次删除流程：
- 完整验证整个备份；
- 对全部源文件执行一次 size + SHA-256 强复核；
- 任一源文件异常则整批删除不启动；
- 全部通过后要求一次批次级 YES 确认；
- YES 后使用预检元数据快照做快速检查，不再逐文件重复整文件 SHA-256；
- 只删除 manifest 中明确列出的 source_path；
- Windows“只读”属性自动处理；ACL 权限、文件占用、杀毒软件拦截等真实错误仍会失败并记录；
- 删除阶段发现文件已不存在时记录 already_absent，并继续；
- 失败项写入 not-deleted.txt，可在关闭占用程序后继续处理；
- 已删除/已不存在的路径以后重新出现时标记 reappeared，不会自动再删。

删除状态文件：

  source-removal.json
  not-deleted.txt        # 仅存在失败/reappeared 项时生成

恢复
----
恢复只接受已经展开为目录的备份。

冲突策略：

  skip       原路径已存在时跳过（默认/推荐）
  rename     恢复成另一个名称
  overwrite  先写临时文件并校验，成功后原子替换

选择冲突策略后，程序会先提示正在执行恢复前 SHA-256 完整性校验。文件较多或较大时需要一定时间，这是正常流程。

恢复过程会对备份、临时文件和最终落盘文件进行 SHA-256 校验。默认 skip 策略下，被跳过的目标会记录到备份批次中的 restore-skipped.txt。

恢复 V0.1.0 旧 ZIP
------------------
V0.1.1 不直接读取 ZIP。如果要恢复 V0.1.0 旧 ZIP，请先完整解压，确认包含 manifest.json 和 files\，再把解压后的目录交给 FileCheck。旧 manifest 即使仍写有 mode=zip，也可以恢复。

扫描规则
--------
默认规则文件：

  config\rules.json

进入菜单 2 时会显示当前实际生效的关键词、扩展名和规则文件路径；修改后保存并重新扫描即可。

高级 CLI
--------
例如：

  FileCheck.exe doctor
  FileCheck.exe verify H:\FileCheckBackup\FC-...
  FileCheck.exe remove-resume H:\FileCheckBackup\FC-...
  FileCheck.exe restore H:\FileCheckBackup\FC-... --conflict skip
  FileCheck.exe selftest

selftest 是开发/回归用的临时文件回环测试，不在普通菜单中。

安全边界
--------
- scan 和 backup 不删除源文件。
- FileCheck 不递归删除目录。
- FileCheck 不清理 Recent、浏览器历史、Office/WPS MRU、USBSTOR、注册表等使用痕迹。
- 当前恢复范围聚焦普通文件内容、原始路径、大小、SHA-256 和基础 mtime；不承诺 ACL、EFS、ADS、硬链接、稀疏文件、重解析点、所有者/审计信息等高级元数据。

第三方组件许可见 THIRD-PARTY-NOTICES.txt。
