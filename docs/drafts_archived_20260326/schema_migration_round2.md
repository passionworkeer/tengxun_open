## Scope
- 当前状态：`data/eval_cases.json` 仍是旧 schema（entry_file / entry_symbol / gold_fqns），目标迁移到 `docs/dataset_schema.md` 的新 schema（source_file / source_commit / ground_truth.{direct,indirect,implicit}_deps 等）。
- 约束：不改动正式文件；只在本文件给出可执行方案 + 两条示例转换（草稿）。

## Schema Diff & 字段映射
| 旧字段 | 新字段 | 迁移方式 | 备注 |
| --- | --- | --- | --- |
| `id` | `id` | 机械迁移 | 保持原值；需全局唯一 |
| `difficulty` | `difficulty` | **需复核** | 旧定义较宽松，新定义结合链路深度+implicit_level；建议保留原值但在人工审校阶段复核 |
| `category` | `category` | **需复核** | 旧值如 `re_export` / `alias_resolution` 等需映射到新分类体系（与 failure_type 解耦）；人工判定 |
| *(无)* | `failure_type` | **新增，人工必填** | Type A-E，旧文件无对应字段 |
| *(无)* | `implicit_level` | **新增，人工必填** | 1-5 级，结合隐式依赖深度 |
| `question` | `question` | 机械迁移 | 原文即可 |
| `entry_file` | `source_file` | 机械迁移 | 需补全为相对 `external/celery/` 的路径 |
| *(无)* | `source_commit` | **新增，统一填充** | 使用当前绑定 `b8f85213f45c937670a6a6806ce55326a0eb537f` |
| `gold_fqns` | `ground_truth.direct_deps` | 机械迁移 | 直接依赖列表；保持顺序 |
| *(无)* | `ground_truth.indirect_deps` | **新增，默认为空数组** | 若证据链有中间 hop，可人工补充 |
| *(无)* | `ground_truth.implicit_deps` | **新增，默认为空数组** | 隐式/动态加载依赖需人工识别 |
| `reasoning_hint` | `reasoning_hint` | 机械迁移 | 可在审校时充实 |
| `source_note` | `source_note` | 机械迁移 | 建议补充覆盖到的源文件清单 |
| `entry_symbol` | *(无直接槽位)* | **弃用/折叠** | 可并入 `question` 或 `source_note` 以保留上下文；不再单列 |

## 机械迁移 vs 人工补齐
- 机械可批处理：`id`, `question`, `source_file`(由 entry_file 直接映射), `ground_truth.direct_deps`(由 gold_fqns), `reasoning_hint`, `source_note`, `source_commit`(统一填当前 submodule commit)。
- 必须人工补：`failure_type`, `implicit_level`, `category` 复核、`ground_truth.indirect_deps`, `ground_truth.implicit_deps`。
- 需人工判定的理由：
  - `failure_type` 依赖错误模式（别名/嵌套/__init__/动态加载）；旧数据未标注。
  - `implicit_level` 需看调用/动态分支深度，无法机械推断。
  - `category` 旧标签与新分类口径可能不一致（如 `re_export` vs Type C/D 边界）。
  - `indirect/implicit_deps` 需要阅读 evidence chain。

## 策略选项与风险
1) **直接改写 `data/eval_cases.json`**  
   - 优点：一步到位。  
   - 风险：旧/新混合期间导致评测脚本、下游 few-shot 同步失败；失败类型/隐式等级若随手填错，会污染正式集。
2) **先生成迁移草稿文件，再审校，最后覆盖正式文件（推荐）**  
   - 优点：隔离风险；可用 reviewer 严审；便于对比 diff。  
   - 风险：多一步合并，但可控。

结论：采用方案 2。先生成 `data/eval_cases_migrated_draft.json`（或置于 docs/drafts/），经 reviewer 逐条 pass 后再替换正式文件。

