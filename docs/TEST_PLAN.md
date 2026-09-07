# FileCheck V0.1 深度测试与回归计划

## 1. 目标

验证以下完整链路在大量候选和异常条件下仍然安全：

```text
Everything scan
→ scan-results.json
→ 全部候选批量 backup
→ 全量 verify
→ restore
```

以及显式迁移链路：

```text
scan-results.json
→ bulk backup
→ verify entire backup
→ re-hash all sources
→ one batch confirmation
→ manifest-only unlink
→ migration state checkpoint
→ migrate-resume
→ restore
```

核心安全不变量：

1. 未验证的备份不能用于恢复或源文件移除；
2. 任一源文件在迁移批量预检时发生变化，删除阶段不得开始；
3. 真正删除每个源文件前再次即时复核；
4. 删除范围只能来自 manifest item，不能递归删除父目录；
5. 迁移中断/文件锁定可通过 state 续跑；
6. 已删除路径后来重新出现时，resume 不自动删除新文件；
7. 恢复覆盖现有文件前，临时恢复副本必须先通过 SHA-256。

## 2. 自动化测试门禁

GitHub Actions 矩阵：

- Windows latest + Python 3.10
- Windows latest + Python 3.12
- Ubuntu latest + Python 3.10
- Ubuntu latest + Python 3.12

每个平台执行：

```text
python -m pytest -q
filecheck selftest
```

### 2.1 Everything / 扫描逻辑

覆盖：

- ES `-argv` 必须作为第一个参数；
- `-path`、`/a-d`、`-full-path-and-name` 参数构造；
- 一个关键词 + 全部扩展名 `ext:` 组合；
- 路径范围二次过滤；
- 多关键词同文件去重；
- severity 取最高级别；
- indexed-but-inaccessible 结果不静默丢弃；
- Everything 非 1.4.x 拒绝；
- ES < 1.1.0.37 拒绝；
- 扫描结果不再要求 `--select`，默认消费全部 items；
- 规则 metadata 使用文件名 + SHA-256，不写绝对路径。

### 2.2 备份/恢复

覆盖：

- directory / ZIP roundtrip；
- 中文路径；
- 空格路径；
- 空文件；
- 二进制文件；
- 多级目录；
- 不同目录同名文件；
- 重叠源路径去重；
- 批次 ID 唯一；
- 目标空间不足；
- 介质写失败；
- incomplete staging 不发布；
- 源文件复制中变化；
- manifest 路径穿越；
- 目录备份内容损坏；
- ZIP CRC 正常但 SHA-256 被篡改；
- `skip / rename / overwrite`；
- restore 开始前完整 verify；
- 临时恢复副本写失败时现有目标不变；
- mtime 基本恢复；
- 只读文件 durable sync 与恢复；
- directory/ZIP 压力回环。

### 2.3 迁移

覆盖：

- directory / ZIP 迁移后全部源文件移除；
- 移除后备份仍可完整 verify；
- 移除后原路径完整 restore；
- 备份完成后任一源文件变化：整批删除前拒绝；
- 损坏备份：源文件一个也不删除；
- 文件锁/PermissionError：记录 partial；
- `migrate-resume` 重新验证备份并继续 failed item；
- failed item 被人工删除后：记录 `already_absent`；
- migration state 篡改：拒绝；
- state 不能写入 directory backup 内部；
- 已记录删除的 source_path 后来重新出现：标记 `reappeared`，不删除；
- 250 文件批量迁移压力测试；
- migration selftest directory/ZIP 闭环。

## 3. 当前真实 Windows 验收证据

已完成一组受控 Windows + Everything 1.4 实机验证：

- ES CLI 1.1.0.37 `-argv` 实际查询成功；
- Everything 1.4 实际 IPC 成功；
- FileCheck 实际扫描得到预期 3 个关键词候选；
- directory backup：4 个测试文件全部备份并独立 verify；
- 人工移走原测试目录后，directory restore：`restored=4, skipped=0`；
- 4/4 恢复文件与原测试副本 SHA-256 一致；
- ZIP backup/verify/restore 同样 4/4 SHA-256 一致。

真实 Windows **显式 migrate 源文件移除**仍建议使用专用测试目录再做一次最终验收，不能直接拿重要数据作为首次迁移测试。

## 4. Windows + Everything 实机回归

### 4.1 环境检查

```powershell
filecheck doctor
```

预期：

- ES >= 1.1.0.37；
- Everything 1.4.x；
- IPC 正常。

### 4.2 扫描

准备受控测试数据，包含：

