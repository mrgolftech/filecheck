# FileCheck v0.2.0

FileCheck v0.2.0 是一次以图形界面和正式便携发布为核心的版本升级。在保留 v0.1.1 已验证的扫描、目录备份、SHA-256 校验、安全删除和恢复能力基础上，本版本新增 CustomTkinter GUI，并统一 GUI 与 CLI 的 Everything 专用索引、备份批次和运行配置。

## 正式发布包

本版本提供 3 个正式便携包：

- `FileCheck-v0.2.0-gui-x64.zip` — Windows 7 SP1 / Windows 10 / Windows 11 64 位，推荐普通用户使用；包内同时提供高级 CLI。
- `FileCheck-v0.2.0-cli-x64.zip` — Windows 7 SP1 / Windows 10 / Windows 11 64 位命令行版。
- `FileCheck-v0.2.0-cli-x86.zip` — Windows 7 SP1 32 位命令行兼容版。
- `SHA256SUMS-v0.2.0.txt` — 三个正式 ZIP 包的 SHA-256 校验值。

所有包均内置对应架构的 Everything 1.4.1.1032 与 ES 1.1.0.37，不需要安装 Python，也不要求系统预装 Everything。

## 主要变化

### 1. 新增 GUI 图形界面

- 使用 Python + CustomTkinter 实现便携 GUI。
- GUI 覆盖设置、索引、扫描、结果查看、备份、源文件删除和恢复主要流程。
- GUI 长耗时操作使用后台任务执行，避免阻塞界面。
- GUI 自动检测管理员权限，并对索引创建、源文件删除和覆盖恢复等高风险操作实施权限限制。
- GUI 和 CLI 使用同一套核心业务逻辑，不单独复制备份、删除或恢复实现。

### 2. 统一单一备份根目录

设置中只配置一个备份根目录，例如：

```text
H:\FileCheckBackup
```

每次备份自动创建独立批次：

```text
H:\FileCheckBackup\FC-YYYYMMDD-HHMMSS\
```

源文件删除和恢复页面只扫描备份根目录的直接子目录，并以 `manifest.json` 判断有效批次。多个批次时默认选择最新批次，也支持手动选择移动过的旧备份目录。

### 3. Everything 专用数据库统一为固定名称

GUI 与正式 CLI 入口均使用独立 `FileCheck` Everything 实例，数据库固定为：

```text
runtime\everything\Everything-FileCheck.db
```

本版本修复了 GUI 直接调用索引服务时可能退回旧 `Everything.db` 的问题，并增加数据库真实落盘、非空和状态路径一致性检查。只有持久化数据库有效时才允许扫描。

### 4. Everything 生命周期与 IPC 稳定性改进

- Everything 以隐藏后台方式启动，不弹出搜索窗口。
- 启动后等待命名实例 IPC 真正可用。
- 停止实例时等待 IPC 真正消失，减少快速重建索引时的竞争条件。
- 显式使用 ES `-save-db` 持久化数据库。
- 索引构建失败或取消时会使旧状态失效，避免 GUI 错误显示“索引就绪”。

### 5. 备份批次选择体验改进

源文件删除和恢复页面均使用统一批次选择器：

- 自动发现统一备份根目录下的有效 `FC-*` 批次；
- 一个批次自动选择；
- 多个批次按名称倒序，默认最新；
- 页面重新显示时自动刷新；
- 保留“手动选择其他目录”用于历史或移动备份。

### 6. 恢复安全增强

恢复仍会先完整验证整个备份。`overwrite` 模式下：

- 临时复制或原子替换前的单文件操作系统错误会记录为跳过错误，并继续处理其他文件；
- 成功替换后的最终同步或 SHA-256 校验异常仍视为致命错误；
- 跳过和错误项写入 `restore-skipped-YYYYMMDD-HHMMSS.txt`。

### 7. 正式包统一附带 README

三个正式 ZIP 包根目录均包含仓库当前 `README.md`，其中保留了正式操作前的人工清理步骤，包括：

- 清空 Windows 回收站；
- `%temp%`；
- `C:\Windows\Temp`；
- `recent`；
- `AutomaticDestinations`；
- `CustomDestinations`。

FileCheck 不会自动执行这些清理，也不会自动处理浏览器历史、USBSTOR、Office/WPS MRU 或注册表记录。

## 兼容性与构建基线

- GUI x64：Python 3.8.10 x64 + PyInstaller 5.13.2 + CustomTkinter 5.2.2。
- CLI x64：Python 3.8.10 x64 + PyInstaller 5.13.2。
- CLI x86：Python 3.8.10 x86 + PyInstaller 5.13.2，并验证 PE machine 为 `0x014C`。

GitHub Actions 会执行 Python 3.8 编译检查、完整回归测试、CLI `selftest`、可执行文件 smoke test、Everything/ES 官方下载 SHA-256 校验、最终 ZIP 内容检查以及正式包 SHA-256 生成。

## 推荐使用顺序

```text
正式操作前人工清理
→ 设置统一备份根目录
→ 创建/更新 Everything 专用索引
→ 扫描候选
→ 人工核对
→ 创建备份
→ 检查备份
→ 按需单独执行源文件删除
→ 必要时恢复
```

扫描和备份不会自动删除源文件。源文件删除始终是独立高风险操作。

> Windows 7 兼容构建已通过 CI 和打包 smoke test；在具体 Windows 7 SP1 目标机器正式部署前，仍建议做一次实际运行验证。
