FileCheck v0.1.1 - Windows 7 SP1 32-bit (x86)
================================================

适用系统
--------
- Windows 7 SP1 32 位（x86）
- 使用 32 位 Python 3.8.10 + PyInstaller 5.13.2 构建
- 64 位 Windows 请优先使用对应 x64 包

便携包内容
----------

  FileCheck.exe
  config\rules.json
  tools\Everything.exe   (Everything 1.4.1.1032 x86 portable)
  tools\es.exe           (ES 1.1.0.37 x86)
  THIRD-PARTY-NOTICES.txt
  SHA256SUMS.txt

无需安装 Python，也不要求预先安装 Everything。

运行数据默认保存在程序目录：

  runtime\everything\Everything.ini
  runtime\everything\Everything-FileCheck.db
  runtime\everything\index-config.json
  runtime\operations\
  scan-results\

FileCheck 使用独立的 Everything 实例“FileCheck”，不会依赖用户已有 Everything，也不会安装永久服务。

运行方式
--------
1. 将 ZIP 完整解压到普通目录。
2. 推荐右键 FileCheck.exe -> 以管理员身份运行。
3. 无参数启动进入交互式菜单。

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
1. 菜单 1：建立专用索引并设置备份根目录。
2. 菜单 2：扫描文件；先查看当前关键词、扩展名和 config\rules.json 路径。
3. 菜单 3：人工核对 JSON / CSV。
4. 菜单 4：创建目录备份；中断的复制任务也从这里继续。
5. 菜单 5：再次完整验证备份。
6. 菜单 6：确认无误后显式删除源文件。
7. 菜单 7：需要时恢复到原路径。

删除与恢复
----------
- 删除前先完整验证备份，并对全部源文件执行一次 size + SHA-256 强复核。
- 任一异常时整批删除不启动；全部通过后才要求 YES。
- YES 后按预检元数据快照快速检查，不再逐文件重复整文件 SHA-256。
- Windows 只读属性自动处理；ACL、文件占用、杀毒软件拦截等真实错误仍会记录为 failed。
- 删除阶段发现文件已经不存在时记录 already_absent，并继续。
- 已删除/已不存在的路径后来重新出现时标记 reappeared，不会自动再次删除。
- 恢复默认冲突策略为 skip；选择策略后会先完整校验备份 SHA-256，再开始恢复。
- 被 skip 的目标会写入备份批次中的 restore-skipped.txt。

恢复 V0.1.0 旧 ZIP
------------------
V0.1.1 不直接读取 ZIP。旧 ZIP 请先人工完整解压，确认有 manifest.json 和 files\，再将解压目录交给 FileCheck。

Windows 7 x86 注意事项
----------------------
- 请使用 Windows 7 SP1。
- 若缺少较新的 VC/UCRT 运行组件，可能需要先安装微软官方 Windows 7 更新/运行库。
- 32 位进程可用虚拟地址空间明显小于 64 位版本；超大扫描结果或极端数量文件场景更推荐 64 位系统和 x64 包。
- NTFS MFT/USN 快速索引和受保护文件操作建议始终以管理员身份运行。

高级 CLI
--------

  FileCheck.exe doctor
  FileCheck.exe verify H:\FileCheckBackup\FC-...
  FileCheck.exe remove-resume H:\FileCheckBackup\FC-...
  FileCheck.exe restore H:\FileCheckBackup\FC-... --conflict skip
  FileCheck.exe selftest

selftest 是开发/回归用临时文件回环测试，不在普通菜单中。

第三方组件许可见 THIRD-PARTY-NOTICES.txt。
