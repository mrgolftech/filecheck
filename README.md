# FileCheck

FileCheck 是一个面向 Windows 终端的离线文件自查、批量目录备份、完整性验证、源文件安全删除和原路径恢复工具。

> **V0.1.1 推荐流程：专用 Everything 索引 → 只读扫描 → 人工核对 JSON/CSV → 目录方式批量备份 → 人工检查 → 再次全量 SHA-256 验证 → 显式删除 manifest 中的源文件 → 必要时原路径恢复。**
>
> `scan` 和 `backup` 永远不删除源文件。关键词命中只表示候选，不代表违规或最终分类结论。

## V0.1.1 设计原则

- **便携运行**：正式 Windows 包同时携带 `FileCheck.exe`、`Everything.exe`、`es.exe` 和默认规则。
- **独立索引**：FileCheck 启动名为 `FileCheck` 的专用 Everything 1.4 实例，不依赖也不修改用户另行安装的默认 Everything 实例。
- **目录备份唯一格式**：V0.1.1 不创建 ZIP，也不直接读取 ZIP。
- **恢复清单不可变**：`manifest.json` 只记录备份创建事实，不记录 `source_removed`。
- **删除状态独立**：删除后写 `source-removal.json`；有失败项时额外写 `not-deleted.txt`。
- **只删除明确文件**：仅删除 manifest 中逐项列出的 `source_path`，不递归删除父目录，也不自动删除空目录。
- **全量校验优先**：正式备份发布、源文件删除、恢复前均执行完整性校验。
- **可恢复失败**：大量文件删除时，单个文件被占用/权限不足会跳过并继续；关闭占用程序后可继续失败项。

## 便携目录

正式包解压后建议保持：

```text
FileCheck\
├─ FileCheck.exe
├─ config\
│  └─ rules.json
├─ tools\
│  ├─ Everything.exe
│  └─ es.exe
├─ runtime\
│  └─ everything\
│     ├─ Everything.ini
│     ├─ Everything.db
│     └─ index-config.json
└─ scan-results\
```

`runtime` 和 `scan-results` 会在运行过程中自动创建。

## 推荐交互流程

无参数启动：

```text
FileCheck.exe
```

当前菜单按生命周期组织：

```text
1. 环境与索引
2. 扫描文件
3. 核对扫描结果（JSON / CSV）
4. 创建目录备份
5. 检查并再次验证备份
6. 删除源文件 / 继续未完成删除
7. 恢复备份文件到各自原路径
8. 继续未完成的备份复制任务
9. 运行本机自检
10. 高级命令帮助
0. 退出
```

### 1. 环境与索引

首次使用选择要纳入自查的磁盘/目录，并设置统一备份根目录。FileCheck 会创建自己的 Everything 配置，自动排除程序目录和备份根目录，建立/重建专用索引，并将索引数据保存在 `runtime\everything`。

### 2. 扫描

默认仅按**文件名**匹配规则关键词；可显式选择同时匹配完整目录路径。

输出：

```text
scan-results\scan-results-YYYYMMDD-HHMMSS.json
scan-results\scan-results-YYYYMMDD-HHMMSS.csv
```

JSON 是后续自动处理输入，CSV 便于人工核对。

### 3. 创建目录备份

扫描结果默认按**全部候选文件**批量处理，不要求逐文件确认。

例如：

```text
C:\ProjectA\报告.pdf
C:\ProjectB\报告.pdf
D:\资料\报告.pdf
```

分别映射为：

```text
files\C\ProjectA\报告.pdf
files\C\ProjectB\报告.pdf
files\D\资料\报告.pdf
```

相同文件名不会互相覆盖；只有完全相同的绝对源路径才去重。

正式批次：

```text
<backup-root>\FC-...\
├─ manifest.json
└─ files\...
```

复制期间先使用 `.FC-....incomplete` 暂存目录。只有完整复制并通过全量大小 + SHA-256 验证后，才发布为正式 `FC-*` 批次。

## manifest.json

V0.1.1 manifest 记录每个普通文件的核心恢复信息：

```text
source_path
backup_path
size
mtime_ns
sha256
```

`manifest.json` 不记录 `source_removed`。备份事实和后续删除状态属于两个不同生命周期。

## 源文件删除

建议在目录备份完成后先人工查看 `files\`，再运行一次独立 `verify`，最后才进入删除。

删除入口会再次执行：

```text
完整验证备份
→ 全部源文件重新检查 size + SHA-256
→ 任一源文件异常：删除阶段不启动
→ 全部一致：批次级 YES 确认
→ 每个文件删除前再次即时复核
→ 只 unlink manifest 中的 source_path
```

删除状态保存在同一备份批次内：

```text
FC-...\
├─ manifest.json
├─ source-removal.json
├─ not-deleted.txt        # 只有失败项时存在
└─ files\...
```

如果某个文件因锁定、权限或变化而无法删除，该文件标记为 `failed`，其余文件继续处理；关闭占用程序后可以继续失败项。

如果此前已经删除的路径后来又出现，resume 会标记为 `reappeared`，不会自动再次删除，以避免误删新生成的数据。

## 恢复

V0.1.1 恢复只接受**目录备份**。恢复前先完整验证整个备份，再按照各自 `source_path` 恢复。

冲突策略：

```text
skip       原路径存在时跳过（默认/推荐）
rename     恢复成另一个名称
overwrite  先写同目录临时文件并校验，成功后原子替换
```

### 恢复 V0.1.0 旧 ZIP

V0.1.1 本身不包含 ZIP 读取/解压逻辑。如果需要恢复旧 ZIP：

1. 使用 Windows/第三方工具完整解压；
2. 确认解压目录含 `manifest.json` 和 `files\`；
3. 将**解压后的目录**交给 FileCheck。

旧 manifest 中即使仍是 `"mode": "zip"`，只要已经完整解压为正常目录，V0.1.1 会按目录方式校验和恢复。

## 高级 CLI

典型命令：

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

`migrate` / `migrate-resume` 作为兼容的高级别名保留，但不属于推荐的交互式主流程。

## 扫描规则

默认规则：

```text
config\rules.json
```

扫描结果只写入规则文件名及其 SHA-256，不写本机规则绝对路径。

当前快速扫描主要基于 Everything 文件名/路径索引，不读取 DOCX/PDF/XLSX/PPTX 等文档正文。正文深度扫描属于后续版本能力。

## 安全边界

FileCheck 当前聚焦普通文件：内容字节、原始绝对路径、文件大小、SHA-256 和基础 mtime。

当前不承诺完整保留/恢复 ACL、EFS、ADS、硬链接、稀疏文件、重解析点、所有者、审计等高级 Windows 文件系统元数据。

FileCheck **不是痕迹清理工具**。它不会清理 Recent、浏览器历史、Office/WPS MRU、USBSTOR、注册表等系统使用记录。

## 开发与测试

源码环境：

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
filecheck selftest
```

V0.1.1 CI 覆盖 Windows / Ubuntu、Python 3.10 / 3.12。Windows 7 兼容包继续采用 Python 3.8.10 + PyInstaller 5.13.2 构建路线，并要求正式发布前进行真实 Win7 实机回归。

## 第三方组件

便携发布包包含 voidtools 的 Everything 和 ES。许可及来源说明见 `THIRD-PARTY-NOTICES.txt`。
