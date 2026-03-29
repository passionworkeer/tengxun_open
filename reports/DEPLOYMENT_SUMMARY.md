xia'z# Qwen3.5-9B 部署状态总结

## ✅ 当前状态

### 环境已就绪
- ✓ PyTorch 2.10.0 (CUDA 12.8)
- ✓ Transformers 5.3.0
- ✓ Qwen3.5 架构支持已确认
- ⚠ GPU 不可用（CPU 模式）

### 已创建文件
1. `/workspace/Qwen3.5_DEPLOY_GUIDE.md` - 详细部署指南
2. `/workspace/llamafactory_qwen35_deploy.py` - 环境检测和示例代码
3. `/workspace/LLaMA-Factory/` - LLaMA Factory 框架（包含示例代码）

---

## 📋 部署方案

### 方案 1：Transformers 直接部署（推荐用于快速测试）

```bash
cd /workspace
python << 'EOF'
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

model_name = "Qwen/Qwen3.5-9B"

print("加载 tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(
    model_name,
    trust_remote_code=True
)

print("加载模型 (CPU 模式，可能需要 10-20 分钟)...")
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="cpu",
    trust_remote_code=True
)

print("模型加载完成！")

# 对话测试
messages = [
    {"role": "user", "content": "你好！"}
]

text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
)

model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

print("生成回复...")
with torch.no_grad():
    generated_ids = model.generate(
        model_inputs.input_ids,
        max_new_tokens=512,
        temperature=0.7,
        do_sample=True
    )

generated_ids = [
    output_ids[len(input_ids):]
    for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
]

response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
print(f"回复: {response}")
EOF
```

### 方案 2：LLaMA Factory Web UI（推荐用于可视化操作）

```bash
cd /workspace/LLaMA-Factory
llamafactory-cli webui
```

访问: http://localhost:7860

在 Web UI 中：
1. 选择模型：`Qwen/Qwen3.5-9B`
2. 设置参数：
   - Template: `qwen`
   - Trust remote code: `true`
3. 开始对话

### 方案 3：LLaMA Factory CLI

```bash
cd /workspace/LLaMA-Factory
llamafactory-cli chat examples/inference/qwen35.yaml
```

---

## ⚠️ 重要提示

### 硬件要求
| 配置项 | 最低要求 | 推荐配置 |
|-------|---------|---------|
| **CPU 内存** | 32GB | 64GB+ |
| **GPU 显存** | - | 16GB+ (如 RTX 3090) |
| **磁盘空间** | 40GB | 60GB+ |
| **下载带宽** | - | 100Mbps+ |

### 性能预期
- **CPU 推理**: 每字生成约 1-5 秒（很慢）
- **GPU 推理**: 每秒生成 30-100 字（很快）
- **量化后 GPU**: 显存减少 50-75%，速度略降

### 首次下载时间
- 使用 100Mbps 网络：约 30-60 分钟
- 模型大小：约 18GB（FP16）

---

## 🔧 故障排除

### 问题 1：内存不足
**症状**: `killed` 进程被终止

**解决方案**:
1. 使用更小的模型：`Qwen/Qwen2.5-7B` (~14GB)
2. 使用量化：`load_in_4bit=True` 或 `load_in_8bit=True`
3. 增加系统交换空间

### 问题 2：LLaMA Factory 无法启动
**症状**: 导入错误或依赖冲突

**解决方案**:
1. 重新安装 LLaMA Factory:
   ```bash
   cd /workspace/LLaMA-Factory
   pip install -e .
   ```

2. 或使用方案 1（Transformers 直接部署）

### 问题 3：下载速度慢
**解决方案**:
1. 使用国内镜像:
   ```bash
   export HF_ENDPOINT=https://hf-mirror.com
   ```

2. 使用 ModelScope:
   ```bash
   export USE_MODELSCOPE_HUB=1
   ```

---

## 📚 相关资源

- **LLaMA Factory 文档**: https://llamafactory.readthedocs.io/
- **Qwen 模型页**: https://huggingface.co/Qwen/Qwen3.5-9B
- **详细部署指南**: `/workspace/Qwen3.5_DEPLOY_GUIDE.md`

---

## ✅ 部署检查清单

- [ ] 确认系统内存 ≥ 32GB
- [ ] 确认磁盘空间 ≥ 40GB
- [ ] 确认网络连接稳定
- [ ] 选择部署方案（1/2/3）
- [ ] 运行部署脚本
- [ ] 测试对话功能
- [ ] （可选）配置 GPU 加速
- [ ] （可选）设置 API 服务

---

## 🎯 下一步操作

1. **快速测试**: 运行方案 1 的 Python 脚本
2. **深度使用**: 使用方案 2 的 Web UI
3. **生产部署**: 参考 `Qwen3.5_DEPLOY_GUIDE.md` 的高级方案

---

## 📞 获取帮助

- LLaMA Factory GitHub Issues
- Cloud Studio 用户群（见 README 中的二维码）
- 官方文档链接（见上方相关资源）

---

**部署就绪！现在可以开始使用了。** 🎉
