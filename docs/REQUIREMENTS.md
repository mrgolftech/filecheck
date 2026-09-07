# FileCheck V0.1 需求说明

## 1. 产品目标

FileCheck 用于 Windows 终端离线文件自查、批量备份、迁移和原路径恢复。当前版本重点解决：

1. 使用 Everything 1.4 快速发现文件名/路径命中规则的候选文件；
2. 面对数百、数千甚至更多候选时，不要求逐文件确认，可将本次扫描结果整体批量备份；
3. 备份时保留原始绝对路径、文件大小、修改时间和 SHA-256，解决不同目录同名文件冲突；
4. 在用户显式选择迁移时，只有备份和源文件再次复核都通过后才允许移除源文件；
5. 迁移部分失败可安全续跑，后续仍能依据 manifest 恢复到原位置。

关键词命中只代表候选，不等同于对文件性质的自动认定。

## 2. 检索要求

### 2.1 Everything 1.4 优先

目标环境使用 Everything 1.4。V0.1 通过官方 ES CLI 调用 Everything IPC，不读取 `Everything.db`，也不创建 FileCheck 自有全盘索引。

启动/扫描前检查：

- `es.exe` 是否存在；
- ES CLI 版本是否 >= 1.1.0.37；
- Everything 是否为 1.4.x；
- IPC 是否可用。

ES 查找顺序：

1. 显式 `--es`；
2. `FILECHECK_ES` 环境变量；
3. 当前目录 `tools/es.exe`；
4. 系统 PATH；
5. Everything 常见安装目录。

V0.1 不自动安装 Everything，也不在 Everything 不可用时静默切换为慢速全盘扫描。

### 2.2 关键词与文件类型组合

关键词由 `config/rules.json` 分组维护。当前每个关键词单独执行一次 ES 查询，全部目标扩展名使用一个 `ext:` 条件组合，例如：

```text
"机密" ext:doc;docx;xls;xlsx;ppt;pptx;pdf;txt;wps;zip;rar;7z;dwg
```

即：

```text
一个关键词 AND (扩展名1 OR 扩展名2 OR ...)
```

这样既减少查询次数，也能准确保留每个文件命中了哪些关键词。

### 2.3 默认文件类型

`.doc .docx .xls .xlsx .ppt .pptx .pdf .txt .wps .zip .rar .7z .dwg`

允许通过规则文件调整。

### 2.4 扫描范围

支持指定盘符或目录。指定范围时必须通过 ES `-path` 在 Everything 侧先过滤，再执行 `-n` 限制，避免全局结果截断导致目标目录漏检。

默认只匹配文件名；`--match-path` 时增加完整路径匹配。

## 3. 扫描结果

扫描完成后生成 `scan-results.json`。顶层至少记录：

- `schema_version`
- `created_at`
- `engine`
- `everything_version`
- `match_path`
- `path_filter`
- `rules.file`
- `rules.sha256`
- `items[]`

每个候选至少记录：

- `path`
- `directory`
- `matched_keywords[]`
- `levels[]`
- `severity`
- `size`
- `mtime_ns`
- `accessible`

规则记录不得默认暴露本机规则文件绝对路径；使用规则文件名 + SHA-256 即可标识本次规则版本。

大量候选时控制台只显示有限条目，完整候选必须全部写入 JSON。

## 4. 批量处理策略

正常工作流不要求逐个候选确认。

```text
scan-results.json
      ↓
默认处理 items 中全部候选
      ↓
批量备份 / 批量迁移
```

`--select` 可以保留作为高级过滤能力，但不是默认必需步骤。

扫描只决定“哪些候选文件进入批次”，不会因为某个文件命中关键词就自动扩大到整个所在目录。用户直接指定目录进行 `backup/migrate` 时，才处理该目录中的普通文件。

## 5. 备份路径映射与同名文件

不同原始路径下的同名文件不能拍平到同一个目标目录。

示例：

```text
C:\ProjectA\报告.docx -> files/C/ProjectA/报告.docx
C:\ProjectB\报告.docx -> files/C/ProjectB/报告.docx
D:\资料\报告.docx    -> files/D/资料/报告.docx
```

源文件唯一性以规范化后的完整绝对路径为依据。重叠选择必须去重；备份相对路径冲突必须使整批备份失败，不允许静默覆盖。

## 6. 备份模式

### 6.1 目录备份

正式批次结构：

```text
FC-<batch>/
├─ manifest.json
└─ files/
   └─ <按原始绝对路径映射的目录树>
```

### 6.2 ZIP 备份

```text
FC-<batch>.zip
├─ manifest.json
└─ files/...
```

ZIP 只是压缩，不代表加密。

## 7. 备份事务与完整性

备份前：

- 收集普通文件并去重；
- 拒绝源目录内部作为备份目标；
- 估算目标空间；
- 目录模式预留源总大小 + 安全余量；
- ZIP 模式考虑 staging + 临时 ZIP 的最坏空间需求。

