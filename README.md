# FileCheck

FileCheck 是一个面向 Windows 终端的离线文件自查、批量备份、完整性验证、源文件安全移除和原路径恢复工具。

> **推荐主流程：只读扫描 → 目录方式批量备份 → 人工检查备份目录 → 再次全量 SHA-256 验证 → 显式删除已验证备份对应的源文件 → 必要时按 manifest 原路径恢复。**
>
> `scan` 和 `backup` 永远不删除源文件。源文件删除只能通过明确的删除/迁移功能进入，并在删除前重新验证整个备份、重新核对源文件，最后还需要一次批次级确认。

## V0.1.0 Win64 发布版

V0.1.0 提供可直接运行的 Win64 便携包，无需目标电脑安装 Python。发布包结构：

```text
FileCheck-win64\
├─ FileCheck.exe
├─ config\
│  └─ rules.json
├─ tools\
│  └─ es.exe
├─ README-WIN64.txt
├─ THIRD-PARTY-NOTICES.txt
└─ SHA256SUMS.txt
```

V0.1.0 已内置官方 **Everything Command-line Interface (ES) 1.1.0.37 x64**，位于 `tools\es.exe`。Everything 本体仍需要在 Windows 上安装、启动并完成索引。

ES 为 voidtools 项目，按 MIT License 再分发；许可文本随发布包提供于 `THIRD-PARTY-NOTICES.txt`。

---

# 正式使用前准备

以下步骤是推荐的人工准备流程。清理 Windows 临时文件、Recent 快捷方式和跳转列表记录会删除相应历史记录，请先确认这些记录不再需要，并按本单位制度执行。

## 1. 清理 Windows 临时目录和最近记录

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

## 2. 确认 ES CLI

V0.1.0 Win64 发布包已经包含：

```text
tools\es.exe
```

使用前请确认该文件存在。FileCheck 在打包运行时会优先查找 **FileCheck.exe 所在目录下的 `tools\es.exe`**，因此即使从其他工作目录启动，也能找到随包提供的 ES。

如果使用源码开发版，也可以手工放置 `tools\es.exe`，或者把 ES 加入 PATH / 设置 `FILECHECK_ES` 环境变量。

## 3. 设置 Everything 索引

建议在正式扫描前先整理 Everything 索引：

1. 打开 Everything。
2. 进入 **工具 → 选项 → 排除列表**。
3. 勾选：
   - **排除隐藏文件和目录**；
   - **排除系统文件和目录**。
4. 确认需要检查/备份的目录**没有被误加入排除列表**。
5. 如果待检查目录没有由现有 NTFS 索引覆盖，可在 **索引 → 文件夹** 中添加需要检查/备份的目录；如果已经由 NTFS 索引覆盖，则无需重复添加。
6. 在 **索引** 相关选项中执行重建/强制重建索引，确保 FileCheck 使用的是最新索引。

---

# 推荐使用流程

下面是 V0.1.0 推荐的实际操作顺序，适合“先备份、再独立验证、最后才删除源文件”的使用习惯。

## 第一步：检查运行环境

启动：

```text
FileCheck.exe
```

主菜单选择：

```text
1. 检查 Everything / ES 环境
```

确认 Everything 和 ES 均检查通过。

## 第二步：扫描

主菜单选择：

```text
2. 扫描并处理（推荐入口）
```

扫描范围建议选择：

```text
1. Everything 当前已索引的全部范围
```

当程序询问：

```text
关键词是否同时匹配目录路径
```

推荐选择：

```text
N
```

这样默认只按文件名进行关键词匹配，避免因为父目录名称包含某个关键词而扩大候选范围。

扫描完成后会生成类似：

```text
%LOCALAPPDATA%\FileCheck\scan-results-20260907-xxxxxx.json
```

如果准备采用“扫描 → 备份 → 再验证 → 删除源文件”的分步流程，在扫描后处理菜单选择：

