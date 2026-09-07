# FileCheck v0.1.0

FileCheck v0.1.0 提供两个 Windows x64 发布包，请按系统版本选择：

- **`FileCheck-v0.1.0-win10plus-x64.zip`**：Windows 10 / Windows 11 x64，使用 Python 3.12 + PyInstaller 6 构建，推荐用于较新 Windows。
- **`FileCheck-v0.1.0-win7-x64.zip`**：Windows 7 SP1 x64 兼容版，使用 Python 3.8.10 + PyInstaller 5.13.2 构建。

两个发布包都包含 `tools\es.exe`（Everything Command-line Interface 1.1.0.37 x64）。Everything 1.4.x 本体仍需要安装、启动并完成索引。

> Windows 7 兼容包已经通过 Python 3.8 源码编译、自动化回归、PyInstaller 构建和 EXE 自检，并于 2026-09-07 在真实 Windows 7 64 位电脑上完成启动与实际使用验收，用户反馈运行正常。

## 主要能力

- 复用 Everything 1.4 索引，按关键词和目标文件类型快速扫描。
- 扫描结果保存为 JSON，支持大量候选文件批量处理。
- 目录备份默认保持源盘符、目录层级和原始文件名，便于人工检查。
- 备份完成后逐文件执行大小和 SHA-256 全量验证。
- 支持独立再次验证已有备份。
- 支持在已验证备份基础上再次核对源文件后批量删除源文件。
- 支持依据 manifest 恢复到原始路径。
- 批量复制支持操作状态和中断续传。

## 环境要求

### Windows 10 / 11 x64

使用 `FileCheck-v0.1.0-win10plus-x64.zip`。

### Windows 7 SP1 x64

使用 `FileCheck-v0.1.0-win7-x64.zip`。建议 Windows 7 已安装全部可用系统更新；若系统缺少 Universal C Runtime / VC 运行库相关更新，可能仍需先补齐系统运行库更新。

## 推荐流程

1. 按 README 中的“正式使用前准备”完成 Windows 临时目录、最近项目记录和 Everything 索引准备。
2. 启动 `FileCheck.exe`，先执行菜单 1 检查 Everything / ES 环境。
3. 菜单 2 扫描，建议选择 Everything 当前已索引的全部范围，并对“关键词是否同时匹配目录路径”选择 N。
4. 保存扫描 JSON 后，从主菜单 3 使用该 JSON 进行目录方式批量备份。
5. 主菜单 5 对备份再次验证。
6. 确认备份无误后，主菜单 7 删除已验证备份对应的源文件。
7. 删除完成后在 Everything 中强制重建索引，再次检查。
8. 妥善保存整个备份批次目录；后续恢复时使用主菜单 6。

## 验收状态

- Windows 10/11 x64：自动化 CI、EXE selftest 和既有 Windows 实机流程已通过。
- Windows 7 SP1 x64：兼容构建自动化回归通过；2026-09-07 已在真实 Win7 64 位环境完成启动和实际使用验收。
- 后续若升级 Win7 构建所用 Python/PyInstaller，或修改 Windows 路径/文件 I/O 关键实现，应重新执行 Win7 实机兼容回归。

## 第三方组件

发布包包含 voidtools 的 Everything Command-line Interface (ES) 1.1.0.37 x64，按 MIT License 再分发。许可文本随包提供于 `THIRD-PARTY-NOTICES.txt`。
