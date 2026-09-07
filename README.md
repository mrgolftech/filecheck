# FileCheck

FileCheck 是一个面向 Windows 终端的离线文件自查、人工复核、迁移备份与恢复工具。

## 核心原则

- **优先使用 Everything 1.4 索引进行快速文件枚举**，避免对磁盘做低效的全盘递归遍历。
- Everything 负责“找文件”，FileCheck 负责规则匹配、人工复核、迁移、校验、记录与恢复。
- 默认只读扫描，不自动删除文件、不清理浏览器/Recent/注册表等审计痕迹。
- 任何迁移动作必须保留源路径、目标路径、文件大小、时间戳和 SHA-256 校验值。
- 支持将文件复制到指定目录或打包备份，并在之后依据 manifest 恢复到原路径。
- 扫描结果、真实文件名、主机名、路径、备份包等运行数据禁止提交到 Git 仓库。

## V0.1 主流程

1. 检测 Everything 1.4 / `es.exe` 是否可用。
2. 使用关键词 + 文件类型调用 Everything 获取候选文件列表。
3. 对候选结果进行人工复核。
4. 用户选择单个文件、多个文件或整个目录进行迁移/备份。
5. 迁移前后计算 SHA-256 并校验。
6. 记录原始路径和迁移信息到 manifest。
7. 后续可读取 manifest，将已备份文件恢复到原始位置。

详细设计见：

- `docs/REQUIREMENTS.md`
- `docs/ARCHITECTURE.md`

## 计划技术栈

- Python 3.12+
- Windows 10/11
- Everything 1.4 + ES CLI（优先）
- Python 原生扫描（Everything 不可用时兜底）
- SQLite / JSON manifest
- PySide6（后续 GUI）
- PyInstaller（最终单文件/目录发布）

## 安全边界

FileCheck 是自查和文件迁移工具，不提供“一键清痕”能力。对于命中的候选文件，只提示人工复核，不自动判断其性质。
