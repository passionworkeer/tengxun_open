# Eval Round 4 Type A Set 1 - Revision 2

> 本稿仅修订 set1，不改原文件。  
> 已按 `docs/dataset_schema.md` 新 schema 输出；并按 `review_round15_formal_pool_safety.md` / `review_round16_eval_round4_gate.md` 收紧为单问单判与最小闭包。  
> 本批次使用全新 ID（不复用 `celery_hard_021~023`）。

## 总表（R2）

| status | id | difficulty | category | failure_type | implicit_level | source_file | 说明 |
|---|---|---|---|---|---:|---|---|
| park | - | - | worker_acks_late_failure_branch | - | - | celery/worker/request.py | 原 `celery_hard_021` 暂不保留为 round4 Type A/hard |
| revise_keep | celery_hard_121 | hard | autodiscovery_import_error_gate | Type A | 5 | celery/app/base.py | 保留并收紧：修复 ID、补齐 loader 层、收口 indirect |
| rewrite_keep | celery_hard_122 | hard | bootstep_lifecycle_instantiation_gate | Type A | 4 | celery/worker/worker.py | 重写为生命周期断点题（实例化先于 include gate） |

## Drop / Park 决策

### 原 `celery_hard_021`（Candidate 01）: `park`

- 决策：不在本轮 set1 r2 中继续硬保留为 `Type A / hard`。
- 原因：
  - 现有题材核心判断停留在 `Request.on_failure` 单函数分支，按 round4 gate 更像局部分支 tracing，不足以稳定满足 `Type A` 长上下文断点与 `hard` 门槛。
  - 若强行保留，只能通过降级 `difficulty`/`failure_type` 才能口径一致，不符合本轮“高价值 Type A/hard 优先”目标。
- 后续建议：
  - 若未来要复用该素材，建议迁移到非 round4 高价值池，按 medium 或非 Type A 重新评估。

## 逐条 JSON 草案（R2 保留项）

### celery_hard_121

```json
{
  "id": "celery_hard_121",
  "difficulty": "hard",
  "category": "autodiscovery_import_error_gate",
  "failure_type": "Type A",
  "implicit_level": 5,
  "question": "在 `app.autodiscover_tasks(packages, force=False)` 的延迟执行链中，真正负责判定 `ModuleNotFoundError` 是“候选 tasks 模块缺失可忽略”还是“嵌套导入错误需重抛”的函数是哪个？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.loaders.base.find_related_module"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.autodiscover_tasks",
      "celery.app.base.Celery._autodiscover_tasks",
      "celery.loaders.base.BaseLoader.import_default_modules",
      "celery.loaders.base.BaseLoader.autodiscover_tasks",
      "celery.loaders.base.autodiscover_tasks"
    ],
    "implicit_deps": [
      "celery.signals.import_modules",
      "vine.starpromise"
    ]
  },
  "reasoning_hint": "`force=False` 只注册 `signals.import_modules` 回调；触发阶段不写死 worker。只要走到 `import_default_modules -> signals.import_modules.send`，最终扫描链会落到 `find_related_module`，并在该函数内基于 `module_name == e.name` 判定吞/抛。",
  "source_note": "See celery/app/base.py:779-841; celery/loaders/base.py:97-105, 218-221, 239-278; t/unit/app/test_loaders.py:267-305."
}
```

**为何仍是 Type A / hard（自检）**  
该题包含“延迟注册（signal + starpromise）-> 运行时触发（import_default_modules）-> loader 扫描收敛 -> import 错误分类决策点”多阶段链路，任一阶段被截断都容易把触发点误当判定点。

### celery_hard_122

```json
{
  "id": "celery_hard_122",
  "difficulty": "hard",
  "category": "bootstep_lifecycle_instantiation_gate",
  "failure_type": "Type A",
  "implicit_level": 4,
  "question": "在 worker 启动链中，当某个 `StartStopStep.include_if()` 最终为 `False` 时，仍会先执行 step 实例化（触发 `Step.__init__`）的生命周期断点方法是哪个？",
  "source_file": "celery/worker/worker.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.bootsteps.Blueprint.apply"
    ],
    "indirect_deps": [
      "celery.worker.worker.WorkController.__init__",
      "celery.bootsteps.StartStopStep.include",
      "celery.bootsteps.Step._should_include"
    ],
    "implicit_deps": [
      "celery.bootsteps.Step.include_if"
    ]
  },
  "reasoning_hint": "worker 初始化时进入 `blueprint.apply(self, **kwargs)`；`apply` 先在 for-loop 中执行 `step = S(parent, **kwargs)` 完成实例化，随后才调用 `step.include(parent)`。因此 `include_if=False` 只阻断 create/挂载，不阻断更早的实例化。",
  "source_note": "See celery/worker/worker.py:129-140; celery/bootsteps.py:186-205, 322-339, 378-383; t/unit/worker/test_bootsteps.py:93-103, 172-180, 197-201, 328-354."
}
```

**为何仍是 Type A / hard（自检）**  
该题不是同文件 helper tracing，而是“worker 启动阶段 -> blueprint 生命周期 -> include gate”的阶段断点识别题，核心风险是把 include gate 误认为实例化 gate，属于典型生命周期截断误判。
