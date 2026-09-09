# FileCheck

FileCheck 是一个面向 Windows 终端的离线文件自查、备份与恢复工具，用于完成：**快速索引 → 关键词扫描 → 人工核对 → 批量目录备份 → 完整性验证 → 源文件安全删除 → 按原路径恢复**。

当前正式版本：**v0.2.1**。

FileCheck 同时提供 **GUI 图形界面** 和 **CLI 命令行**。两种入口共用同一套核心逻辑、扫描规则、Everything 专用索引、备份格式和 SHA-256 校验机制。

> **推荐流程：正式操作前人工清理 → 设置统一备份根目录 → 创建/更新专用 Everything 索引 → 扫描候选 → 人工核对 → 创建目录备份 → 检查备份 → 按需单独执行源文件删除 → 必要时恢复。**
>
> `scan` 和 `backup` 永远不会自动删除源文件。关键词命中只表示“候选”，不代表违规或最终分类结论。

## v0.2.1 发布包

正式 Release 提供 3 个便携包：

- `FileCheck-v0.2.1-gui-x64.zip`：GUI 完整版，面向 Windows 7 SP1 / Windows 10 / Windows 11 64 位，**普通用户推荐**；包内同时包含 x64 CLI。
- `FileCheck-v0.2.1-cli-x64.zip`：纯命令行版，面向 Windows 7 SP1 / Windows 10 / Windows 11 64 位。
- `FileCheck-v0.2.1-cli-x86.zip`：纯命令行兼容版，面向 Windows 7 SP1 32 位。

所有便携包均内置对应架构的 Everything 和 ES，解压后即可运行，不需要安装 Python，也不要求系统预先安装 Everything。

> GUI/x64 CLI 使用 Python 3.8.10 x64 + PyInstaller 5.13.2 的 Windows 7 兼容构建基线；x86 CLI 使用 Python 3.8.10 x86 + PyInstaller 5.13.2。CI 会执行 Python 3.8 兼容、完整回归、现代 Windows GUI 构造、EXE smoke test 和最终 ZIP 校验。正式部署到具体 Windows 7 机器前，仍建议在目标环境做一次实际运行验证。

## v0.2.1 修复说明

v0.2.0 在深层目录备份时，原子复制临时文件会重复原文件名并附加 UUID。某些正式目标路径本身低于传统 Windows `MAX_PATH`，但临时文件路径可能被额外推到 260 字符附近，在 Windows 7 上表现为：

```text
[Errno 2] No such file or directory
```

v0.2.1 将备份和恢复临时文件改为固定长度短名称，例如：

```text
.fc-b-65738f732c5e459e.part
.fc-r-0123456789abcdef.part
```

临时文件仍位于最终目标同一目录，因此原子替换、异常清理和 SHA-256 校验逻辑不变。已有 v0.2.0 备份批次无需迁移。

## 选择哪个版本

| 使用场景 | 推荐包 |
| --- | --- |
| 日常人工操作、希望使用图形界面 | `FileCheck-v0.2.1-gui-x64.zip` |
| 64 位 Windows 上脚本化、批处理或高级诊断 | `FileCheck-v0.2.1-cli-x64.zip` |
| Windows 7 SP1 32 位旧机器 | `FileCheck-v0.2.1-cli-x86.zip` |

GUI 包中的高级命令行入口位于：

```text
advanced\FileCheck.exe
```

GUI 和这个 CLI 共用 GUI 便携包根目录，因此会复用同一套：

```text
config\rules.json
runtime\everything\Everything-FileCheck.db
runtime\everything\index-config.json
runtime\settings.json
scan-results\
```

不要把 `advanced\FileCheck.exe` 单独复制到别处运行，否则它将无法继续识别原便携包根目录。

## 核心特性

- **GUI + CLI 双入口**：普通操作优先使用 GUI，高级用户可继续使用 CLI。
- **独立便携 Everything 索引**：使用名为 `FileCheck` 的专用 Everything 实例，不依赖、不修改用户另外安装的默认 Everything。
- **统一数据库文件名**：索引数据库固定为 `runtime\everything\Everything-FileCheck.db`。
- **NTFS 快速索引**：本地 NTFS 固定磁盘优先使用 MFT/USN；不安装永久 Windows 服务。
- **全部运行数据本地化**：配置、索引、操作状态和扫描结果都保存在 FileCheck 便携目录下。
- **单一备份根目录**：设置一个统一备份根目录，每次备份创建独立 `FC-YYYYMMDD-HHMMSS-*` 批次。
- **目录备份**：按原始盘符和目录结构镜像保存，不创建新的 ZIP 备份。
- **同名文件安全**：不同绝对路径下的同名文件保持各自目录结构，不会互相覆盖。
- **SHA-256 完整性保护**：备份、删除前复核和恢复均使用 SHA-256 验证。
- **安全删除**：删除是独立高风险操作，备份完成后不会自动触发删除。
- **安全恢复**：恢复前完整验证备份；默认 `skip`，不会覆盖已经存在的文件。
- **恢复异常继续处理**：覆盖恢复时遇到无法替换的单个文件会跳过、记录并继续处理其他文件。

