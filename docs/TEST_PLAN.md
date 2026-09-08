# FileCheck V0.1.1 测试与验收计划

## 1. 验证目标

V0.1.1 的主链路为：

```text
portable Everything 专用索引
→ scan-results.json / CSV
→ 人工核对
→ 全部候选目录备份
→ 全量 verify
→ 人工检查
→ 全部源文件再次复核
→ YES
→ manifest-only unlink
→ source-removal.json / not-deleted.txt
→ 必要时 resume
→ 原路径 restore
```

同时验证旧 V0.1.0 ZIP **人工解压后的目录**仍可被校验和恢复。

## 2. 核心安全不变量

1. `scan` 不修改源文件。
2. `backup` 不删除源文件。
3. 只有完整备份通过 size + SHA-256 全量校验后才发布正式 `FC-*` 批次。
4. `manifest.json` 不包含 `source_removed`，后续删除行为不回写 manifest。
5. 源文件删除前必须重新验证整个备份。
6. 删除第一项前必须先重新复核**全部**源文件。
7. 只删除 manifest 中逐项列出的 `source_path`。
8. 不递归删除父目录，不自动删除空目录。
9. 单文件被占用/权限不足时，跳过该文件并继续其余文件。
10. 删除状态逐文件 checkpoint 到 `<batch>\source-removal.json`。
11. 未删除项写入 `<batch>\not-deleted.txt`；全部完成后该文本应消失。
12. 已经删除后又重新出现的路径标记 `reappeared`，resume 不自动再次删除。
13. 恢复前先验证整个备份，不能边验证边写原路径。
14. `overwrite` 必须先恢复到目标同目录临时文件，校验通过后再替换。
15. 不同目录/不同盘符中的同名文件必须分别备份、删除和恢复。

## 3. 自动化测试范围

当前 pytest 覆盖重点包括：

- Everything / ES 参数、Unicode 路径和去重；
- FileCheck 专用 portable Everything 配置与发现；
- 扫描结果规则 metadata 隐私；
- 批量 `--from-scan` 默认全部候选；
- 目录备份单次复制路径和完整 verify；
- 目标位于源目录内部时拒绝；
- 备份空间不足时在正式复制前拒绝；
- 复制失败/最终 verify 失败时不发布正式批次；
- 只读文件备份与恢复；
- manifest 路径安全和篡改拒绝；
- 目录备份恢复 `skip / rename / overwrite`；
- `manifest_immutable` / 无 `source_removed`；
- 删除前整批源文件复核；
- 备份损坏阻止删除；
- 文件锁模拟、部分删除、`source-removal.json`、resume；
- `not-deleted.txt` 生成/清理；
- migration state 篡改拒绝；
- 250 文件批量删除/恢复；
- reappeared 路径保护；
- 20 轮重复目录备份/恢复；
- 未完成备份复制状态和续传。

## 4. 当前自动化基线

2026-09-07，V0.1.1 目录工作流代码基线已经在 GitHub Actions 通过：

```text
Windows latest / Python 3.10 : PASS
Windows latest / Python 3.12 : PASS
Ubuntu latest  / Python 3.10 : PASS
Ubuntu latest  / Python 3.12 : PASS
```

Windows 3.12 日志：

```text
62 passed
```

并且 `filecheck selftest` 全部通过：

```text
directory_roundtrip: PASS (5 files)
manifest_immutable: PASS
source_removal_state: PASS (5 files)
sha256_verification: PASS
conflict_skip: PASS
conflict_overwrite: PASS
source_removal_restore: PASS
```

## 5. Windows 10/11 便携构建验收

Win64 构建任务必须完成：

```text
pytest
selftest
PyInstaller one-file build
exe selftest / --help smoke test
官方 ES 下载 + SHA-256 校验
官方 Everything portable 下载 + SHA-256 校验
组装 portable package
从其他工作目录运行 FileCheck.exe doctor
上传 artifact
```

当前已通过构建基线：

```text
FileCheck-v0.1.1-win10plus-x64
Everything 1.4.1.1032 x64 portable
ES 1.1.0.37 x64
62 passed
```

该构建已验证 `doctor` 能从包内定位：

