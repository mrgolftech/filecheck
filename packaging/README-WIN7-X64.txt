FileCheck v0.1.1 - Windows 7 SP1 x64 compatibility package
===========================================================

适用系统
--------
- Windows 7 SP1 64 位
- 使用 Python 3.8.10 x64 + PyInstaller 5.13.2 构建
- Windows 10/11 64 位建议优先使用 FileCheck-v0.1.1-win10plus-x64.zip

包内组件
--------

  FileCheck.exe
  config\rules.json
  tools\Everything.exe   (Everything 1.4.1.1032 x64 portable)
  tools\es.exe           (ES 1.1.0.37 x64)
  THIRD-PARTY-NOTICES.txt
  SHA256SUMS.txt

不需要安装 Python，也不要求预先安装 Everything。

运行数据保存在程序目录：

  runtime\everything\Everything.ini
  runtime\everything\Everything-FileCheck.db
  runtime\everything\index-config.json
  runtime\operations\
  scan-results\

FileCheck 使用独立的 Everything 实例“FileCheck”，不依赖用户已有 Everything，也不安装永久服务。

运行方式
--------
1. 将 ZIP 完整解压，不要直接在压缩包内运行。
2. 推荐右键 FileCheck.exe -> 以管理员身份运行。
3. 交互式主流程要求管理员权限；selftest/--help 等高级 CLI 可单独运行。

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

推荐流程
--------
1. 菜单 1：选择磁盘并建立 FileCheck 专用索引，设置统一备份根目录。
2. 菜单 2：扫描文件；程序先显示关键词、扩展名和 config\rules.json 路径。
3. 菜单 3：人工核对 JSON / CSV。
4. 菜单 4：创建目录备份；中断的复制任务也在这里继续。
5. 人工检查备份目录。
6. 菜单 5：再次完整验证备份。
7. 菜单 6：确认无误后显式删除源文件。
8. 菜单 7：需要时恢复到原路径。

目录备份
--------
V0.1.1 新建备份只使用目录方式，不创建 ZIP。

正式备份批次：

  FC-...\
    manifest.json
    files\...

manifest.json 是不可变恢复清单，记录 source_path、backup_path、size、mtime_ns、sha256，不记录 source_removed。

删除源文件
----------
删除前会：
- 完整验证备份；
- 对全部源文件执行一次 size + SHA-256 强复核；
- 任一异常时整批删除不启动；
- 全部通过后要求输入 YES；
- YES 后按预检元数据快照快速检查，不再逐文件重复计算整文件 SHA-256；
- 只删除 manifest 中明确列出的文件，不递归删除目录。

Windows 只读属性会被自动处理。ACL 权限、文件占用、杀毒软件拦截等真实错误仍会标记为 failed。

删除过程中如果文件已经不存在，则记录 already_absent 并继续。失败项保存在 source-removal.json / not-deleted.txt 中，可以继续处理。

如果此前已经 deleted/already_absent 的路径以后重新出现，会标记 reappeared，不会自动再次删除，以避免误删新数据。

恢复
----
恢复前先对整个备份执行完整 SHA-256 校验，随后才开始恢复；文件多或较大时这一步会有明显等待时间，程序会显示提示。

冲突策略：

  skip       原路径存在时跳过（默认/推荐）
  rename     恢复为新名称
  overwrite  临时文件校验通过后原子替换

恢复过程还会校验临时文件和最终落盘文件。默认 skip 时，跳过项写入 restore-skipped.txt。

恢复 V0.1.0 旧 ZIP
------------------
V0.1.1 不直接读取 ZIP。旧 ZIP 请先人工完整解压，确认有 manifest.json 和 files\，再将解压目录交给 FileCheck。旧 manifest 即使 mode=zip 仍可使用。

Win7 特别注意
-------------
- 请使用 Windows 7 SP1，并尽量安装可用系统更新。
- 若缺少 Universal C Runtime / VC 运行库相关更新，FileCheck.exe 可能无法启动，应先补齐系统运行库更新。
- Windows 7 长路径能力弱于 Windows 10/11，极端超长路径仍需重点验证。
- NTFS MFT/USN 快速索引、受保护文件删除/恢复建议始终以管理员身份运行。

高级 CLI
--------

  FileCheck.exe doctor
  FileCheck.exe verify H:\FileCheckBackup\FC-...
  FileCheck.exe remove-resume H:\FileCheckBackup\FC-...
  FileCheck.exe restore H:\FileCheckBackup\FC-... --conflict skip
  FileCheck.exe selftest

selftest 是开发/回归用临时文件回环测试，不在普通菜单中。

安全边界
--------
- scan 和 backup 不删除源文件。
- FileCheck 不清理 Recent、浏览器历史、Office/WPS MRU、USBSTOR、注册表等痕迹。
- 当前恢复范围聚焦普通文件内容、路径、大小、SHA-256 和基础 mtime，不承诺 ACL/EFS/ADS/硬链接/稀疏文件/重解析点等高级元数据。

第三方组件许可见 THIRD-PARTY-NOTICES.txt。
