# FileCheck V0.1 深度测试计划

## 1. 目标

V0.1 的首要目标不是“自动搬走文件”，而是证明以下链路可靠：

1. Everything 1.4 能稳定找到目标候选文件；
2. FileCheck 能完整复制候选文件；
3. 备份能够独立验证；
4. 备份损坏时恢复必须拒绝开始；
5. 正常备份能够恢复到原始绝对路径；
6. 恢复发生冲突时不会误覆盖；
7. `overwrite` 仅在恢复临时副本通过 SHA-256 后才原子替换已有文件。

只有完成本计划中的 Windows 实机验收后，才考虑增加“自动移出原文件”功能。

## 2. 自动化测试门禁

GitHub Actions 测试矩阵：

- Windows latest + Python 3.10
- Windows latest + Python 3.12
- Ubuntu latest + Python 3.10
- Ubuntu latest + Python 3.12

每个平台执行：

```text
python -m pytest -q
filecheck selftest
```

核心覆盖：

- 目录备份/恢复回环；
- ZIP 备份/恢复回环；
- 中文路径；
- 空格路径；
- 空文件；
- 二进制文件；
- 多级目录；
- SHA-256 校验；
- ZIP CRC 正常但内容 SHA-256 不一致；
- manifest 路径篡改；
- 源文件在复制过程中变化；
- `skip`、`overwrite`、`rename` 三种冲突策略；
- 重叠选择去重；
- 批次 ID 冲突；
- Everything 查询构造、目录范围过滤、严重级别去重。

## 3. Windows + Everything 1.4 实机验收

### 3.1 环境记录

记录：

- Windows 版本；
- 文件系统：NTFS/exFAT/FAT32；
- Everything 版本；
- ES CLI 版本；
- Everything 是否以服务方式运行；
- 被测试盘符及磁盘类型。

先执行：

```powershell
filecheck doctor
```

预期：准确显示 ES CLI 和 Everything 1.4.x 版本。

### 3.2 Everything 索引联调

在专用测试目录创建：

```text
D:\FileCheck-Test\
  普通文件.txt
  机密_测试.docx
  子目录\密码 方案.pdf
  子目录\普通名字.txt
```

执行：

```powershell
filecheck scan --path D:\FileCheck-Test --output scan-results.json
```

验证：

- 关键词命中文件均出现；
- 非命中文件不误报；
- 中文文件名不乱码；
- 原始绝对路径准确；
- 指定 `--path` 后不混入其他盘符同名文件；
- 新建、重命名、移动测试文件后 Everything 索引能及时更新。

### 3.3 目录备份回环

准备至少包含：

- 0 字节文件；
- 1 KB 文本；
- 2 MB 二进制；
- 100 MB 以上随机文件；
- 中文文件名；
- 带空格文件名；
- 多层目录；
- 常用 Office/PDF/ZIP 文件。

执行：

```powershell
filecheck backup D:\FileCheck-Test --dest X:\FileCheckBackup
filecheck verify X:\FileCheckBackup\FC-xxxx
```

人工将测试源目录改名为 `FileCheck-Test.before-restore`，再执行恢复。

逐文件对比：

- 文件数量；
- 文件大小；
- SHA-256；
- 相对目录结构；
- 原始绝对路径。

至少连续执行 10 轮。

### 3.4 ZIP 备份回环

执行同样测试：

```powershell
filecheck backup D:\FileCheck-Test --dest X:\FileCheckBackup --zip
filecheck verify X:\FileCheckBackup\FC-xxxx.zip
filecheck restore X:\FileCheckBackup\FC-xxxx.zip
```

至少连续执行 10 轮。

### 3.5 故障注入

必须主动验证失败场景。

#### A. 目录备份内容损坏

修改备份目录中的一个测试文件，再执行：

```powershell
filecheck verify <backup>
filecheck restore <backup>
```

预期：

- `verify` 失败；
- `restore` 在写入任何原路径前失败。

#### B. ZIP 损坏

复制 ZIP 后人为截断或重建其中一个成员，使其内容改变。

预期：CRC 或 SHA-256 检查失败，不开始恢复。

#### C. 原路径已有文件

分别测试：

```text
--conflict skip
--conflict rename
--conflict overwrite
```

预期：

- skip：已有文件字节完全不变；
- rename：原文件保留，恢复文件使用 `.restored-N` 名称；
- overwrite：只有临时恢复文件通过 SHA-256 后才替换已有目标。

#### D. 原始盘符不可用

如果 manifest 指向可移动盘符，卸载该盘后执行恢复。

预期：Windows 预检阶段直接失败，不开始恢复其它文件。

#### E. 备份介质中途不可写/空间不足

使用测试介质模拟空间不足或写失败。

预期：

- 不生成“验证通过”的完成批次；
- 原始源文件不受影响。

#### F. 源文件在备份过程中改变

对大测试文件持续写入，同时启动备份。

预期：FileCheck 检测到大小/mtime/SHA-256 变化并中止该批次。

## 4. 长路径与 Windows 特性

必须单独测试：

- 260 字符附近路径；
- Windows 已启用 LongPathsEnabled 时 >260 字符路径；
- 只读普通文件；
- 被其它程序独占锁定的文件；
- 外接 USB NTFS/exFAT 盘。

对于失败项，要求明确报错，不能静默跳过。

## 5. 当前不承诺的内容

V0.1 的恢复承诺范围是普通文件的内容、原始绝对路径和基本修改时间。

当前不承诺完整保留：

- NTFS ACL；
- EFS；
- Alternate Data Streams (ADS)；
- 硬链接关系；
- 稀疏文件特性；
- Reparse Point / Junction / Symbolic Link；
- 文件所有者和完整审计元数据。

这些内容如后续确有业务需要，应先增加专门检测和恢复测试，再扩大承诺范围。

## 6. V0.1 通过标准

在允许 V0.1 进入真实数据使用前，应同时满足：

1. GitHub CI 全绿；
2. `filecheck selftest` 在目标 Windows 机器通过；
3. Everything 1.4 实机索引测试通过；
4. 目录回环 10/10 通过；
5. ZIP 回环 10/10 通过；
6. 故障注入全部按预期安全失败；
7. 至少抽取一个真实但非敏感的典型工程目录进行演练；
8. 在以上验证完成前，不启用自动移除源文件功能。
