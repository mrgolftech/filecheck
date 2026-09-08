FileCheck v0.1.1 GUI - Windows 7 SP1 x64 portable package
==========================================================

用途
----
这是 FileCheck 的 CustomTkinter 图形界面测试包，面向 Windows 7 SP1 / Windows 10 / Windows 11 64 位实机验收。

构建基线：
- Python 3.8.10 x64
- PyInstaller 5.13.2
- CustomTkinter 5.2.2

主要目录
--------

  FileCheck-GUI\
    FileCheck-GUI.exe     图形界面入口
    *.dll / *.pyd         Python / Tk / PyInstaller 运行依赖，请勿删除
  config\rules.json       扫描规则，GUI 可直接编辑
  tools\Everything.exe    Everything 1.4.1.1032 x64 portable
  tools\es.exe            ES 1.1.0.37 x64
  advanced\FileCheck.exe  高级 CLI，仅用于诊断/交叉验证
  README.txt
  THIRD-PARTY-NOTICES.txt
  SHA256SUMS.txt

GUI 使用 PyInstaller onedir 打包。DLL/PYD 是 Python、Tk 和第三方库的正常运行文件，不能删除；本包将这些文件集中放在 FileCheck-GUI 子目录，避免散落在 ZIP 根目录。

首次使用
--------
1. 将 ZIP 完整解压到本地目录，不要直接在压缩包内运行。
2. 右键 FileCheck-GUI\FileCheck-GUI.exe -> 以管理员身份运行。
3. 首页先阅读“正式扫描前建议先人工准备”的清理提示。
4. 进入“设置”：配置统一备份根目录、扫描关键词和文件类型并保存。
5. 进入“扫描”：勾选需要检查的磁盘，点击“创建 / 更新索引”。
6. 索引完成后点击“开始扫描”。
7. 在“扫描结果”查看摘要，并人工核对 JSON / CSV。
8. 进入“备份”，确认扫描摘要和备份空间预检后执行备份。
9. 如需迁出源文件，进入“源文件删除”并完成安全复核和 DELETE 二次确认。
10. 需要恢复时进入“恢复”。

现在首次 Everything 专用索引创建已经集成到 GUI，不再要求先打开 CLI。

正式扫描前建议人工准备
----------------------
FileCheck 不会自动执行以下 Windows 清理动作。请确认相关记录不再需要，并按本单位制度执行：

- 清空 Windows 回收站；
- Win + R → %temp%：清理当前用户临时目录；
- Win + R → C:\Windows\Temp：清理系统临时目录；
- Win + R → recent：清理最近使用快捷方式；
- 清理 %APPDATA%\Microsoft\Windows\Recent\AutomaticDestinations；
- 清理 %APPDATA%\Microsoft\Windows\Recent\CustomDestinations。

GUI 主流程
----------

  首页准备提示
   ↓
  设置：备份目录 / 关键词 / 文件类型
   ↓
  扫描：选择磁盘 → 创建索引 → 扫描
   ↓
  扫描结果：摘要 + JSON / CSV 人工核对
   ↓
  备份：空间预检 → 批量备份 → 全量 SHA-256
   ↓
  源文件删除：再次复核 → DELETE 二次确认 → 删除/续作
   ↓
  恢复：skip / rename / overwrite

扫描
----
扫描页直接列出 Windows 固定盘和可移动盘。首次使用或扫描范围变化时，勾选磁盘并创建/更新 FileCheck 专用 Everything 索引。

NTFS 快速索引需要管理员权限。索引建立后才能开始扫描。

扫描关键词和文件类型由“设置”页面统一维护。扫描结果同时保存 JSON / CSV；关键词命中仅表示候选，执行备份前应人工核对。

备份
----
备份根目录只能在“设置”中统一修改，备份页面不再提供临时路径选择。

备份页显示当前扫描摘要：候选数量、高风险/敏感/复核数量、总容量、JSON 和 CSV 路径。

执行前会检查：
- 文件数量；
- 源文件总容量；
- 预计空间需求；
- 安全余量；
- 目标盘可用空间。

正式备份采用目录方式：复制文件时计算 SHA-256，复制完成后再对备份执行全量 SHA-256 校验。备份步骤永远不会自动删除源文件。

源文件删除
----------
源文件删除是独立高风险步骤。

删除前会完整验证备份并对 manifest 中全部源文件重新执行 size + SHA-256 复核；任一文件不一致时整批删除不会启动。全部通过后必须输入 DELETE 才能执行。

删除状态持续写入 source-removal.json；中途取消只会在安全检查点生效，之后可以继续未完成项。重新出现的同路径文件会被保护，不会自动再次删除。

恢复
----
恢复页默认采用最保守的 skip 策略：

  skip       已有目标保持不动，只恢复缺失文件（默认/推荐）
  rename     已有目标保持不动，把备份内容恢复为新的不冲突文件名
  overwrite  用备份内容覆盖已有目标

正式恢复前会全量验证备份 SHA-256、检查原始驱动器/共享并统计冲突。overwrite 且存在冲突时必须输入 OVERWRITE 二次确认。

运行数据
--------
完整便携包使用统一程序根目录保存：

  config\
  runtime\everything\
  runtime\operations\
  scan-results\

FileCheck 使用独立 Everything 实例“FileCheck”，不会复用或修改用户自己的 Everything 实例。

Win7 特别注意
-------------
- 使用 Windows 7 SP1 64 位。
- 建议安装可获得的系统更新和 Universal C Runtime / VC 运行库相关更新。
- NTFS MFT/USN 索引、受保护路径扫描、删除和恢复建议以管理员身份运行。
- Windows 7 对极端超长路径的支持弱于 Windows 10/11，需要实机重点测试。
- CI 的 Python 3.8 / GUI 构造测试只是兼容性门槛，不等同于真实 Windows 7 实机验收。

高级 CLI
--------
advanced\FileCheck.exe 仅保留用于诊断和交叉验证，正常 GUI 主流程不依赖它。

安全边界
--------
- scan 和 backup 不删除源文件。
- 删除源文件与覆盖恢复都有独立风险确认。
- FileCheck 不自动清理 Recent、浏览器历史、Office/WPS MRU、USBSTOR、注册表等系统使用痕迹。
- 当前恢复聚焦普通文件内容、路径、大小、SHA-256 和基础 mtime；不承诺完整还原 ACL/EFS/ADS/硬链接/稀疏文件/重解析点等高级元数据。

第三方组件许可说明见 THIRD-PARTY-NOTICES.txt。
