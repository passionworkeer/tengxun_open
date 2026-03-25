# Review Round 9 — Type A / D Few-shot (Strict)

只审 A01/A02/D-01/D-02/D-03/D-04，结论仅用于 few-shot 取舍。判定：accept / needs_more_fix / reject。

---

## A01  (CLI worker 启动长链)
- verdict: **accept**  
- objections checked:  
  - 目标落在 `celery.apps.worker.Worker`，入口与动态 subclass 路径区分明确；不与 eval 主链重复。  
  - direct/indirect/implicit 划分自洽，未将命令入口与最终类混写。  
  - 前置条件写清（默认 loader/argv），可复核。  

## A02  (current_app 首次访问 auto-finalize 链)
- verdict: **needs_more_fix**  
- objections:  
  - 题干宣称 “回填并触发 auto-finalize”，但链路中未出现实际触发 finalize 的节点（`Celery.finalize` 只在 tasks 属性或显式调用时触发，`_get_current_app` 本身不会 auto-finalize）。  
  - ground_truth 把 `_get_current_app` 与 `PromiseProxy` / pending drain混写进 indirect/implicit，仍缺 `_announce_app_finalized` / `connect_on_app_finalize` 等真实触发 finalize 的路径，口径漂移。  
  - 作为 few-shot 容易教出错误心智（“访问 current_app 就会 finalize”），需补充触发条件或改题。  

## D-01  (TaskRegistry 同名覆盖)
- verdict: **accept**  
- objections checked:  
  - “last write wins” 与源码 `TaskRegistry.register -> self[name]=task` 一致；前置条件列出，未与 eval 泄漏。  
  - direct/indirect/implicit 分层合理（注册函数/副作用/容器）。  

## D-02  (@app.task 同名复用)
- verdict: **accept**  
- objections checked:  
  - 明确 lazy=False 分支，`_task_from_fun` 的同名短路确实返回已有任务（first wins）；与 D-01 形成对照，具备 few-shot 价值。  
  - 未将 `_task_from_fun` 终点混入多重目标，字段口径稳。  

## D-03  (control_command 同名覆盖)
- verdict: **accept**  
- objections checked:  
  - 直接命中 `Panel._register` 的 dict 赋值语义，结论“后注册覆盖先注册”符合源码；前置条件写明同 Panel。  
  - 不与现有 eval/few-shot 重复主题。  

## D-04  (Signal dispatch_uid 冲突)
- verdict: **accept**  
- objections checked:  
  - `dispatch_uid` 相同 key 直接被 `_connect_signal` 去重，结论“一次 connect 生效”符合源码；依赖顺序和容器都在 ground_truth 中体现。  
  - 适合作 few-shot 讲解冲突决议，不与 eval 重复。  

---

## Integration Guidance
- **integrate_now**: A01, D-01, D-02, D-03, D-04  
- **hold_back**: A02（需补充/修正 auto-finalize 触发路径，避免误导 “current_app 即自动 finalize”）