## 推荐执行顺序（可直接照做）
1. 复制旧集：`cp data/eval_cases.json data/eval_cases_migrated_draft.json`。
2. 机械填充脚本（或手动一次性编辑）：
   - 将 `entry_file` 重命名为 `source_file`。
   - 删除 `entry_symbol`（可追加到 `source_note` 尾部 “entry_symbol: xxx”）。
   - 将 `gold_fqns` 写入 `ground_truth.direct_deps`，并新增空数组 `indirect_deps`、`implicit_deps`。
   - 增加 `source_commit: "b8f85213f45c937670a6a6806ce55326a0eb537f"`。
3. 人工字段占位：
   - 为每条增加 `failure_type: "TBD"`，`implicit_level: 0`（或 -1），并在 `source_note` 标注“需要审校”。
4. 审校分批进行（按 easy/medium/hard）：
   - 判定 `failure_type`：  
     - Type B 典型：装饰器/回调 (`@shared_task`, `connect_on_app_finalize`)  
     - Type C 典型：多层 `__init__.py` 重导  
     - Type D 典型：命名空间/注册表别名 (`ALIASES`, `BACKEND_ALIASES`)  
     - Type E 典型：`symbol_by_name` / 动态 import  
     - Type A：上下文缺失/过长链（本批次可能较少）
   - 判定 `implicit_level`：  
     - 1-2：单跳显式 import / re-export  
     - 3：需跨模块再导出或注册表查表  
     - 4-5：动态加载、延迟回调、状态机触发
   - 补 `indirect_deps` / `implicit_deps`：根据 evidence chain 补充中间 hop。
5. reviewer 按 `docs/drafts/review_round1.md` 的 rubric 逐条 pass/hold/reject。
6. 仅将 reviewer “pass” 条目替换回正式 `data/eval_cases.json`；对 hold/reject 回炉。
7. 更新 `docs/remaining_work_checklist.md` / `plan.md` 的迁移进度。

## 旧 -> 新 schema 示例（草稿，不写回正式文件）
以下仅示范结构，供审校时对照。

### 示例 1：`easy_001`（draft）
```json
{
  "id": "easy_001",
  "difficulty": "easy",
  "category": "re_export", // 待复核是否归为 Type C 样式
  "failure_type": "TBD",
  "implicit_level": 1,
  "question": "Which real class does `celery.Celery` resolve to in the top-level lazy API?",
  "source_file": "celery/__init__.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": ["celery.app.base.Celery"],
    "indirect_deps": [],
    "implicit_deps": []
  },
  "reasoning_hint": "`celery.__init__` re-exports `Celery` from `celery.app`, and `celery.app` imports it from `.base`.",
  "source_note": "Bound to external/celery/celery/__init__.py and celery/app/__init__.py; entry_symbol: celery.Celery"
}
```

### 示例 2：`hard_004`（draft）
```json
{
  "id": "hard_004",
  "difficulty": "hard",
  "category": "alias_resolution", // 需审校：可能归为 Type E 动态解析
  "failure_type": "TBD",
  "implicit_level": 4,
  "question": "In `celery.worker.strategy.default`, what real class does `task.Request` resolve to?",
  "source_file": "celery/worker/strategy.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": ["celery.worker.request.Request"],
    "indirect_deps": ["celery.app.task.Task.Request"], // registry indirection
    "implicit_deps": ["celery._state.symbol_by_name"] // 动态加载路径，需审校确认
  },
  "reasoning_hint": "`default` calls `symbol_by_name(task.Request)`, while `Task.Request` stores the string `celery.worker.request:Request`.",
  "source_note": "Bound to worker/strategy.py, app/task.py, worker/request.py; entry_symbol: celery.worker.strategy.default"
}
```

## 立即可落地的动作
- 按推荐步骤先产出 `data/eval_cases_migrated_draft.json`。
- 用 reviewer 严审字段：`failure_type`、`implicit_level`、`indirect/implicit_deps`、`category` 边界。
- 审完的 pass 条目再覆盖正式集；其余回炉补充。

（完）
