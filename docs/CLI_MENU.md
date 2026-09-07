# FileCheck 交互式命令行菜单

## 1. 启动

重新安装当前开发版后，直接执行：

```powershell
filecheck
```

不带任何子命令时进入交互式菜单。原有高级命令仍然保留，例如：

```powershell
filecheck scan --path D:\ --output scan-results.json
filecheck backup --from-scan scan-results.json --dest X:\FileCheckBackup
filecheck migrate --from-scan scan-results.json --dest X:\FileCheckBackup
```

也可以显式执行：

```powershell
filecheck menu
```

## 2. 主菜单

```text
FileCheck V0.1 · 文件扫描 / 批量备份 / 迁移 / 恢复

1. 检查 Everything / ES 环境
2. 扫描并处理（推荐入口）
3. 使用已有扫描结果批量备份
4. 使用已有扫描结果迁移（会进入源文件移除确认）
5. 验证已有备份
6. 从备份恢复到原路径
7. 继续未完成的迁移
8. 运行本机自检
9. 显示高级命令帮助
0. 退出
```

## 3. 扫描范围

菜单中的扫描支持两种范围：

```text
1. Everything 当前已索引的全部范围
2. 指定盘符或目录（推荐）
```

指定范围示例：

```text
C:\
D:\Work
C:\Users\Public\Documents
```

命令行等价写法：

```powershell
filecheck scan --path D:\Work
```

不指定 `--path` 时，FileCheck 查询 Everything 当前已有索引范围。指定 `--path` 时，FileCheck 通过 ES `-path` 在 Everything 端先限制搜索范围，再进行关键词查询。

`--match-path`/菜单中的“关键词同时匹配目录路径”只控制关键词是否也检查完整路径，不改变扫描范围。

## 4. 扫描后的容量提示

菜单读取 `scan-results.json` 中每个可访问候选的文件大小并给出：

```text
候选文件
可统计大小的文件数
候选数据总量
目录备份建议至少可用空间
ZIP 备份过程建议至少可用空间
```

当前空间估算与备份实现保持一致：

```text
目录备份：候选总字节数 + 安全余量
ZIP：2 × 候选总字节数 + 安全余量
```

安全余量最少 16 MiB、最多 512 MiB，中间按候选数据量约 5% 计算。

ZIP 的 `2×` 是创建过程的保守峰值估算，因为当前实现会同时保留已经验证的 staging 副本和临时 ZIP。最终 ZIP 文件大小由压缩率决定，不等于该峰值估算。

若扫描结果中存在当前不可访问的文件，其大小无法统计，菜单会明确提示空间值只是下限；实际开始备份时仍会重新检查文件和目标剩余空间。

用户输入备份目标目录后，菜单还会尝试显示该目标所在磁盘的当前剩余空间，并与当前备份模式的建议空间进行比较。真正的 `create_backup()` 仍执行严格的空间门禁，菜单提示不是替代校验。

## 5. 扫描后的默认处理

扫描结束后不要求逐个确认候选文件，而是针对完整扫描结果选择批量动作：

```text
1. 目录方式批量备份全部候选（推荐，源文件不动）
2. ZIP 方式批量备份全部候选（源文件不动）
3. 目录方式迁移：备份验证后移除候选源文件
4. ZIP 方式迁移：备份验证后移除候选源文件
5. 只保存扫描结果，暂不处理
0. 返回
```

`backup` 永远不会移除源文件。

`migrate` 仍保持破坏性操作门禁：

```text
批量备份
→ 整批 verify
→ 全部源文件再次 SHA-256 复核
→ 一次 YES 批次确认
→ 逐文件即时复核
→ 只移除 manifest 中记录的源文件
→ 保存 migration state
```

菜单不会自动传递 `--yes`，因此不会绕过最后一次源文件移除确认。

## 6. 扫描结果存放

菜单模式下，扫描结果默认写到 FileCheck 本机运行数据目录，并使用带时间戳的文件名，例如 Windows：

```text
%LOCALAPPDATA%\FileCheck\scan-results-20260907-140000.json
```

这样避免把包含真实文件路径的扫描结果默认写入代码仓库工作目录。

命令行高级模式仍可以通过 `--output` 自行指定位置。

## 7. 备份目标建议

建议把备份目标放在扫描范围之外，最好是另一块磁盘或专用备份目录。如果备份目标位于本次扫描范围内部，菜单会提示：后续再次扫描时可能把备份副本也检索出来。
