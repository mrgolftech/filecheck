# FileCheck v0.2.4

本版本在 v0.2.3 备份/恢复与历史备份保护机制基础上，新增**双模式文件扫描与备份**。不修改既有目录备份结构和 SHA-256 安全验证机制。

## 新增：两种互斥扫描模式

1. **文件类型 + 关键词（默认，兼容旧行为）**：继续使用 `config/rules.json` 中的 `keywords`、`extensions` 匹配，并按关键词标注高风险、敏感和复核。
2. **仅按扩展名**：不要求文件名或路径命中关键词，只要最后的扩展名属于选定列表就纳入候选；所有结果标为「复核」，不据扩展名推断敏感性。GUI 扫描页面新增模式单选按钮和可编辑列表，CLI 可传 `--mode extensions` 和 `--extensions`。

扩展名输入示例：`pdf, docx, xlsx, dwg`。支持前导点与逗号/分号/空白分隔、大小写不敏感、自动去重。拒绝空列表与可能插入查询语法的非法值；只精确匹配**最后一个**后缀，不支持 `*.tar.gz` 多段扩展名。

## 使用方法

GUI：完成「设置」和索引 → 「扫描」选择模式 → 在新模式输入扩展名 → 开始扫描 → 「扫描结果」人工核对 → 「备份」执行预检和目录备份。

CLI：

```powershell
# 原模式（默认）
FileCheck.exe scan

# 新模式（文件名无需关键词）
FileCheck.exe scan --mode extensions --extensions ".pdf,docx,xlsx,dwg" --output scan-results-extensions.json

# 继续使用原备份流程
FileCheck.exe backup --from-scan scan-results-extensions.json --dest "D:/FileCheckBackup"
```

扫描结果 JSON 增加 `scan_mode`、`selected_extensions`；CSV 增加「命中扩展名」列。旧扫描结果读取和备份格式仍兼容。

## 安全与兼容性

- 两种模式共用 FileCheck 专用 Everything 1.4 索引；继续排除程序目录、备份根目录及已识别的历史 FileCheck 备份。
- 扩展名结果达到单类型查询上限时直接失败，避免误以为得到了完整备份范围。
- 修改模式或扩展名后旧候选失效，必须重新扫描；备份继续预检不可访问文件、空间和源文件。
- **扫描和备份都不会自动删除原始文件**；源文件删除是独立且需人工确认的操作。
- 沿用目录式备份、SHA-256 校验和按原路径恢复；备份 manifest schema 不变。
- Windows 7 SP1、Windows 10、Windows 11 的 x64 GUI 和 CLI，以及 Windows 7 SP1 的 x86 CLI，沿用 Python 3.8.10 / PyInstaller 5.13.2 构建基线。
- 旧索引如仍处于 v0.2.2 或更早策略，须重新创建索引以纳入 Hidden/System 文件；若 v0.2.3 索引已就绪则无需仅为双模式功能重建。

## 发布产物

- `FileCheck-v0.2.4-gui-x64.zip`：Windows 7 SP1 / 10 / 11 64 位 GUI 完整版（内含 CLI）。
- `FileCheck-v0.2.4-cli-x64.zip`：Windows 7 SP1 / 10 / 11 64 位命令行。
- `FileCheck-v0.2.4-cli-x86.zip`：Windows 7 SP1 32 位命令行。
- `SHA256SUMS-v0.2.4.txt`：三个发布包 SHA-256 校验值。

正式包经 GitHub Actions 构建、自测、ZIP 内容检查和 SHA-256 计算后发布。构建环境验证不能完全替代特定 Windows 7 设备的真机确认。
