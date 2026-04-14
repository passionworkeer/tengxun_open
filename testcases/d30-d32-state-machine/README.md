# D30-D32 状态机与时刻域测试集

7 个端到端 Fail-to-Pass 测试 case，覆盖协议状态机违反、重入锁、信号处理异步安全三个维度。

## 目录结构

```
d30-d32-state-machine/
  D30-01-Python-Txn-State-Machine/   ← 未begin就commit数据库事务
  D30-02-Go-Response-Body-Leak/      ← Response.Body未Close连接泄漏
  D30-03-Java-Connection-Pool-Not-Returned/ ← 连接池未归还
  D31-01-Cpp-Mutex-Callback-Reentry/  ← 持mutex调用用户回调重入
  D31-02-Java-ReentrantLock-Reentry/  ← ReentrantLock重入数据不一致
  D32-01-C-SIGTERM-Malloc-Corruption/ ← SIGTERM handler中malloc
  D32-02-C-SIGUSR1-Fprintf-Corruption/ ← SIGUSR1 handler中fprintf
```

## 每个 Case 的结构

```
<case-dir>/
  buggy_code.<ext>   含缺陷代码（AI Coder 收到这个版本）
  gold_patch.<ext>   正确修复
  test_patch.py      pytest 测试套件
  <case-id>.json     元数据
```

## 运行方式

```bash
# 进入任意 case 目录
cd d30-d32-state-machine/D30-01-Python-Txn-State-Machine
pytest test_patch.py -v --tb=short

# 或运行全部
for dir in d30-d32-state-machine/*/; do
  echo "=== $dir ==="
  pytest "$dir/test_patch.py" -v --tb=short
done
```

## 预期结果

| Case | buggy 版本 | gold_patch 版本 |
|------|-----------|----------------|
| D30-01 Python | FAIL (isolation_level=None) | PASS |
| D30-02 Go | FAIL (Body.Close 缺失) | PASS |
| D30-03 Java | FAIL (连接泄漏) | PASS |
| D31-01 C++ | FAIL (死锁/超时) | PASS |
| D31-02 Java | FAIL (transactionCount 错误) | PASS |
| D32-01 C | FAIL (malloc in handler) | PASS |
| D32-02 C | FAIL (fprintf in handler) | PASS |

## 难度分布 (PDF 维度定义)

- **D30** 协议状态机违反：方法调用顺序违反协议约定
- **D31** 重入与递归锁：持锁时调用再次获取同一把锁
- **D32** 信号处理异步安全：handler 调用非 async-signal-safe 函数

参考论文：SWE-bench (ICLR 2024), DDI 调试衰减模型 (Nature CompSci 2025)
