# MAP/A2L Lookup 0.01

离线命令行工具：以 ASAP2/A2L 对象为查询入口，用链接 MAP 的 VMA/LMA 和符号名做交叉校验。该版本只报告静态定义，不代表 ECU 当前运行固件，也不会将 VMA/LMA 自动转换为运行时地址。

## 环境与运行

需要 Python 3.10+，无第三方运行依赖。开发目录直接运行：

```powershell
python -m map_a2l_tool summary --a2l .\full_CMP_0.0.0_CANApe_0923.a2l --map .\CMP_TZCU_0.0.0_9110100VC20000_A.map
```

在仓库根目录也可设 `PYTHONPATH=src` 后运行 `python -m map_a2l_tool.cli ...`；安装开发入口：

```powershell
python -m pip install -e .
map-a2l summary
```

省略 `--a2l` 时扫描当前目录及子目录，忽略无有效对象的空壳文件，并选择对象数最多的候选；同规模时要求显式指定。省略 `--map` 仅在当前目录恰有一个 `.map` 文件时可用。

## 命令

```text
map-a2l summary
map-a2l query CIL_3rModFlapMotCtr
map-a2l query --fuzzy CIL_3rModFlapMot --limit 20
map-a2l address 0xB0056364
map-a2l batch names.txt -o result.csv
map-a2l report -o report.json
```

所有命令都可通过 `--a2l`、`--map` 覆盖输入。批量清单每行一个变量名，空行和 `#` 注释行忽略；JSON/CSV 导出保留未命中对象。索引旁生成 `.map_a2l_cache.json`，仅在输入文件路径、大小、修改时间和 SHA-256 均一致时复用。

`query --fuzzy` 支持变量名包含匹配和相似度匹配，结果按相似度降序返回；`--limit` 控制最大结果数。`address` 支持 `0x` 十六进制地址，返回 A2L 精确地址、MAP VMA/LMA 精确地址及符号范围命中。

Tkinter 界面提供三种查询模式：变量模糊匹配、严格匹配和地址匹配。严格匹配要求输入内容与 A2L 变量名完整相等但不区分大小写，不会返回前缀、包含或相似名称；严格匹配结果仍会继续应用对象类型、等级、匹配状态和地址范围筛选。

## 匹配级别

- A（完全一致）：A2L 名称和地址均与 MAP 符号及 VMA/LMA 一致。
- B（地址匹配）：A2L 地址命中 MAP，但符号名称未精确匹配。
- C（名称匹配）：MAP 符号名称命中，但 A2L 地址缺失或不一致。
- D（未匹配）：A2L 对象未按名称或地址命中 MAP。
- E（存在歧义）：同名或同地址存在多个候选，禁止静默选择。

Tkinter 界面会同时显示等级、等级说明和诊断信息。筛选条件之间按 AND 逻辑生效，支持对象类型、等级、匹配状态和 A2L/MAP 地址范围组合筛选。

当前版本直接解析 MEASUREMENT、CHARACTERISTIC、AXIS_PTS、INSTANCE、BLOB 的顶层对象和基础字段，并解析 MAP 常见表格行。复杂记录布局、复合数据的完整物理解释、候选目录交互选择和构建 ID 验证尚未实现；版本状态会明确标为“未验证”。

## 开发测试

```powershell
python -m unittest discover -s tests -v
```
