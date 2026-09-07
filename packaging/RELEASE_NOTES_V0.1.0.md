# FileCheck v0.1.0

首个正式 Win64 发布版。

## 主要能力

- 复用 Everything 1.4 索引，按关键词和目标文件类型快速扫描。
- 扫描结果保存为 JSON，支持大量候选文件批量处理。
- 目录备份默认保持源盘符、目录层级和原始文件名，便于人工检查。
- 备份完成后逐文件执行大小和 SHA-256 全量验证。
- 支持独立再次验证已有备份。
- 支持在已验证备份基础上再次核对源文件后批量删除源文件。
- 支持依据 manifest 恢复到原始路径。
- 批量复制支持操作状态和中断续传。
- Win64 发布包内置 ES CLI 1.1.0.37 x64，位于 `tools\es.exe`。

## 环境要求

- Windows x64。
- Everything 1.4.x 已安装、正在运行并完成索引。
- FileCheck 发布包内已包含 ES CLI 1.1.0.37 x64。

## 推荐流程

1. 按 README 中的“正式使用前准备”完成 Windows 临时目录、最近项目记录和 Everything 索引准备。
2. 启动 `FileCheck.exe`，先执行菜单 1 检查 Everything / ES 环境。
3. 菜单 2 扫描，建议选择 Everything 当前已索引的全部范围，并对“关键词是否同时匹配目录路径”选择 N。
4. 保存扫描 JSON 后，从主菜单 3 使用该 JSON 进行目录方式批量备份。
5. 主菜单 5 对备份再次验证。
6. 确认备份无误后，主菜单 7 删除已验证备份对应的源文件。
7. 删除完成后在 Everything 中强制重建索引，再次检查。
8. 妥善保存整个备份批次目录；后续恢复时使用主菜单 6。

## 第三方组件

本发布包包含 voidtools 的 Everything Command-line Interface (ES) 1.1.0.37 x64，按 MIT License 再分发。许可文本随包提供于 `THIRD-PARTY-NOTICES.txt`。