```text
5. 只保存扫描结果，暂不处理
```

记下扫描 JSON 的完整路径。

## 第三步：使用扫描 JSON 批量备份

回到主菜单选择：

```text
3. 使用已有扫描结果批量备份
```

输入刚才生成的 `scan-results-*.json` 完整路径，然后选择统一备份目标目录。

推荐使用 **目录方式批量备份全部候选**。

程序会：

```text
逐文件复制
→ 每个文件计算 SHA-256
→ 完整批次再次逐文件验证
→ 验证通过后才发布正式备份批次目录
```

大量文件任务会建立可续传操作状态。如果复制过程中出现文件消失、权限问题、移动盘瞬断或用户中断，可通过主菜单的“继续未完成的备份 / 迁移”继续，不必重新复制已经校验通过的暂存文件。

## 第四步：人工检查备份目录

目录备份**保持源盘符、源目录层级和原始文件名**，便于直接使用资源管理器人工检查。

例如源文件：

```text
G:\work\ProjectA\参考资料\报告.pdf
```

备份为：

```text
<备份批次>\files\G\work\ProjectA\参考资料\报告.pdf
```

不会把文件改成哈希文件名，也不会把所有同名文件拍平到一个目录。

## 第五步：再次验证已有备份

人工检查后，主菜单选择：

```text
5. 验证已有备份
```

输入刚才的完整备份批次目录，例如：

```text
H:\backup\FC-20260907-xxxxxx-xxxxxxxx
```

程序会重新对整个备份执行大小和 SHA-256 全量校验。

## 第六步：删除电脑中的源文件

确认备份内容、目录结构和再次校验都没有问题后，主菜单选择：

```text
7. 删除已验证备份对应的源文件
```

该功能不会仅依赖你刚刚执行过的“验证已有备份”。真正删除前仍会重新执行：

```text
完整验证整个备份
→ 读取 manifest.json
→ 逐个重新检查源文件大小
→ 逐个重新计算源文件 SHA-256
→ 任意一个文件不一致：不启动删除阶段
→ 全部一致：要求输入 YES
→ 只删除 manifest 中明确列出的 source_path
```

注意：

- 不递归删除父目录；
- 不删除同目录中的其他非候选文件；
- 不自动删除空目录；
- 文件被占用或权限不足时，不强制解锁、不杀进程；
- 部分删除失败会保存迁移状态，可关闭占用程序后继续。

## 第七步：强制重建 Everything 索引并复查

删除源文件完成后，重新进入 Everything：

```text
工具 → 选项 → 索引
```

执行**强制重建索引**，然后再次搜索/检查，确认 Everything 索引已经反映当前实际文件状态。

## 第八步：妥善保存备份批次

请完整保存整个备份批次目录，例如：

```text
H:\backup\FC-20260907-xxxxxx-xxxxxxxx\
```

其中包括：

```text
manifest.json
files\...
```

不要只单独保留部分文件。`manifest.json` 是后续自动校验和恢复到原始路径的权威清单。

---

# 将来需要恢复时

启动 `FileCheck.exe`，主菜单选择：

```text
6. 从备份恢复到原路径
```

输入完整备份批次目录（或 ZIP 备份文件）路径。

程序会先验证整个备份，再根据 `manifest.json` 中记录的 `source_path` 恢复到原始路径。

恢复冲突策略：

```text
skip       原路径已存在时跳过，默认/推荐
rename     恢复为另一个名称
overwrite  先恢复到临时文件并校验，成功后再原子替换原文件
```

---

# 当前主菜单

```text
FileCheck V0.1 · 文件扫描 / 批量备份 / 验证 / 源文件处理 / 恢复

1. 检查 Everything / ES 环境
2. 扫描并处理（推荐入口）
3. 使用已有扫描结果批量备份
4. 使用已有扫描结果迁移（备份后直接进入源文件移除）
5. 验证已有备份
6. 从备份恢复到原路径
7. 删除已验证备份对应的源文件
8. 继续未完成的备份 / 迁移
9. 运行本机自检
10. 显示高级命令帮助
0. 退出
```