每个文件：

```text
读取源元数据
→ 源 SHA-256
→ 复制到临时路径
→ 刷盘
→ 目标 SHA-256
→ 再次检查源是否变化
→ 一致后原子发布
```

批次：

```text
.FC-xxxx.incomplete
→ 所有文件完成
→ manifest 原子写入并刷盘
→ 全量 verify
→ 正式 FC-xxxx / FC-xxxx.zip
→ 再次 verify
```

任何失败都不得留下一个看似成功的正式批次。

## 8. Manifest

每个正式备份包含不可缺失的 manifest：

```json
{
  "schema_version": 1,
  "batch_id": "FC-20260907-xxxx",
  "created_at": "...",
  "mode": "directory",
  "source_bytes_total": 12345,
  "space_required_estimate": 23456,
  "space_free_at_start": 999999,
  "items": [
    {
      "source_path": "D:\\work\\projectA\\design.docx",
      "backup_path": "files/D/work/projectA/design.docx",
      "size": 12345,
      "mtime_ns": 0,
      "sha256": "...",
      "backup_verified": true
    }
  ]
}
```

`manifest.json` 是恢复路径映射与内容完整性的权威依据。

## 9. `backup` 行为

`backup` 永远是非破坏性操作：

```text
候选/指定源
→ 复制
→ 全量验证
→ 返回正式备份
→ 源文件保持不变
```

即使用户从 `scan-results.json` 批量处理全部候选，也不允许 `backup` 隐式删除源文件。

## 10. `migrate` 行为

`migrate` 是唯一允许进入源文件移除阶段的显式命令。

必须按以下顺序：

```text
创建备份
→ 完整 verify
→ 对所有源文件再次计算 size + SHA-256
→ 任一源文件变化：整批停止，尚未删除任何源文件
→ 全部通过
→ 显示文件数/总大小/备份位置
→ 一次批次级 YES 确认（或显式 --yes）
→ 每个文件删除前再次即时复核
→ 只 unlink manifest 中的 source_path
→ 不删除目录
→ 持续记录 migration state
```

禁止：

- 按父目录递归删除；
- 为绕过占用而杀进程；
- 强制解锁；
- 在未验证备份时删除源文件。

## 11. Migration state 与续跑

迁移开始删除前必须先成功落盘 sidecar 状态文件：

```text
FC-xxxx.migration.json
FC-xxxx.zip.migration.json
```

每项状态支持：

- `pending`
- `deleted`
- `already_absent`
- `failed`
- `reappeared`

若文件被占用或无权限：

- 该文件保留原位置；
- 记录 `failed` 和错误原因；
- 其他已安全处理项无需回滚；
- 用户关闭应用/修正权限后可执行 `migrate-resume`。

`migrate-resume` 必须：

1. 再次验证整个备份；
2. 验证 state 与 manifest 的 batch、文件集合、size、SHA-256 一致；
3. 只重试 `pending/failed`；
4. 若已记录删除的路径后来重新出现，标记 `reappeared`，不自动删除，以防误删新数据。

## 12. 恢复

恢复前必须完整验证备份。冲突策略：

- `skip`（默认）
- `rename`
- `overwrite`

恢复流程：

```text
完整 verify
→ 检查原始盘符/共享可用性
→ 写同目录临时文件
→ 临时文件 size + SHA-256
→ 恢复基本 mtime
→ os.replace 原子落盘
→ 最终 SHA-256
```

`overwrite` 也不得先删除现有目标文件。

## 13. 数据与安全要求

- 默认离线运行；
- 不上传扫描结果、manifest 或 migration state；
- 不记录文件正文；
- 扫描结果、路径、manifest、migration state 和备份包都可能包含敏感运行信息，不得提交 Git；
- 不提供 Recent、浏览器历史、USBSTOR、Office/WPS MRU、注册表等清痕能力；
- `scan` 与 `backup` 不删除任何源文件；
- 只有用户显式调用 `migrate` 才允许经过验证后移除 manifest 中列出的源文件。

## 14. V0.1 验收标准

- Everything 1.4 + ES 1.1.0.37+ 实机可稳定扫描中文/空格路径；
- 关键词与扩展名查询构造正确；
- 同一文件多关键词命中可去重并保留全部命中原因；
- 大量候选可整体批量进入备份，不要求逐文件确认；
- 目录/ZIP 两种备份均通过全量 SHA-256；
- 不同目录同名文件无冲突；
- 空间不足、介质写失败、源文件变化时不发布正式备份；
- 损坏备份在恢复/迁移前被拒绝；
- 目录/ZIP 均可依据 manifest 恢复原路径；
- `migrate` 在任何源文件变化时不开始批量删除；
- 部分文件锁定时状态可记录并续跑；
- 已删除路径重新出现时 resume 不误删新文件；
- Windows / Ubuntu、Python 3.10 / 3.12 CI 全绿；
- `filecheck selftest` 覆盖备份、验证、迁移和恢复闭环。
