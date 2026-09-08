# FileCheck v0.1.1

FileCheck v0.1.1 是一次面向实际 Windows 使用场景的完整流程升级，重点改进了便携 Everything 索引、目录备份、安全删除、恢复体验和 Windows 7 兼容打包。

## 发布包

本版本提供 3 个正式便携包：

- `FileCheck-v0.1.1-win10plus-x64.zip` — Windows 10 / 11 64 位
- `FileCheck-v0.1.1-win7-x64.zip` — Windows 7 SP1 64 位
- `FileCheck-v0.1.1-win7-x86.zip` — Windows 7 SP1 32 位

每个包均包含：

- `FileCheck.exe`
- `config\rules.json`
- 对应架构的 `tools\Everything.exe`
- 对应架构的 `tools\es.exe`
- 平台说明文档
- `THIRD-PARTY-NOTICES.txt`
- `SHA256SUMS.txt`

无需安装 Python，也不要求系统预先安装 Everything。

## 主要变化

### 1. 独立便携 Everything 索引

- 内置 Everything 1.4.1.1032 + ES 1.1.0.37。
- 使用独立 `FileCheck` 实例，不依赖、不修改用户默认 Everything。
- 索引配置和数据库均保存在程序目录：
  - `runtime\everything\Everything.ini`
  - `runtime\everything\Everything-FileCheck.db`
  - `runtime\everything\index-config.json`
- NTFS 本地固定磁盘优先使用 MFT/USN 快速索引。
- 不安装永久 Windows 服务，不弹出 Everything 搜索窗口。
- 自动排除 FileCheck 程序目录和备份根目录。

### 2. 交互式菜单重构

V0.1.1 主菜单精简为正常工作流：

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

`selftest`、高级命令帮助等开发/诊断功能继续保留为 CLI，不再占用普通菜单。

### 3. 扫描规则可见、可编辑

进入扫描前会显示：

- 当前关键词分组；
- 当前文件扩展名；
- 实际使用的 `config\rules.json` 路径。

修改规则文件后重新执行扫描即可生效。

### 4. 新建备份统一为目录方式

- V0.1.1 不再创建 ZIP 备份。
- 按原始盘符和目录结构镜像保存文件。
- 同名但不同绝对路径的文件不会互相覆盖。
- 复制期间使用 `.FC-....incomplete` 暂存目录。
- 复制完成并通过 SHA-256 校验后才发布正式 `FC-*` 批次。
- 支持继续未完成的备份复制任务。

### 5. manifest 与删除状态彻底分离

`manifest.json` 只记录备份事实：

- `source_path`
- `backup_path`
- `size`
- `mtime_ns`
- `sha256`

后续删除状态单独写入：

- `source-removal.json`
- `not-deleted.txt`（仅失败/reappeared 项存在时生成）

### 6. 删除安全与性能改进

第一次删除前：

1. 完整验证整个备份；
2. 对全部源文件执行一次 size + SHA-256 强复核；
3. 任一文件异常则整批删除不启动；
4. 全部通过后要求一次 `YES` 确认。

确认后：

- 不再逐文件重复计算完整 SHA-256；
- 使用预检时记录的 size / mtime / 文件标识等元数据快照做快速检查；
- 文件在预检后发生变化时跳过并标记失败；
- Windows“只读”属性自动处理；
- ACL、文件占用、杀毒软件拦截等真实错误仍安全失败；
- 删除时发现文件已不存在则记录 `already_absent` 并继续；
- 删除状态按批次写入，减少大量文件场景下的状态文件写入开销。

继续删除时会重新验证备份，并对待重试文件重新做强校验。

如果已经 `deleted` / `already_absent` 的路径后来重新出现，会标记 `reappeared`，不会自动再次删除，避免误删后来生成的新数据。

### 7. 恢复流程增强

- 恢复前先完整验证整个备份 SHA-256。
- 选择恢复冲突策略后会明确提示“正在执行恢复前完整性校验”，避免用户误以为程序无响应。
- 默认冲突策略为 `skip`，不覆盖现有文件。
- `rename` 可恢复为新名称。
- `overwrite` 使用临时文件 + SHA-256 + 原子替换。
- 恢复后的最终目标再次执行 size + SHA-256 校验。
- skip 项写入 `restore-skipped.txt`，并区分“内容相同”与“内容不同/无法确认”。

### 8. 兼容 V0.1.0 旧 ZIP 备份

V0.1.1 本身不直接读取 ZIP。

如需恢复 V0.1.0 ZIP：

1. 使用 Windows 或第三方工具完整解压；
2. 确认解压目录包含 `manifest.json` 和 `files\`；
3. 把解压目录交给 V0.1.1。

旧 manifest 中即使仍是 `mode=zip`，只要目录结构完整即可验证和恢复。

## Windows 构建路线

- Win10/11 x64：Python 3.12 + PyInstaller 6
- Win7 x64：Python 3.8.10 x64 + PyInstaller 5.13.2
- Win7 x86：Python 3.8.10 x86 + PyInstaller 5.13.2

Win7 x86 构建额外验证 `FileCheck.exe` PE machine 为 `0x014C`。

所有发布包在 GitHub Actions 中执行回归测试、`selftest`、可执行文件 smoke test、Everything/ES 官方包 SHA-256 校验和最终便携包内容验证。

## 使用建议

推荐始终按以下顺序操作：

```text
索引 → 扫描 → 人工核对 → 创建备份 → 人工检查 → 检查备份 → 删除源文件
```

恢复属于独立的后续操作。

交互式运行建议始终“以管理员身份运行”，尤其是 NTFS MFT/USN 索引以及受保护路径下的删除/恢复场景。