```text
tools\Everything.exe
tools\es.exe
```

## 6. Windows 7 构建兼容性

Win7 构建路线继续固定：

```text
Python 3.8.10 x64
PyInstaller 5.13.2
pytest 7.4.4
```

构建任务要求：

- Python 3.8 `compileall`；
- 62 项回归测试；
- selftest；
- PyInstaller 打包；
- 包内 Everything / ES 完整性；
- `FileCheck.exe doctor` 便携发现。

当前 GitHub Actions 构建已全部通过并成功生成 `FileCheck-v0.1.1-win7-x64` artifact。

**这不等价于真实 Windows 7 运行验收。** V0.1.1 正式发布前仍必须在真实 Windows 7 SP1 x64 机器上重新执行下述实机链路。

## 7. 真实 Windows 实机验收

只使用可随时删除的测试数据，禁止第一次就在真实重要文件上执行删除。

建议测试数据至少包含：

```text
C:\FileCheck-Test\A\报告.txt
C:\FileCheck-Test\B\报告.txt
D:\FileCheck-Test\报告.txt
C:\FileCheck-Test\普通目录\普通文件.txt
```

前三项名称命中测试关键词，第四项不命中，用于证明删除范围不会扩大。

### 7.1 专用索引

确认：

- 无需另行安装 Everything；
- `tools\Everything.exe` / `tools\es.exe` 能被发现；
- 可选择 C:/D: 等测试范围；
- `runtime\everything\Everything.ini` 和 `Everything.db` 建立；
- 程序目录、备份根目录被排除；
- 不干扰用户已有默认 Everything（如果机器上存在）。

### 7.2 扫描

确认：

- 文件名命中正确；
- 默认不因为父目录关键词误扩大候选；
- JSON/CSV 均生成；
- 完整 Unicode 路径不乱码；
- `rules` 只记录文件名 + SHA-256，不暴露规则绝对路径。

### 7.3 目录备份

确认：

- 全部候选一次处理；
- 不要求逐文件确认；
- 三个不同路径的 `报告.txt` 都存在于不同 `files\...` 路径；
- backup 完成后源文件全部仍存在；
- `manifest.json` 中没有 `source_removed`；
- `verify` 再次通过。

### 7.4 源文件删除

确认：

- 删除前再次验证备份；
- 删除前再次复核全部源文件；
- 需要一次 `YES`；
- 只删除候选三项；
- `普通文件.txt` 保留；
- 父目录保留；
- `source-removal.json` 位于备份批次目录中。

### 7.5 文件占用 / resume

使用测试 FileStream 或编辑器独占一个候选文件：

```text
一个文件删除失败
→ 其余文件继续删除
→ not-deleted.txt 出现
→ 关闭占用
→ 继续删除
→ 失败文件删除成功
→ not-deleted.txt 消失
```

### 7.6 恢复

删除完成后：

```text
verify
→ restore --conflict skip
→ 所有 manifest 源路径重新出现
→ 每项 SHA-256 与 manifest 一致
```

然后再测试：

```text
rename
overwrite
```

## 8. 旧 V0.1.0 ZIP 兼容验收

FileCheck v0.1.1 不直接处理 ZIP。

测试方法：

1. 取一个 V0.1.0 真实测试 ZIP；
2. 使用系统工具完整解压；
3. 确认目录内存在 `manifest.json` 和 `files\`；
4. 保持旧 manifest 的 `mode=zip` 不修改；
5. 执行 `verify <解压目录>`；
6. 在可丢弃目标上执行 restore；
7. 比对全部 SHA-256。

通过标准：旧 ZIP **无需改 manifest，只需人工解压**即可恢复。

## 9. 发布门禁

V0.1.1 不合并/不正式发布，直到同时满足：

```text
四矩阵 CI 全绿
Win10/11 portable build 全绿
Win7 compatibility build 全绿
Win10/11 真实机完整索引→扫描→备份→删除→恢复通过
Win7 真实机完整索引→扫描→备份→删除→恢复通过
旧 V0.1.0 ZIP 人工解压恢复通过
```

涉及真实文件删除的验收必须先使用受控测试数据完成。