# 正式使用前准备

**以下人工步骤请在 FileCheck 正式扫描、备份和删除操作之前完成。**

清理 Windows 临时文件、Recent 快捷方式和跳转列表记录会删除相应历史记录，请先确认这些记录不再需要，并按本单位制度执行。

先清空 **Windows 回收站**，然后依次处理以下位置。

## 1. 清理当前用户临时目录

`Win + R` → 输入：

```text
%temp%
```

全选删除。正在被系统或应用占用、无法删除的文件直接跳过即可。

## 2. 清理系统级临时目录

`Win + R` → 输入：

```text
C:\Windows\Temp
```

同样全选删除，无法删除的占用文件直接跳过。

## 3. 清理最近使用快捷方式目录

`Win + R` → 输入：

```text
recent
```

全选删除。

## 4. 清理 AutomaticDestinations

打开：

```text
%APPDATA%\Microsoft\Windows\Recent\AutomaticDestinations
```

删除其中不再需要的跳转列表记录。

## 5. 清理 CustomDestinations

打开：

```text
%APPDATA%\Microsoft\Windows\Recent\CustomDestinations
```

删除其中不再需要的跳转列表记录。

> FileCheck **不会自动执行以上 Windows 清理操作**，也不会自动处理浏览器历史、USBSTOR、Office/WPS MRU 或注册表记录。以上内容只是正式使用前的独立人工准备步骤。

# GUI 快速使用

## 1. 解压并启动

保持 ZIP 内原有目录结构，推荐右键：

```text
FileCheck-GUI.exe → 以管理员身份运行
```

GUI 会检测管理员权限。非管理员模式仍可查看部分信息、使用已有索引扫描、执行备份，以及使用 `skip/rename` 恢复；但会限制索引创建/更新、源文件删除和覆盖恢复等高风险操作。

## 2. 设置统一备份根目录

首次使用先进入 **设置** 页面，选择唯一的备份根目录，例如：

```text
H:\FileCheckBackup
```

后续每次备份会自动创建独立批次：

```text
H:\FileCheckBackup\
├─ FC-20260909-090000-xxxxxxxx\
│  ├─ manifest.json
│  └─ files\...
├─ FC-20260909-103000-yyyyyyyy\
│  ├─ manifest.json
│  └─ files\...
└─ ...
```

源文件删除和恢复页面会自动扫描这个备份根目录下的直接子目录，并识别其中存在 `manifest.json` 的有效备份批次。

## 3. 创建 / 更新索引

进入 **扫描** 页面，点击“创建 / 更新索引”。

GUI 不要求用户手工设置扫描范围，按当前配置对本地固定磁盘建立 FileCheck 专用索引。程序目录和备份根目录会自动排除。

数据库固定保存为：

```text
runtime\everything\Everything-FileCheck.db
```

只有数据库真实存在且非空、索引状态记录与数据库路径一致时，GUI 才会显示“索引就绪”并允许扫描。

## 4. 扫描候选文件

扫描结果默认保存为：

```text
scan-results\scan-results-YYYYMMDD-HHMMSS.json
scan-results\scan-results-YYYYMMDD-HHMMSS.csv
```

GUI 页面只显示文件名，可通过右侧“打开位置”按钮直接打开对应目录。

当前快速扫描主要依据 Everything 的**文件名和路径索引**，不会读取 DOCX/PDF/XLSX/PPTX 等文档正文。

## 5. 人工核对扫描结果

进入 **扫描结果** 页面查看候选列表，也可以打开 CSV / JSON 做进一步人工核对。

FileCheck 不要求逐文件确认；核对完成后可以将本次候选批量备份。

## 6. 创建备份

进入 **备份** 页面，选择本次扫描结果并执行备份。

正式备份批次结构：

```text
<backup-root>\FC-...\
├─ manifest.json
└─ files\...
```

复制过程中使用 `.FC-....incomplete` 暂存目录。每个文件先复制到同目录短临时文件并同步落盘，再原子替换为正式备份文件。只有全部复制完成并通过大小 + SHA-256 校验后，才发布为正式 `FC-*` 批次。

不同绝对路径下的同名文件会保留各自的原始目录结构，不会互相覆盖。

