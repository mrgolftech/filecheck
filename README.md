# FileCheck

FileCheck 是一个面向 Windows 终端的离线文件自查工具，用于：**快速索引 → 关键词扫描 → 人工核对 → 批量目录备份 → 完整性验证 → 源文件安全删除 → 按原路径恢复**。

> **V0.1.1 推荐流程：专用 Everything 索引 → 扫描候选 → 人工核对 JSON/CSV → 创建目录备份 → 检查备份 → 删除源文件 → 必要时恢复。**
>
> `scan` 和 `backup` 永远不会删除源文件。关键词命中仅表示“候选”，不代表违规或最终分类结论。

## V0.1.1 发布包

正式 Release 提供 3 个便携包：

- `FileCheck-v0.1.1-win10plus-x64.zip`：Windows 10 / 11 64 位
- `FileCheck-v0.1.1-win7-x64.zip`：Windows 7 SP1 64 位
- `FileCheck-v0.1.1-win7-x86.zip`：Windows 7 SP1 32 位

解压后直接运行，不需要安装 Python，也不要求系统预先安装 Everything。

## V0.1.1 核心特性

- **独立便携索引**：发布包内置 Everything 1.4.1.1032 和 ES 1.1.0.37，使用名为 `FileCheck` 的专用实例，不依赖、不修改用户另外安装的 Everything。
- **NTFS 快速索引**：本地 NTFS 固定磁盘优先使用 MFT/USN；非 NTFS 或显式目录使用兼容目录索引。
- **全部运行数据本地化**：索引配置、数据库、操作状态、扫描结果都保存在 FileCheck 程序目录下。
- **目录备份**：V0.1.1 新建备份只使用目录结构，不创建 ZIP，保留原始盘符和目录层级，便于人工检查。
- **可继续备份**：备份复制中断后可以继续未完成任务。
- **manifest 不可变**：`manifest.json` 只记录备份事实；删除状态单独写入 `source-removal.json`。
- **安全删除**：删除前执行整批 SHA-256 强校验；确认后使用快速元数据检查避免重复整文件哈希；只读属性自动处理，ACL/占用等真实错误仍安全失败。
- **安全恢复**：恢复前再次完整验证备份；默认 `skip`，不覆盖已经存在的文件；恢复过程使用临时文件、SHA-256 校验和原子替换。
- **旧备份兼容**：V0.1.0 ZIP 需要先人工解压，解压后的 `manifest.json + files\` 可由 V0.1.1 校验和恢复。

## 便携目录

正式包解压后建议保持完整目录结构：

```text
FileCheck\
├─ FileCheck.exe
├─ config\
│  └─ rules.json
├─ tools\
│  ├─ Everything.exe
│  └─ es.exe
├─ runtime\
│  ├─ everything\
│  │  ├─ Everything.ini
│  │  ├─ Everything-FileCheck.db
│  │  └─ index-config.json
│  └─ operations\
└─ scan-results\
```

`runtime` 和 `scan-results` 会在首次使用时自动创建。

## 正式使用前准备

以下步骤是推荐的人工准备流程。清理 Windows 临时文件、Recent 快捷方式和跳转列表记录会删除相应历史记录，请先确认这些记录不再需要，并按本单位制度执行。

### 1. 清理 Windows 临时目录和最近记录

先清空 Windows 回收站，然后依次处理：

1. **清理当前用户临时目录**

   `Win + R` → 输入：

   ```text
   %temp%
   ```

   全选删除。正在被系统或应用占用、无法删除的文件直接跳过即可。

2. **清理系统级临时目录**

   `Win + R` → 输入：

   ```text
   C:\Windows\Temp
   ```

   同样全选删除，无法删除的占用文件直接跳过。

3. **清理最近使用快捷方式目录**

   `Win + R` → 输入：

   ```text
   recent
   ```

   全选删除。

4. **清理 AutomaticDestinations**

   ```text
   %APPDATA%\Microsoft\Windows\Recent\AutomaticDestinations
   ```

5. **清理 CustomDestinations**

   ```text
   %APPDATA%\Microsoft\Windows\Recent\CustomDestinations
   ```

> FileCheck 程序本身不会自动执行以上 Windows 清理操作，也不会自动处理浏览器历史、USBSTOR、Office/WPS MRU 或注册表记录。以上内容只是使用前的独立人工准备步骤。

## 启动方式

推荐右键：

```text
FileCheck.exe → 以管理员身份运行
```

交互式主流程要求管理员权限，主要用于 NTFS MFT/USN 快速索引，以及受保护路径下的删除/恢复操作。

高级 CLI（例如 `--help`、`selftest`）仍可单独运行。

## 主菜单与使用说明

无参数启动 `FileCheck.exe` 后，V0.1.1 主菜单为：

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

### 1. 环境检查与索引创建

首次使用先执行第 1 项。

程序会检测磁盘类型，并提示选择索引范围。典型输入：

```text
直接回车 / A = 所有本地固定磁盘
C,D          = 只索引 C: 和 D:
C D          = 同样可以
```

默认不会自动把可移动 USB 磁盘包含进“全部本地固定磁盘”；需要时可以显式选择。

随后设置统一备份根目录。程序目录和备份根目录会自动从索引及后续扫描结果中排除。

建立索引时使用独立 `FileCheck` Everything 实例，数据库保存到：

```text
runtime\everything\Everything-FileCheck.db
```

索引过程不启动永久 Windows 服务，也不会弹出 Everything 搜索窗口。

### 2. 扫描文件列表

进入第 2 项时，程序会先显示当前实际生效的：

- 关键词分组；
- 文件扩展名；
- `config\rules.json` 的完整路径。

如果要修改扫描关键词或扩展名，直接编辑：

```text
config\rules.json
```

保存后重新执行扫描即可。

扫描结果默认输出：

```text
scan-results\scan-results-YYYYMMDD-HHMMSS.json
scan-results\scan-results-YYYYMMDD-HHMMSS.csv
```

JSON 用于后续程序处理，CSV 便于人工核对。当前快速扫描主要依据 Everything 文件名/路径索引，不读取 DOCX/PDF/XLSX/PPTX 等文档正文。

### 3. 核对扫描结果

建议先查看 CSV/JSON，确认关键词命中的候选文件是否确实需要备份。

FileCheck 不要求逐文件确认；核对完成后可将整批候选统一备份。

### 4. 创建备份 / 继续未完成的备份任务

进入第 4 项后：

```text
1. 创建新备份
2. 继续未完成的备份任务
0. 返回主菜单
```

V0.1.1 新建备份只使用**目录备份**。

例如：

```text
C:\ProjectA\报告.pdf
C:\ProjectB\报告.pdf
D:\资料\报告.pdf
```

会分别备份为：

```text
files\C\ProjectA\报告.pdf
files\C\ProjectB\报告.pdf
files\D\资料\报告.pdf
```

不同目录中的同名文件不会互相覆盖；只有完全相同的绝对源路径才去重。

正式备份批次：

```text
<backup-root>\FC-...\
├─ manifest.json
└─ files\...
```

复制过程中使用 `.FC-....incomplete` 暂存目录。只有复制完成并通过大小 + SHA-256 校验后，才会发布为正式 `FC-*` 批次。

### 5. 检查备份

第 5 项会对备份批次逐文件执行：

```text
文件存在性
→ 文件大小
→ SHA-256
```

建议在删除源文件前，先用资源管理器人工查看备份目录，再执行一次第 5 项完整验证。

## manifest.json

每个备份文件记录：

```text
source_path
backup_path
size
mtime_ns
sha256
```

`manifest.json` 不记录 `source_removed`，不会因后续删除或恢复而修改。

## 6. 删除源文件 / 继续未完成的删除任务

删除是独立的显式操作，备份成功本身不会自动删除任何源文件。

### 第一次删除

流程为：

```text
完整验证整个备份
→ 对全部源文件执行一次 size + SHA-256 强复核
→ 任一源文件异常：整批删除不启动
→ 全部一致：提示输入 YES
→ YES 后快速确认备份/manifest 未变化
→ 每个源文件按预检元数据快照快速检查
→ 删除 manifest 明确列出的 source_path
```

为提高大量文件删除速度，`YES` 之后不会再给每个文件重复计算一次完整 SHA-256；而是检查 size、mtime、文件标识等预检快照。如果在整批 SHA-256 复核后文件发生变化，该文件会被跳过并标记为失败。

Windows 的“只读”属性不会阻止删除：程序会只清除只读/写保护位后删除；如果实际问题是 ACL 权限、文件占用、杀毒软件拦截等，则仍会标记为 `failed`。

如果进入真正删除阶段后发现某个源文件已经不存在，则记录为：

```text
already_absent
```

并继续处理其他文件。

删除状态保存在备份批次内：

```text
FC-...\
├─ manifest.json
├─ source-removal.json
├─ not-deleted.txt        # 仅有失败/reappeared 项时存在
└─ files\...
```

### 继续未完成删除

继续删除时会重新完整验证备份，并对待重试的源文件重新做强校验，因此即使距离第一次删除已经过去较长时间，也不会直接使用旧校验结果。

如果一个已经 `deleted` 或 `already_absent` 的原路径后来重新出现，程序会标记为：

```text
reappeared
```

并禁止自动再次删除，避免把后来生成的新文件误删。

## 7. 恢复备份文件到源路径

V0.1.1 恢复只接受已经展开为目录的备份批次。

恢复冲突策略：

```text
1 = skip       默认/推荐：目标存在就保留，不覆盖
2 = rename     恢复为另一个文件名
3 = overwrite  校验临时文件后原子替换目标
```

选择策略后，程序会先提示：

```text
正在执行恢复前备份完整性校验（SHA-256）……
校验通过后将自动开始恢复。
```

这是正常流程，不是程序卡死。备份文件较多或较大时，全量 SHA-256 会需要一定时间。

实际恢复过程为：

```text
恢复前完整验证备份
→ 复制到目标目录临时文件
→ 临时文件 size + SHA-256 校验
→ 原子替换/落盘
→ 最终目标再次 size + SHA-256 校验
```

默认 `skip` 策略下，被跳过的文件会记录到：

```text
<backup-batch>\restore-skipped.txt
```

如果目标文件内容与备份一致，报告会明确标记“内容与备份一致”；如果不同或无法确认，则只跳过，不覆盖。

### 恢复 V0.1.0 旧 ZIP

V0.1.1 不直接读取 ZIP 文件。如需恢复 V0.1.0 旧 ZIP：

1. 使用 Windows 或第三方工具完整解压；
2. 确认解压目录包含 `manifest.json` 和 `files\`；
3. 在第 7 项选择这个**解压后的目录**。

旧 manifest 即使仍包含 `"mode": "zip"`，只要已经完整解压，V0.1.1 仍可按目录方式校验和恢复。

## 高级 CLI

主菜单之外保留高级命令：

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

`selftest` 是开发/回归用的临时文件回环测试，不再放进普通菜单。

## 安全边界

FileCheck 当前聚焦普通文件的内容字节、原始绝对路径、文件大小、SHA-256 和基础 mtime。

当前不承诺完整保留/恢复 ACL、EFS、ADS、硬链接、稀疏文件、重解析点、所有者、审计等高级 Windows 文件系统元数据。

FileCheck **不是痕迹清理工具**，不会清理 Recent、浏览器历史、Office/WPS MRU、USBSTOR、注册表等系统使用记录。

## 开发与测试

源码环境：

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
filecheck selftest
```

构建路线：

- Windows 10/11 x64：Python 3.12 + PyInstaller 6
- Windows 7 x64：Python 3.8.10 x64 + PyInstaller 5.13.2
- Windows 7 x86：Python 3.8.10 x86 + PyInstaller 5.13.2，并校验 PE machine=`0x014C`

正式发布包均包含对应架构的 Everything / ES，并在 GitHub Actions 中执行回归测试、`selftest`、可执行文件 smoke test 和便携包内容检查。

## 第三方组件

便携发布包包含 voidtools 的 Everything 和 ES。许可及来源说明见 `THIRD-PARTY-NOTICES.txt`。