FileCheck v0.1.1 - Windows 7 SP1 32-bit (x86)
================================================

适用系统
--------
- Windows 7 SP1 32 位（x86）
- 这是专门使用 32 位 Python 3.8.10 + PyInstaller 5.13.2 构建的兼容版本。
- 不要在 64 位系统上优先使用此包；64 位 Windows 建议使用对应的 x64 包。

便携包内容
----------
FileCheck.exe
config\rules.json
tools\Everything.exe
tools\es.exe
THIRD-PARTY-NOTICES.txt
SHA256SUMS.txt

说明
----
1. Everything 采用官方 1.4.1.1032 x86 Portable 版本。
2. ES 采用官方 1.1.0.37 x86 版本。
3. FileCheck 使用独立的 Everything 实例，运行数据保存在程序目录：
   runtime\everything\Everything.ini
   runtime\everything\Everything.db
4. 扫描结果保存在：
   scan-results\
5. 对 NTFS 本地磁盘优先使用 Everything MFT/USN 快速索引；建立/重建索引时可能需要管理员权限。
6. 新建备份仅使用目录备份，不创建 ZIP。
7. 备份完成后应先 verify，再执行源文件删除。
8. 删除失败的文件会保留，并可继续删除任务；恢复默认冲突策略为 skip。

Windows 7 注意事项
------------------
- 请使用 Windows 7 SP1。
- 若系统缺少较新的 VC/UCRT 运行组件，可能需要先安装微软官方 Windows 7 更新/运行库。
- 32 位进程可用虚拟地址空间明显小于 64 位版本，因此特别大的扫描结果或极端数量文件场景更推荐使用 64 位系统和 x64 包。
- 该构建仍需在真实 Windows 7 32 位机器完成最终实机验收后再视为正式兼容基线。
