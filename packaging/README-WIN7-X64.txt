FileCheck v0.1.1 - Windows 7 SP1 x64 compatibility package
===========================================================

适用系统
--------
- Windows 7 SP1 64 位。
- 该包继续使用 Python 3.8.10 + PyInstaller 5.13.2 构建，以保留 Win7 兼容路线。
- Windows 10/11 建议优先使用 FileCheck-v0.1.1-win10plus-x64.zip。

注意：v0.1.0 Win7 包已经在真实 Windows 7 64 位机器上完成过启动和实际使用验收；v0.1.1 修改了索引/菜单/目录备份流程，并把 Everything 本体纳入便携包，因此 v0.1.1 在正式发布前仍需要重新进行一次真实 Win7 实机回归。

包内组件
--------
本包应包含：

  FileCheck.exe
  config\rules.json
  tools\Everything.exe   (Everything 1.4.1.1032 x64 portable)
  tools\es.exe           (ES 1.1.0.37 x64)
  THIRD-PARTY-NOTICES.txt
  SHA256SUMS.txt

不需要另外安装 Python，也不要求预先安装 Everything。

FileCheck 会启动独立的 FileCheck Everything 实例，索引数据保存在：

  runtime\everything\Everything.ini
  runtime\everything\Everything.db

扫描结果默认保存在：

  scan-results\

推荐流程
--------
1. 运行 FileCheck.exe。
2. 菜单 1：环境与索引，选择要索引的磁盘/目录并设置统一备份根目录。
3. 菜单 2：扫描文件；默认建议只匹配文件名，不把父目录路径纳入关键词匹配。
4. 菜单 3：人工核对 JSON / CSV。
5. 菜单 4：创建目录备份。
6. 用资源管理器人工检查备份目录。
7. 菜单 5：再次完整验证备份。
8. 确认无误后，菜单 6：删除源文件 / 继续未完成删除。
9. 将来需要时，菜单 7：恢复到各自原路径。

目录备份与删除状态
------------------
FileCheck v0.1.1 只创建目录备份，不再创建 ZIP。

正式备份批次：

  FC-...\
    manifest.json
    files\...

manifest.json 是不可变恢复清单，不记录 source_removed。

显式删除源文件后，会在同一个备份批次目录内写入：

  source-removal.json

如果有文件因占用/权限等原因未删除，还会写入：

  not-deleted.txt

关闭占用程序后可以继续删除失败项；已经删除的项目不会重复删除。若此前已删除的路径后来重新出现，则视为可能的新数据，不会自动再次删除。

恢复旧备份
----------
FileCheck v0.1.1 不直接读取 ZIP 文件。

如果需要恢复 v0.1.0 的旧 ZIP 备份，请先完整解压，然后把解压目录交给 FileCheck。即使旧 manifest.json 中仍有 mode=zip，只要 manifest.json 和 files\ 目录完整，v0.1.1 可以进行完整性校验和原路径恢复。

Win7 特别注意
-------------
- 建议 Windows 7 SP1 已安装全部可用系统更新。
- 若系统缺少 Universal C Runtime / VC 运行库相关更新，FileCheck.exe 可能无法启动，应先补齐系统运行库更新。
- Windows 7 的长路径能力弱于 Windows 10/11。FileCheck 会尽量使用兼容 I/O 路径，但极端超长路径仍需重点实测。
- v0.1.1 的正式验收必须至少覆盖：启动、建立专用 Everything 索引、扫描、目录备份、verify、删除失败/继续删除、恢复、同名不同路径文件。

安全边界
--------
- scan 和 backup 不删除源文件。
- 删除前会重新验证完整备份并复核全部源文件，之后仍需一次 YES 确认。
- 只删除 manifest 中列出的源文件，不递归删除目录。
- FileCheck 不清理 Recent、浏览器历史、Office/WPS MRU、USBSTOR 或注册表痕迹。
- 当前恢复范围聚焦普通文件内容、路径、大小、SHA-256 和基础 mtime，不承诺 ACL/EFS/ADS/硬链接/稀疏文件/重解析点等高级元数据。

第三方组件许可见 THIRD-PARTY-NOTICES.txt。
