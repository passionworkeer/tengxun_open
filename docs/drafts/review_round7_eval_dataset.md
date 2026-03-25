# Review Round 7 – eval_cases_migrated_draft.json

## Quick parse check
- `ConvertFrom-Json` fails with “Invalid object … ':' or '}' expected.” on this file. In its current form，工具无法直接解析为 JSON，对自动评测管线是硬阻塞。
- 文件含多处中文 mojibake（例：`easy_007` 问题字段），说明编码/转存有损，同样影响可读性与可信度。

## Schema completeness (spot scan)
- 所有条目包含 `id/difficulty/category/failure_type/implicit_level/question/source_file/source_commit/ground_truth` 字段，但至少 3 点不合规：  
  1. 部分 `ground_truth` 中 `implicit_deps/indirect_deps` 为空但按语义不应为空（如 `easy_002` shared_task Proxy 场景未列 Proxy/回调；`hard_002` 缺 finalize/Proxy 相关隐式）。  
  2. 多条 `source_note` 明示 “failure_type assumed”/“implicit_level approximated”，未经过复核。  
  3. 编码破损导致 `question` 文本不可用于提示词（`easy_007`, `medium_005`, `medium_006` 等中文字段乱码）。

## 分布检查（人工估计，因解析失败无法程序计数）
- 28 条总量：easy 约 7，medium 约 11（含新更名 medium_017/020），hard 约 10，仍远低于目标 50 且 hard<15 目标。
- failure_type：Type A 缺失；Type D 仅 2~3 条；Type B/E 占绝大多数，配比失衡。
- implicit_level：集中在 1–4，未见 5 以上覆盖，且多条为估值。

## 旧 12 条迁移质量
- `failure_type` 大量拍脑袋（标注 “assumed/approximated”），缺少复核证据。  
- 多条 `implicit_deps` 空缺但语义应包含 Proxy/alias/动态解析（`easy_002`、`hard_002` 等）。  
- 迁移文本未修正语言编码，直接降低可读性和提示有效性。

## 是否可替换正式 eval v0.2
- 结论：**do_not_promote_yet**。
- 最小阻塞项：  
  - 文件当前无法被标准 JSON 解析器读取（ConvertFrom-Json 报错），必须先修复合法性。  
  - 编码破损（mojibake）需重写相关字段。  
  - failure_type / implicit_level 存在大面积未复核的占位值；多条 implicit/indirect 为空与任务语义不符。  
  - 配比失衡：Type A 缺席、Type D 稀缺、hard 数量不足，无法代表目标分布。  
  - 总量仅 28 条，距离 50 条目标远，且 hard<15。

## 建议的最小修复路径
- 先修复 JSON 合法性与编码，再用脚本跑分布统计；对迁移的旧 12 条逐条补充 failure_type/implicit/indirect，并去掉 “assumed/approx” 占位。  
- 补齐 Type A/D 及 hard 槽位（至少再添 ≥2 Type D、≥5 hard），同时完成双人复核。  
- 通过一次机器可解析性校验（ConvertFrom-Json 成功）后，再讨论升级为正式 v0.2。
