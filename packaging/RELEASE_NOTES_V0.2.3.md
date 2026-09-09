# FileCheck v0.2.3

FileCheck v0.2.3 是对 v0.2.2 历史备份保护机制的补完修复版本，并扩大 Everything 索引覆盖范围。建议所有 v0.2.x 用户升级后重新创建/更新一次 FileCheck 专用索引。

## 1. 历史备份识别不再依赖外层目录名

此前旧版本历史备份在没有 `.filecheck-backup` 标记时，识别逻辑仍可能依赖备份批次目录名与 `manifest.batch_id` 的一致性。

v0.2.3 改为以有效 FileCheck `manifest.json` + `files/` 结构作为备份身份基础。即使用户把：

```text
FC-20260909-113220-a07f8670
```

改名为：

```text
FC-2
```

或者移动到其他目录，仍会被识别为历史 FileCheck 备份并受到保护。

新版本的 `.filecheck-backup` 仍作为持久身份标记使用；即使该 marker 缺失、损坏或与 manifest 不一致，一个结构有效的 FileCheck 历史备份也不会因此降级成普通源目录。

## 2. Hidden / System 文件与目录现在纳入 Everything 索引

FileCheck 专用 Everything 配置现在明确设置：

```ini
exclude_hidden_files_and_folders=0
exclude_system_files_and_folders=0
```

因此索引会覆盖：

- 普通文件和目录；
- Hidden 属性文件；
- Hidden 属性目录；
- System 属性文件；
- System 属性目录；
- 同时具有 Hidden + System 属性的文件和目录。

仍然会继续排除 FileCheck 程序目录和配置的备份根目录等明确排除路径。

## 3. 旧索引策略强制升级

本版本增加 `index_policy_version=2`，并在索引状态中记录 Hidden / System 的纳入策略。

如果升级后检测到旧索引状态，FileCheck 不会直接继续正式扫描，而会要求重新创建/更新索引，避免继续使用一个本来没有收录 Hidden/System 内容的旧 Everything 数据库。

因此从 v0.2.2 或更早版本升级到 v0.2.3 后，请先执行一次“创建 / 更新索引”。

## 4. GUI 与 CLI 统一历史备份扫描保护

历史备份候选过滤已经抽取为公共 `scan_guard` 能力，GUI 与 CLI `scan` 共用同一套逻辑。

现在无论通过 GUI、CLI 还是命令行菜单进行扫描：

```text
Everything 返回候选
→ 检查候选是否位于合法 FileCheck 历史备份中
→ 历史备份候选自动排除
→ 只保留普通源文件候选
```

CLI 扫描结果 JSON 也与 GUI 对齐，记录：

- `protected_backup_batches`
- `excluded_backup_items`

并在控制台提示自动排除的候选数量和备份批次数。

## 5. 多层安全保护继续保留

即使异常情况下历史备份文件绕过扫描候选过滤，核心备份入口仍会拒绝将其再次作为普通源文件备份；源文件删除阶段也会再次执行独立硬保护。

因此保护链路为：

```text
Everything 查询层
→ 扫描候选结构过滤
→ create_backup 核心保护
→ 删除预检保护
→ 删除运行时硬保护
```

历史 FileCheck 备份不会仅因为改名、搬移或更换 backup root 而重新进入普通文件处理链路。

## 兼容性

- `manifest.json` schema version 仍为 1；
- v0.2.0 / v0.2.1 / v0.2.2 现有目录备份无需迁移；
- 备份内容与 SHA-256 校验语义不变；
- Windows 7 深层目录紧凑存储和短原子临时文件机制继续保留；
- GUI 与 CLI 继续使用相同核心安全逻辑；
- 升级后需要重新创建/更新一次 Everything 专用索引，以应用新的 Hidden/System 索引策略。

## 回归验证

本版本已验证：

- 旧备份目录改名为 `FC-2` 后仍受保护；
- marker 损坏不会使合法备份失去保护；
- 无效伪 manifest 不会把普通目录误判为历史备份；
- Hidden/System Everything INI 策略正确生成；
- 旧索引策略会要求重建；
- GUI 和 CLI 使用统一历史备份候选过滤；
- CLI 扫描会排除改名后的历史备份，并写入保护元数据；
- Ubuntu Python 3.10 / 3.12 完整测试通过；
- Windows Python 3.10 / 3.12 完整测试、GUI smoke test 和 backup/restore selftest 通过；
- Python 3.8 Win7 GUI 兼容编译、模块导入和 GUI 构造检查通过。

## 发布包

- `FileCheck-v0.2.3-gui-x64.zip` — GUI 完整版，Windows 7 SP1 / 10 / 11 64 位，推荐普通用户使用；包内含 x64 CLI。
- `FileCheck-v0.2.3-cli-x64.zip` — Windows 7 SP1 / 10 / 11 64 位 CLI。
- `FileCheck-v0.2.3-cli-x86.zip` — Windows 7 SP1 32 位 CLI。
- `SHA256SUMS-v0.2.3.txt` — 三个正式 ZIP 的 SHA-256 校验值。
