# FileCheck v0.1.1 交互式命令行菜单

## 1. 启动

源码开发环境：

```powershell
filecheck
```

正式包：

```powershell
.\FileCheck.exe
```

无参数时进入交互式菜单；带子命令时进入高级 CLI。

## 2. 主菜单

```text
FileCheck v0.1.1 · 便携索引 → 扫描 → 目录备份 → 验证 → 删除 → 恢复

1. 环境与索引（选择磁盘、设置备份目录、建立索引）
2. 扫描文件（结果保存到程序目录 scan-results）
3. 核对扫描结果（JSON / CSV）
4. 创建目录备份（全部候选，保持原目录结构）
5. 检查并再次验证备份
6. 删除源文件 / 继续未完成删除
7. 恢复备份文件到各自原路径
8. 继续未完成的备份复制任务
9. 运行本机自检
10. 高级命令帮助
0. 退出
```

菜单强调生命周期顺序，而不是把“备份”和“删除”混成一个默认动作。

## 3. 环境与索引

首次使用选择需要纳入检查的磁盘/目录，并指定统一备份根目录。

FileCheck 使用随包提供的 portable Everything，启动专用实例 `FileCheck`，运行数据保存到：

```text
runtime\everything\Everything.ini
runtime\everything\Everything.db
runtime\everything\index-config.json
```

自动排除：

```text
FileCheck 程序目录
统一备份根目录
```

因此备份副本不会在后续扫描中再次成为候选。

## 4. 扫描

菜单默认扫描当前 FileCheck 专用索引的全部配置范围。

用户只需要决定：

```text
关键词是否同时匹配目录路径（默认 N）
```

默认只匹配文件名，避免父目录关键词导致候选范围意外扩大。

高级 CLI 仍允许：

```powershell
filecheck scan --path D:\Work
```

其中 `--path` 只是在已经建立的专用索引中进一步限定子目录。

## 5. 扫描结果

默认输出：

```text
scan-results\scan-results-YYYYMMDD-HHMMSS.json
scan-results\scan-results-YYYYMMDD-HHMMSS.csv
```

JSON 供 FileCheck 后续处理；CSV 供人工核对。

扫描完成后不会立刻进入删除，也不要求逐文件选择。

## 6. 容量提示

菜单按当前扫描结果估算：

```text
候选文件数
当前可统计大小的文件数
候选数据总量
目录备份建议至少可用空间
```

V0.1.1 只有目录备份，因此不再显示 ZIP 空间估算。

估算公式：

```text
候选总字节数 + 安全余量
```

安全余量最少 16 MiB、最多 512 MiB，中间按候选数据量约 5% 计算。实际开始备份时后端仍会再次执行空间门禁。

## 7. 创建目录备份

菜单 4 默认把当前选择的 `scan-results.json` 中**全部候选**交给备份流程：

```text
扫描 JSON
→ 全部候选
→ 保持源盘符/目录/文件名复制
→ 每文件 SHA-256
→ 整批全量 verify
→ 成功后发布 FC-* 正式目录
```

不要求逐文件确认，也不提供 ZIP 选项。

## 8. 再次验证

菜单 5 用于人工检查备份目录后再次执行完整 `verify`。

这是源文件删除前推荐的独立人工门禁。

## 9. 删除源文件 / 继续删除

菜单 6 的逻辑：

```text
选择正式备份批次
→ 若无 source-removal.json：
     完整验证备份
     → 全部源文件重新 size + SHA-256
     → YES
     → 逐文件即时复核并删除
→ 若已有未完成 source-removal.json：
     再次验证备份
     → 只重试 pending/failed
```

删除状态保存在：

```text
<备份批次>\source-removal.json
```

有失败项时还会生成：

```text
<备份批次>\not-deleted.txt
```

删除失败不会终止整个批次；文件占用、权限等问题关闭/修复后可继续。

## 10. 恢复

菜单 7 只接受目录备份。恢复前先验证整个备份。

冲突策略：

```text
1 = skip       默认/推荐
2 = rename
3 = overwrite
```

V0.1.0 旧 ZIP 必须先人工完整解压，再把解压目录交给 FileCheck。

## 11. 未完成备份

大批量复制如果被中断或遇到暂时不可访问文件，可通过菜单 8 读取操作状态继续。

已经复制且重新校验仍有效的暂存文件不会重复复制。

## 12. 高级 CLI

```powershell
filecheck doctor
filecheck index --drive C:\ --drive D:\ --backup-root H:\FileCheckBackup
filecheck scan
filecheck backup --from-scan scan-results.json --dest H:\FileCheckBackup
filecheck verify H:\FileCheckBackup\FC-...
filecheck remove-sources H:\FileCheckBackup\FC-...
filecheck remove-resume H:\FileCheckBackup\FC-...
filecheck restore H:\FileCheckBackup\FC-... --conflict skip
filecheck selftest
```

`migrate` / `migrate-resume` 仅作为兼容高级别名保留，不属于推荐菜单主流程。