其中菜单 4 `migrate` 仍然保留，用于希望一次连续完成：

```text
备份 → 验证 → 源文件复核 → YES 确认 → 删除源文件
```

但对于需要人工检查备份后再决定删除的场景，更推荐：

```text
3 → 5 → 7
```

---

# 已实现能力

- 复用 **Everything 1.4 已有索引**，不创建 FileCheck 自有全盘索引。
- 使用 ES CLI 1.1.0.37+ 的 `-argv` 和 UTF-8 导出通道，避免 Windows 参数解析和特殊 Unicode 文件名问题。
- 搜索按“**一个关键词 + 全部目标扩展名**”组合。
- 可扫描 Everything 当前已索引的全部范围，也可指定盘符/目录。
- 扫描结果按完整绝对路径去重；同一文件命中多个关键词时合并命中原因并取最高风险级别。
- 候选很多时控制台只显示有限数量，完整结果全部写入 `scan-results.json`。
- `backup --from-scan` 默认批量处理扫描结果中的全部候选，不要求逐个确认。
- 目录备份保持原盘符、目录结构和文件名，同名文件不会互相覆盖。
- 支持目录备份和 ZIP 备份。
- 每个文件记录原始绝对路径、备份相对路径、大小、mtime 和 SHA-256。
- 备份前检查目标剩余空间。
- `.FC-....incomplete` 作为未完成批次暂存目录，未通过验证不会发布成正式备份。
- 批量复制支持操作状态、失败记录和中断续传。
- Windows 文件 I/O 使用长路径兼容处理。
- 备份完成后逐文件执行大小 + SHA-256 全量复核。
- ZIP 同时检查 CRC 和逐文件 SHA-256。
- 独立 `verify` 可对已发布备份再次完整验证。
- 独立源文件删除功能以已验证 manifest 为唯一删除清单。
- 删除前重新验证备份、重新 SHA-256 复核全部源文件。
- 源文件删除支持 `.migration.json` 状态和断点继续。
- 已删除路径若后来重新出现，不会在 resume 中自动再次删除，防止误删新数据。
- 恢复前先验证整个备份集。
- 恢复支持 `skip / rename / overwrite`。
- 自带 `selftest` 和 Windows/Linux CI 回归。

---

# 扫描规则

默认规则：

```text
config\rules.json
```

当前每个关键词构造成类似：

```text
"机密" ext:doc;docx;xls;xlsx;ppt;pptx;pdf;txt;wps;zip;rar;7z;dwg
```

也就是一个关键词一次 Everything 查询，同时限定全部目标扩展名。

默认只匹配文件名；启用 `--match-path` 后才同时匹配完整目录路径。

---

# 备份目录和 manifest

## 目录备份结构

源路径：

```text
C:\ProjectA\报告.docx
D:\资料\报告.docx
```

备份：

```text
<批次目录>\
├─ manifest.json
└─ files\
   ├─ C\
   │  └─ ProjectA\
   │     └─ 报告.docx
   └─ D\
      └─ 资料\
         └─ 报告.docx
```

## `manifest.json`

每个文件至少包含：

```json
{
  "source_path": "C:\\ProjectA\\报告.docx",
  "backup_path": "files/C/ProjectA/报告.docx",
  "size": 123456,
  "mtime_ns": 1234567890000000000,
  "sha256": "..."
}
```

`manifest.json` 是恢复和源文件安全移除的权威映射，但备份目录本身仍保持人工可读结构。

---

# 高级命令行

## 环境检查

```powershell
filecheck doctor
```

## 扫描

```powershell
filecheck scan --path D:\ --output scan-results.json
```

扫描 Everything 当前全部索引范围：

