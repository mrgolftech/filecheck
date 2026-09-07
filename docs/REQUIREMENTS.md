# FileCheck V0.1.1 需求说明

## 1. 产品目标

FileCheck 用于 Windows 终端离线文件自查、批量目录备份、完整性验证、源文件安全删除和原路径恢复。

V0.1.1 重点解决：

1. 随软件携带 Everything 1.4 + ES，建立 FileCheck 自己的便携索引环境；
2. 面对数百/数千候选时按整批处理，不要求逐文件确认；
3. 目录备份保留源盘符、目录层级、原始文件名和 SHA-256；
4. 人工检查和再次 verify 后，才允许显式删除 manifest 对应源文件；
5. 删除单文件失败不影响其余安全项，支持状态记录和继续；
6. 将来可依据不可变 manifest 恢复到各自原路径。

关键词命中只代表候选，不等同于违规或最终文件性质认定。

## 2. 产品边界

V0.1.1 是**文件自查和备份恢复工具**，不是系统痕迹清理工具。

不提供：

- Recent / Jump List 清理；
- 浏览器历史清理；
- Office/WPS MRU 清理；
- USBSTOR / 注册表清理；
- 强制解锁文件、杀进程；
- 递归删除候选所在父目录。

## 3. 便携 Everything 索引

### 3.1 随包组件

正式 Windows 包包含：

```text
tools\Everything.exe   Everything 1.4.1.1032 x64 portable
tools\es.exe           ES 1.1.0.37 x64
```

不要求目标机器预先安装 Everything。

### 3.2 专用实例

FileCheck 启动 Everything 实例名固定为：

```text
FileCheck
```

配置与数据库保存在：

```text
runtime\everything\Everything.ini
runtime\everything\Everything.db
runtime\everything\index-config.json
```

不得修改用户可能已有的默认 Everything 实例和索引。

### 3.3 索引范围

用户在首次配置时选择一个或多个磁盘/目录，例如：

```text
C:\
D:\
G:\Project
```

同时设置统一备份根目录。

FileCheck 必须自动排除：

- FileCheck 程序目录；
- 统一备份根目录。

## 4. 扫描

### 4.1 规则

规则由 `config/rules.json` 管理，支持关键词分级和扩展名集合。

默认按文件名匹配；只有显式启用 `--match-path` 时才把完整路径纳入关键词匹配。

### 4.2 查询实现

通过 ES CLI 查询 FileCheck 专用 Everything 实例：

- ES 版本必须 >= 1.1.0.37；
- 使用 `-argv`，避免 Python/PowerShell 参数解析歧义；
- 使用 UTF-8 导出通道，保留中文、NBSP 等 Unicode 路径；
- 一个关键词与全部扩展名组合查询；
- 结果按规范化绝对路径去重；
- 同一文件命中多个关键词时合并命中原因并取最高 severity。

### 4.3 扫描结果

默认保存：

```text
scan-results\scan-results-*.json
scan-results\scan-results-*.csv
```

JSON 顶层至少记录：

```text
schema_version
created_at
engine
instance
everything_version
selected_roots
excluded_roots
match_path
path_filter
rules.file
rules.sha256
items[]
```

不得把规则文件绝对路径写入扫描结果。

## 5. 批量目录备份

### 5.1 默认全部候选

`backup --from-scan` 默认处理扫描 JSON 中全部候选。`--select` 仅作为高级过滤能力保留。

### 5.2 只支持目录备份

V0.1.1 不创建 ZIP 备份，也不直接读取 ZIP 文件。

源文件：

```text
C:\ProjectA\报告.pdf
D:\资料\报告.pdf
```

映射为：

```text
files\C\ProjectA\报告.pdf
files\D\资料\报告.pdf
```

不同路径中的同名文件必须独立保存，不能拍平。

### 5.3 发布门禁

备份流程：

```text
预检查目标空间
→ .FC-....incomplete
→ 逐文件复制并计算 SHA-256
→ 检查源文件复制前后是否稳定
→ 写 manifest
→ 整批逐文件 size + SHA-256 verify
→ 全部通过后原子发布为 FC-* 目录
```

任何未通过完整验证的暂存目录都不能被当成正式备份。

## 6. manifest.json

manifest 是备份创建时的不可变恢复清单。

每个 item 至少记录：

```text
source_path
backup_path
size
mtime_ns
sha256
backup_verified
```

V0.1.1 **不得**写入 `source_removed` 字段，无论顶层还是 item。

后续删除状态不能回写 manifest。

## 7. 源文件删除

### 7.1 进入条件

删除入口必须执行：

```text
完整 verify 备份
→ 全部 source_path 重新检查普通文件属性
→ size 校验
→ SHA-256 校验
→ hash 前后 stat 稳定性检查
→ 任一失败：删除阶段不启动
→ 全部通过：一次批次级 YES 确认
```

### 7.2 删除规则

删除阶段：

- 每个文件删除前再次即时复核；
- 仅对 manifest 列出的 `source_path` 调用 unlink；
- 不删除父目录；
- 不删除空目录；
- 不扫描并删除同目录其他文件。

### 7.3 单文件失败

文件锁、权限或内容变化时：

- 当前文件标记失败；
- 不强制处理；
- 继续后续文件；
- 状态逐文件 checkpoint。

状态位置：

```text
<backup>\source-removal.json
```

有失败项时：

```text
<backup>\not-deleted.txt
```

完成全部删除后 `not-deleted.txt` 应自动移除。

### 7.4 Resume 保护

resume 前必须再次完整 verify 备份。

只重试 `pending/failed`。

如果之前记录为 `deleted/already_absent` 的源路径后来重新出现，标记为 `reappeared`，不得自动再次删除，即使内容与旧备份完全相同。

## 8. 恢复

恢复入口只接受目录。

流程：

```text
完整 verify 备份
→ Windows 原始驱动器/共享可用性预检查
→ 逐 item 恢复
→ 同目录临时文件
→ size + SHA-256 校验
→ 成功后原子替换/发布
→ 最终再次 size + SHA-256
```

冲突策略：

```text
skip
rename
overwrite
```

默认 `skip`。

## 9. V0.1.0 ZIP 兼容

V0.1.1 不包含 ZIP 解压逻辑。

用户可先人工完整解压旧 ZIP。只要解压目录包含：

```text
manifest.json
files\...
```

FileCheck 应接受该目录；旧 manifest 中 `mode=zip` 不需要修改。

## 10. 可续传备份

大量文件复制使用操作状态：

- 已复制且重新校验有效的暂存文件不重复复制；
- 单文件暂时不可访问可以记录失败；
- 中断后可继续；
- 完整批次仍须全量 verify 后才发布。

## 11. 当前可靠性范围

V0.1.1 保证的核心对象是普通文件：

- 文件内容；
- 绝对原路径；
- 目录映射；
- 文件大小；
- SHA-256；
- 基础 mtime。

暂不承诺完整保留/恢复：

- ACL / owner / audit；
- EFS；
- ADS；
- 硬链接；
- 稀疏属性；
- 重解析点/符号链接语义。

## 12. 平台与发布

### Windows 10/11

正式便携包使用 Python 3.12 + PyInstaller 6 构建。

### Windows 7 SP1 x64

兼容包固定采用：

```text
Python 3.8.10
PyInstaller 5.13.2
```

GitHub Actions 构建通过不等价于真实 Win7 运行通过；正式发布前必须重新执行 Win7 实机验收。