- 单关键词文件名；
- 多关键词文件名；
- 普通文件；
- 中文；
- 空格；
- 相同文件名位于不同目录；
- 目标扩展名和非目标扩展名。

```powershell
filecheck scan --path <test-root> --output scan-results.json
```

验证：

- 预期候选数；
- matched_keywords；
- severity；
- 指定 path 不混入其它目录结果；
- JSON 保存完整结果；
- `rules` 仅含 `file` + `sha256`。

## 5. 批量备份实机回归

### 5.1 全部候选默认备份

```powershell
filecheck backup --from-scan scan-results.json --dest <backup-root>
```

不带 `--select` 应备份全部候选。

验证：

- 文件数等于 scan items 数；
- 不同目录同名文件都存在；
- backup_path 各不相同；
- verify 全通过；
- 所有源文件仍存在。

### 5.2 ZIP

```powershell
filecheck backup --from-scan scan-results.json --dest <backup-root> --zip
filecheck verify <FC-xxxx.zip>
```

## 6. 显式 migrate 实机验收

必须使用专用可丢弃测试目录。

```powershell
filecheck migrate --from-scan scan-results.json --dest <backup-root>
```

确认输出：

```text
第一阶段：备份全量验证通过
第二阶段：全部源文件再次 SHA-256 复核通过
一次 YES 确认
源文件移除进度
migration state
```

迁移后：

- scan items 对应源文件不存在；
- 未被扫描的普通文件仍存在；
- 原目录本身不被递归删除；
- 空目录允许保留；
- `filecheck verify <backup>` 仍通过；
- `filecheck restore <backup>` 可恢复全部迁移文件；
- 恢复后逐文件 SHA-256 与 manifest 一致。

## 7. 迁移故障注入实机

### A. 一个文件被应用占用

预期：

- 不杀进程；
- 该文件保持原位；
- migration state 为 `failed`；
- 其他已完成项正确记录；
- 关闭应用后 `migrate-resume` 成功。

### B. 备份后、确认前修改一个源文件

预期：

- source recheck 失败；
- 尚未删除任何源文件。

### C. 删除过程中修改尚未处理的文件

预期：

- 删除前即时 SHA-256 检测异常；
- 该文件不删除，记录 failed。

### D. 已迁移路径被应用重新创建

完成一次迁移后，在原路径创建新文件，再执行：

```powershell
filecheck migrate-resume <state>
```

预期：

- 新文件保留；
- state 标记 `reappeared`；
- 不自动删除。

### E. 备份盘掉线 / 不可写

预期：

- 备份阶段失败时不发布正式批次；
- migration state 初始落盘失败时不开始删除源文件；
- 若删除中途状态 checkpoint 失败，任务报错；恢复介质后根据已有 state/源路径实际存在情况续跑。

## 8. 恢复故障注入

### A. 目录备份内容损坏

`verify` / `restore` 均失败，且在完整 verify 通过之前不触碰任何原目标。

### B. ZIP 篡改

CRC 或逐文件 SHA-256 失败。

### C. 原路径已有文件

验证：

- `skip`：原文件完全不变；
- `rename`：原文件保留；
- `overwrite`：临时文件校验成功后才替换。

### D. 原始盘符/共享不可用

Windows preflight 直接失败，不开始其它目标恢复。

## 9. 长路径与 Windows 特性

额外实机覆盖：

- 260 字符附近；
- LongPathsEnabled 下 >260 字符；
- 只读普通文件；
- Word/Excel/PDF 等应用占用；
- USB NTFS；
- 如业务需要，再测试 exFAT/FAT32。

失败必须明确报告，不允许静默漏项。

## 10. 当前不承诺

当前可靠性目标是普通文件：

- 内容字节；
- 原始绝对路径；
- 文件大小；
- 基本 mtime；
- SHA-256。

暂不承诺：

- NTFS ACL；
- EFS；
- ADS；
- 硬链接关系；
- 稀疏文件特性；
- Junction / Symbolic Link / Reparse Point；
- 文件所有者与完整审计元数据；
- 空目录单独恢复。

## 11. 通过门槛

进入真实重要数据使用前要求：

1. 最新 head 的四平台 CI 全绿；
2. `filecheck selftest` 四平台通过；
3. Everything 1.4 实机 scan 通过；
4. directory + ZIP 实机备份/恢复 SHA-256 通过；
5. 专用 Windows 测试目录完成一次 `migrate → verify → restore → SHA-256`；
6. 至少验证一次文件占用后的 `migrate-resume`；
7. 任何失败场景均不出现“未验证备份 + 源文件已删除”的组合。
