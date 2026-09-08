FileCheck v0.1.1 GUI - Windows 7 SP1 x64 portable package
==========================================================

用途
----
这是 FileCheck 的 CustomTkinter 图形界面测试包，面向 Windows 7 SP1 / Windows 10 / Windows 11 64 位实机验收。

构建基线：
- Python 3.8.10 x64
- PyInstaller 5.13.2
- CustomTkinter 5.2.2

包内同时保留原 CLI 入口，便于环境初始化、诊断和交叉验证。

主要文件
--------

  FileCheck-GUI.exe     图形界面入口（推荐日常使用）
  FileCheck.exe         原 CLI 入口（保留兼容与诊断能力）
  config\rules.json     扫描规则，GUI / CLI 共用
  tools\Everything.exe  Everything 1.4.1.1032 x64 portable
  tools\es.exe          ES 1.1.0.37 x64
  README.txt
  THIRD-PARTY-NOTICES.txt
  SHA256SUMS.txt

注意：GUI 使用 PyInstaller onedir 方式打包。FileCheck-GUI.exe 依赖同目录下的运行文件，不能只复制单个 GUI EXE 到其他位置使用；请始终完整解压并保留整个目录。

首次使用
--------
1. 将 ZIP 完整解压到本地目录，不要直接在压缩包内运行。
2. 推荐右键 FileCheck.exe -> 以管理员身份运行。
3. 首次使用先在 CLI 主菜单执行“环境检查与索引创建”，选择需要检查的磁盘/目录，并设置统一备份根目录。
4. 索引建立完成后关闭 CLI。
5. 右键 FileCheck-GUI.exe -> 以管理员身份运行，开始使用图形界面。

当前 GUI 暂未提供“首次创建 Everything 专用索引”的完整页面，因此第一次初始化仍保留 CLI 入口。索引建立后，扫描、结果查看、备份、源文件安全处理和恢复均可在 GUI 中完成。

GUI 推荐流程
-----------

  扫描
   ↓
  扫描结果人工核对
   ↓
  备份与迁出：先预检空间，再批量备份 + 全量 SHA-256
   ↓
  源文件处理：再次复核备份和全部源文件
   ↓
  输入 DELETE 二次确认后删除
   ↓
  需要时在“恢复”页选择备份恢复

扫描
----
GUI 读取 config\rules.json 和 FileCheck 专用 Everything 索引。

默认只匹配文件名；如主动勾选，可同时匹配完整目录路径。
扫描结果同时保存 JSON / CSV。关键词命中仅表示候选，执行备份前应人工核对。

备份
----
GUI 会先显示：
- 文件数量
- 源文件总容量
- 预计空间需求
- 安全余量
- 目标盘可用空间

预检通过后才能开始正式备份。
正式备份采用目录方式：复制文件时计算 SHA-256，复制完成后再对备份执行全量 SHA-256 校验。

备份步骤永远不会自动删除源文件。

源文件处理
----------
源文件删除是独立的高风险步骤。

删除前会：
- 再次完整验证备份；
- 对 manifest 中全部源文件重新执行 size + SHA-256 复核；
- 任一源文件与已验证备份不一致时，整批删除不会启动；
- 全部通过后，GUI 明确显示影响文件数量；
- 必须输入 DELETE 后才能解锁红色删除按钮。

删除状态持续写入 source-removal.json。中途取消只会在安全检查点生效；已经删除的状态会先落盘，因此之后可以继续处理。

失败文件不会被假装成已删除。失败和未完成项可以再次载入备份批次后继续。

恢复
----
恢复页默认采用最保守的“跳过已有文件”策略。

三种冲突策略：

  skip       已有目标保持不动，只恢复缺失文件（默认/推荐）
  rename     已有目标保持不动，把备份内容恢复为新的不冲突文件名
  overwrite  用备份内容覆盖已有目标

正式恢复前必须执行“验证备份与目标”：
- 全量验证备份 SHA-256；
- 检查原始驱动器/共享是否可用；
- 统计已有目标冲突；
- 根据当前策略显示预计恢复/跳过数量。

若选择 overwrite 且存在目标冲突，GUI 使用红色危险按钮，并要求输入 OVERWRITE 二次确认。

每个恢复文件先写入同目录临时文件，临时文件校验通过后再原子替换/发布；最终落盘文件还会再次执行 SHA-256 校验。

恢复取消规则：
- 正式恢复前的全量备份校验阶段取消：不写任何目标文件；
- 已进入文件恢复阶段取消：当前文件完成最终校验后停止，已完成项不回滚；
- skip 模式可以重新预检后继续补齐缺失文件；
- rename 模式中断后应先人工核对已生成副本，避免重复执行时生成额外重命名副本。

运行数据
--------
使用完整便携包时，配置和运行数据位于程序目录：

  config\
  runtime\everything\
  runtime\operations\
  scan-results\

FileCheck 使用独立的 Everything 实例“FileCheck”，不会复用或修改用户自己的 Everything 实例。

Win7 特别注意
-------------
- 使用 Windows 7 SP1 64 位。
- 建议安装仍可获得的系统更新和 Universal C Runtime / VC 运行库相关更新。
- NTFS MFT/USN 索引、受保护路径扫描、删除和恢复建议以管理员身份运行。
- Windows 7 对极端超长路径的支持弱于 Windows 10/11，需要实机重点测试。
- 当前 CI 的 Python 3.8 / GUI 构造测试只是兼容性门槛，不等同于真实 Windows 7 实机验收。

CLI 诊断
--------

  FileCheck.exe doctor
  FileCheck.exe selftest
  FileCheck.exe verify H:\FileCheckBackup\FC-...
  FileCheck.exe remove-resume H:\FileCheckBackup\FC-...
  FileCheck.exe restore H:\FileCheckBackup\FC-... --conflict skip

安全边界
--------
- scan 和 backup 不删除源文件。
- 删除源文件与覆盖恢复都有独立风险确认。
- FileCheck 不清理 Recent、浏览器历史、Office/WPS MRU、USBSTOR、注册表等系统使用痕迹。
- 当前恢复聚焦普通文件内容、路径、大小、SHA-256 和基础 mtime；不承诺完整还原 ACL/EFS/ADS/硬链接/稀疏文件/重解析点等高级元数据。

第三方组件许可说明见 THIRD-PARTY-NOTICES.txt。
