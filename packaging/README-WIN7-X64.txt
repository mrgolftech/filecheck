FileCheck v0.1.0 - Windows 7 SP1 x64 compatibility package
===========================================================

适用系统
--------
- Windows 7 SP1 64 位。
- 该版本使用 Python 3.8.10 + PyInstaller 5.13.2 构建，用于兼容 Windows 7。
- Windows 10/11 建议优先使用 win10plus-x64 发布包。

环境要求
--------
1. Everything 1.4.x 已安装、正在运行并完成索引。
2. 本包已附带 tools\es.exe（Everything Command-line Interface 1.1.0.37 x64）。
3. 建议 Windows 7 已安装全部可用系统更新。若系统缺少 Universal C Runtime / VC 运行库相关更新，程序可能无法启动，应先补齐系统运行库更新。

推荐流程
--------
1. 运行 FileCheck.exe。
2. 菜单 1：检查 Everything / ES 环境。
3. 菜单 2：扫描；建议选择 Everything 当前已索引的全部范围，关键词是否匹配目录路径选择 N。
4. 扫描完成后保存 scan-results JSON。
5. 菜单 3：使用已有扫描结果进行目录方式批量备份。
6. 人工检查备份目录。
7. 菜单 5：再次验证已有备份。
8. 确认无误后，菜单 7：删除已验证备份对应的源文件。
9. 删除后在 Everything 中强制重建索引并再次检查。
10. 妥善保存完整备份批次目录；将来通过菜单 6 恢复到原路径。

注意事项
--------
- backup 不会删除源文件。
- 删除源文件前，FileCheck 会重新验证完整备份并重新核对源文件，最后还需要一次 YES 确认。
- 目录备份保持源盘符、目录层级和原始文件名，便于人工检查。
- Windows 7 的长路径能力弱于 Windows 10/11。虽然 FileCheck 对 Windows 文件 I/O 做了长路径兼容处理，但极端超长路径仍需重点实机验证。
- 本兼容包必须在真实 Windows 7 SP1 x64 上完成最终运行验证，GitHub Actions 构建环境本身不是 Windows 7。

第三方组件
----------
本包包含 voidtools 的 Everything Command-line Interface (ES) 1.1.0.37 x64，按 MIT License 再分发。详见 THIRD-PARTY-NOTICES.txt。
