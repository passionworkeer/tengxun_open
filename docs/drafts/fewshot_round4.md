# Few-shot Round 4 Draft (E03 Only)

范围说明：本文件只处理最后一个未收口的 few-shot `E03`。  
目标：消除 `direct` 口径摇摆，同时保留 `by_url + override_backends + tuple 返回` 这个 Type E 价值点。  
答案结构继续使用与正式 schema 兼容的形式：

```json
{
  "ground_truth": {
    "direct_deps": [],
    "indirect_deps": [],
    "implicit_deps": []
  }
}
```

---

## E03（round4 修订）

**回填空位**：`docs/fewshot_examples.md` -> `Type E` -> `Few-shot E03`  
**针对 objection 的修订点**：
- `direct_deps` 只保留最终解析得到的 backend 类，不再把入口函数和最终目标混写。
- `by_url` 返回 `(cls, url)` 的二元语义只写在推理与说明中，不扩 schema。

**环境前置条件**：
1. `loader.override_backends = {'kv': 'celery.backends.redis:RedisBackend'}`。  
2. 调用入口为：`celery.app.backends.by_url('kv+redis://localhost/0', loader=loader)`。  

**修订版问题**：在上述前置下，`by_url('kv+redis://localhost/0', loader=loader)` 会把 backend 部分最终解析成哪个类，以及这个过程中 URL payload 如何被保留下来？

**推理过程（>=4步）**：
1. `by_url` 先检测输入含 `://`，取出 scheme `kv+redis`。  
2. `by_url` 再按 `+` 拆分 scheme，得到 `backend='kv'` 与 `url='redis://localhost/0'`。  
3. 随后 `by_url` 调用 `by_name('kv', loader)` 去解析 backend 类，而不是自己直接做类加载。  
4. `by_name` 会合并 `dict(BACKEND_ALIASES, **loader.override_backends)`，因此 `kv` 命中运行时覆盖映射。  
5. `symbol_by_name` 最终把该字符串解析为 `celery.backends.redis.RedisBackend`。  
6. `by_url` 的返回不是实例化对象，而是二元组 `(resolved_backend_cls, rewritten_url)`，也就是 `(celery.backends.redis.RedisBackend, 'redis://localhost/0')`。  

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.backends.redis.RedisBackend"
    ],
    "indirect_deps": [
      "celery.app.backends.by_url",
      "celery.app.backends.by_name",
      "celery.utils.imports.symbol_by_name"
    ],
    "implicit_deps": [
      "celery.app.backends.BACKEND_ALIASES"
    ]
  }
}
```

**返回语义说明（非 schema 字段）**：  
该链路的完整运行时返回值是 `(resolved_backend_cls, rewritten_url)`，即 `(celery.backends.redis.RedisBackend, 'redis://localhost/0')`。schema 中只记录 FQN，不把 tuple 结构塞进 `ground_truth`。  

**对抗的失效类型**：Type E（动态 scheme 拆分、运行时 alias 覆盖、字符串到类解析的组合路径）。  

**为什么和现有 eval / 已通过 few-shot 不重复**：
1. `medium_001` 只覆盖 `by_name('redis')` 的静态 alias 命中，不涉及 `by_url` 的 scheme 拆分。  
2. `medium_006` 虽然覆盖 `by_url('rpc://...')`，但它走的是内置 alias，不依赖 `override_backends` 的运行时覆盖。  
3. 这条 few-shot 的关键教学点是“类解析结果”和“URL payload 保留语义”同时存在，但 schema 只记录类 FQN，适合做 few-shot 纠偏，不适合直接当 eval 打分项。  
