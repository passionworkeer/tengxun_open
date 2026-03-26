# BC Tail Few-shot Review Notes

复核对象：`docs/drafts/fewshot_bc_tail_round1.md`（B05 / C04 / C05）  
对照源码：`external/celery` 当前快照（`b8f85213f45c937670a6a6806ce55326a0eb537f`）

---

## B05（`@app.task` execv 分支转发）

**verdict=needs_fix**

1. 主链判断正确：`Celery.task` 在 `USING_EXECV and opts.get('lazy', True)` 下确实先 `return shared_task(...)`（`celery/app/base.py`）。  
2. direct 命中 `celery.app.shared_task` 与题干“先转发到哪个入口”一致，未停在别名层。  
3. 但前置条件不够稳定：`USING_EXECV` 是模块导入时读取环境变量得到的常量，环境变量应在导入 `celery.app.base` 之前设置，否则题设不成立。  
4. 分类存在摇摆：题目只问“首跳入口”，当前 `implicit_deps` 放入 `_task_from_fun` 会把答案重心拉回下游终点，易与 B01/B02 的终点题混淆。  
5. few-shot 价值是有的（分支改道是高频误判点），但需收紧题面与依赖边界后再用。  

最小修复建议：
- 在“环境前置条件”补一句：`FORKED_BY_MULTIPROCESSING` 必须在导入 `celery.app.base` 前设置。  
- 保留 `direct_deps=["celery.app.shared_task"]`，将 `_task_from_fun` 从 `implicit_deps` 移除（或改为解释文本，不进答案字段）。  

---

## C04（`celery.chord` 再导出 + 兼容别名链）

**verdict=accept**

1. 追链正确：顶层 `celery.chord` 由 `recreate_module` 映射到 `celery.canvas.chord`。  
2. 在 `celery.canvas` 中，`chord = _chord`，真实类定义是 `class _chord(Signature)`，因此 direct 指向 `_chord` 合理。  
3. `indirect_deps` 中保留 `celery.canvas.chord`（公开别名）和 `celery.local.recreate_module`（顶层懒导出机制）分层清晰。  
4. 无明显 direct/indirect/implicit 摇摆；问题、推理、答案三者一致。  
5. 适合作 few-shot（教“公开名不等于真实定义”），且与 C01/C03 主题区分度足够。  

最小修复建议：
- 可选优化：在题干补“以类定义落点为准”，进一步避免与“可调用公开名”口径混淆。  

---

## C05（`celery.uuid` 跨模块再导出链）

**verdict=accept**

1. 追链到真实提供者是正确的：`celery.__init__` 映射到 `celery.utils.uuid`，而 `celery.utils.__init__` 明确 `from kombu.utils.uuid import uuid`。  
2. direct 选 `kombu.utils.uuid.uuid` 符合“不要停在 alias/公开名”的审稿重点。  
3. `indirect_deps` 放 `celery.utils.uuid` 与 `celery.local.recreate_module` 合理，能解释两段再导出。  
4. 无明显字段分层摇摆；答案结构与正式 few-shot 模板一致。  
5. 作为 few-shot 可接受：虽然链路不长，但“跨包再导出终点追踪”是常见误判点，且不与现有 C01/C03 直接重复。  

最小修复建议：
- 在 source/说明中补一行“最终提供者位于依赖包 kombu”，提醒复核时需接受跨包终点。  