```powershell
filecheck scan --output scan-results.json
```

关键词同时匹配目录：

```powershell
filecheck scan --path D:\ --match-path --output scan-results.json
```

## 批量备份

```powershell
filecheck backup --from-scan scan-results.json --dest H:\backup
```

ZIP：

```powershell
filecheck backup --from-scan scan-results.json --dest H:\backup --zip
```

高级过滤：

```powershell
filecheck backup --from-scan scan-results.json --select 1,3-5 --dest H:\backup
```

## 一次性迁移

```powershell
filecheck migrate --from-scan scan-results.json --dest H:\backup
```

## 验证

```powershell
filecheck verify H:\backup\FC-xxxx
```

## 恢复

```powershell
filecheck restore H:\backup\FC-xxxx --conflict skip
```

## 自检

```powershell
filecheck selftest
```

---

# 运行产物

## `scan-results.json`

扫描候选清单，记录：

- 扫描时间；
- Everything 版本；
- 扫描范围；
- 规则文件名和规则 SHA-256；
- 每个候选的完整路径、目录、命中关键词、风险级别、大小、mtime 和访问状态。

扫描阶段不对所有候选计算文件内容 SHA-256，以保持 Everything 快速扫描优势。

## `manifest.json`

备份/恢复权威清单。

## `*.operation.json`

大量文件备份/迁移的全过程操作状态，默认保存在：

```text
%LOCALAPPDATA%\FileCheck\operations\
```

用于复制阶段中断续传。

## `*.migration.json`

源文件删除阶段状态，记录 `pending / deleted / already_absent / failed / reappeared` 等状态和失败原因。

---

# 安装开发版

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

ES CLI 搜索顺序包括：

1. Win64 冻结程序所在目录的 `tools\es.exe`；
2. 当前工作目录 `tools\es.exe`；
3. 系统 PATH；
4. `FILECHECK_ES`；
5. Everything 常见安装目录。

V0.1.0 按 Everything 1.4.x + ES 1.1.0.37 环境验证。

---

# 自动化测试

```powershell
python -m pytest -q
```

CI 矩阵：

- Windows latest + Python 3.10
- Windows latest + Python 3.12
- Ubuntu latest + Python 3.10
- Ubuntu latest + Python 3.12

覆盖重点包括：

- Everything 查询参数构造；
- Unicode 特殊文件名；
- 大量候选批量处理；
- 目录/ZIP 备份与恢复；
- Windows 长路径；
- 目录镜像结构；
- 同名文件；
- 空间不足；
- 写入失败；
- 源文件复制中变化；
- 备份损坏；
- 批量复制中断和续传；
- 只读文件；
- 源文件复核和删除；
- 删除中断续跑；
- 已删除路径重新出现保护；
- 恢复冲突策略；
- Win64 EXE smoke/selftest。

---

# 安全边界与已知限制

- 关键词命中只表示候选，不自动认定文件性质。
- `scan` 和 `backup` 不删除源文件。
- 源文件删除只依据已经验证的 `manifest.items[].source_path`。
- 不杀进程、不强制解锁。
- FileCheck 程序本身不自动清理 Recent、浏览器历史、USBSTOR、Office/WPS MRU 或注册表记录。
- 扫描结果、真实文件名/路径、manifest、migration state 和备份包都可能包含敏感运行信息，不应提交 Git 或随意外发。
- ZIP 是压缩格式，不是加密格式。
- 当前恢复承诺针对普通文件内容、原始绝对路径、大小、基本 mtime 和 SHA-256。
- NTFS ACL、EFS、ADS、硬链接、稀疏文件、重解析点等高级文件系统语义暂不作为恢复承诺。
- 空目录不会单独备份或恢复，源文件删除后也不会自动清理空目录。

---

# 文档

- `docs/REQUIREMENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/TEST_PLAN.md`
- `docs/CLI_MENU.md`