## 7. 源文件删除

**源文件删除是单独的高风险操作，不会在备份完成后自动执行。**

进入 **源文件删除** 页面后，程序会自动发现统一备份根目录下的有效 `FC-*` 批次；也可以手动选择移动过的旧备份目录。

第一次删除会执行：

```text
完整验证整个备份
→ 对全部源文件执行 size + SHA-256 强复核
→ 任一异常则整批删除不启动
→ 用户明确确认
→ 根据预检快照逐文件删除 manifest 指定的 source_path
```

删除状态单独保存在：

```text
source-removal.json
```

无法删除或重新出现的文件会记录到：

```text
not-deleted.txt
```

Windows 的“只读”属性会自动处理；ACL 权限、文件占用、杀毒软件拦截等真实错误不会被绕过，而是记录后继续处理其他文件。

## 8. 恢复

进入 **恢复** 页面后选择备份批次和冲突策略：

```text
skip       默认/推荐：目标存在就保留，不覆盖
rename     恢复为另一个文件名
overwrite  校验临时文件后替换目标
```

恢复前会重新完整验证备份。

实际恢复过程：

```text
恢复前完整验证备份
→ 复制到目标目录短临时文件
→ 临时文件 size + SHA-256 校验
→ 原子替换/落盘
→ 最终目标再次 size + SHA-256 校验
```

`overwrite` 模式下，如果某个已有文件因为占用、权限等原因无法覆盖，该文件会被跳过并记录，其他文件继续恢复。

跳过/失败报告保存在备份批次中，例如：

```text
restore-skipped-YYYYMMDD-HHMMSS.txt
```

# CLI 使用

纯 CLI 包直接运行：

```text
FileCheck.exe
```

GUI 包则使用：

```text
advanced\FileCheck.exe
```

无参数启动后进入交互式菜单：

```text
1. 环境检查与索引创建
2. 扫描文件列表
3. 核对扫描结果
4. 创建备份 / 继续未完成的备份任务
5. 检查备份
6. 删除源文件 / 继续未完成的删除任务
7. 恢复备份文件到源路径
0. 退出
```

推荐以管理员身份运行 CLI，尤其是创建 NTFS MFT/USN 索引、删除源文件和执行覆盖恢复时。

## 高级 CLI 命令

```powershell
FileCheck.exe doctor
FileCheck.exe index --drive C:\ --drive D:\ --backup-root H:\FileCheckBackup
FileCheck.exe scan
FileCheck.exe backup --from-scan scan-results.json --dest H:\FileCheckBackup
FileCheck.exe verify H:\FileCheckBackup\FC-...
FileCheck.exe remove-sources H:\FileCheckBackup\FC-...
FileCheck.exe remove-resume H:\FileCheckBackup\FC-...
FileCheck.exe restore H:\FileCheckBackup\FC-... --conflict skip
FileCheck.exe selftest
```

`selftest` 用于开发/回归测试，不属于正常业务流程。

# 扫描规则

扫描关键词和扩展名配置位于：

```text
config\rules.json
```

修改后重新执行扫描即可生效。

当前快速扫描只依据 Everything 返回的文件名和路径，不解析文档正文。

# manifest.json 与备份事实

每个备份文件记录：

```text
source_path
backup_path
size
mtime_ns
sha256
```

`manifest.json` 只记录备份事实，不记录源文件删除状态，也不会因为后续删除或恢复操作而修改。

源文件删除状态单独写入：

```text
source-removal.json
```

# 重要安全原则

- 扫描结果必须人工核对。
- 备份和源文件删除必须分成两个独立动作。
- 删除前会再次验证完整备份与源文件状态。
- 恢复前会完整验证备份。
- `manifest.json` 是备份事实记录，不随删除状态改变。
- 不绕过 Windows ACL、文件占用或安全软件限制。
- 正式删除操作前，确认备份目标介质稳定、空间充足，并建议抽查关键文件。

# 便携包主要目录

GUI 包：

```text
FileCheck-GUI.exe
README.md
advanced\FileCheck.exe
app\
config\rules.json
tools\Everything.exe
tools\es.exe
runtime\
scan-results\
SHA256SUMS.txt
THIRD-PARTY-NOTICES.txt
```

CLI 包：

```text
FileCheck.exe
README.md
config\rules.json
tools\Everything.exe
tools\es.exe
runtime\
scan-results\
SHA256SUMS.txt
THIRD-PARTY-NOTICES.txt
```

# 第三方组件

FileCheck 便携包包含第三方组件 Everything / ES 和 CustomTkinter。相关许可与说明见：

```text
THIRD-PARTY-NOTICES.txt
```
