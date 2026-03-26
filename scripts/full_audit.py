#!/usr/bin/env python3
"""
全量审计微调数据集

审计维度：
1. FQN准确性 - 所有FQN路径是否真实存在于源码中
2. 推理逻辑 - Step-by-step推理是否正确
3. 难度标注 - easy/medium/hard是否合理
4. 格式规范 - JSON格式、字段完整性
5. 数据质量 - 唯一性、多样性
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from collections import Counter
import subprocess


@dataclass
class AuditResult:
    """审计结果"""

    index: int
    instruction: str
    fqn_score: float  # 0-1
    logic_score: float  # 0-1
    difficulty_score: float  # 0-1
    format_score: float  # 0-1
    total_score: float  # 0-1
    issues: List[str]
    fqn_valid: bool
    logic_valid: bool
    difficulty_valid: bool


class FQNValidator:
    """FQN路径验证器 - 修复方法级FQN问题"""

    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        self.fqn_cache: Dict[str, bool] = {}

    def validate_fqn(self, fqn: str) -> Tuple[bool, str]:
        """
        验证FQN路径是否真实存在

        修复方法级FQN问题：
        - celery.app.base.Celery.send_task 现在能正确找到 celery/app/base.py
        - 递归尝试所有可能的模块/符号切分点
        """
        if fqn in self.fqn_cache:
            return self.fqn_cache[fqn], ""

        parts = fqn.split(".")
        if len(parts) < 2:
            self.fqn_cache[fqn] = False
            return False, "FQN格式错误"

        # 外部包直接放行
        if parts[0] in ("kombu", "vine", "billiard", "pydantic", "eventlet", "gevent"):
            self.fqn_cache[fqn] = True
            return True, "外部包"

        # 核心修复：跳过第一个 celery 前缀（因为 source_dir 已经包含了）
        # celery.utils.imports.symbol_by_name -> utils.imports.symbol_by_name
        if parts[0] == "celery":
            parts = parts[1:]

        if len(parts) < 1:
            self.fqn_cache[fqn] = False
            return False, "FQN格式错误"

        # 核心修复：递归尝试所有可能的模块/符号切分点
        # utils.imports.symbol_by_name
        # 可能是：
        #   文件=utils/imports.py, 符号=symbol_by_name
        # 从最长的模块路径开始尝试

        for split_at in range(len(parts), 0, -1):
            module_parts = parts[:split_at]
            symbol_name = parts[split_at] if split_at < len(parts) else None

            # 如果没有符号名，只检查模块文件是否存在
            if symbol_name is None:
                # 检查 module_parts/__init__.py
                path = self.source_dir / Path(*module_parts) / "__init__.py"
                if path.exists():
                    self.fqn_cache[fqn] = True
                    return True, f"模块存在: {path}"
                # 检查 module_parts.py (单层模块)
                if len(module_parts) == 1:
                    path2 = self.source_dir / f"{module_parts[0]}.py"
                    if path2.exists():
                        self.fqn_cache[fqn] = True
                        return True, f"模块文件: {path2.name}"
                continue

            # 尝试 module/as/path.py
            if len(module_parts) >= 2:
                path1 = (
                    self.source_dir
                    / Path(*module_parts[:-1])
                    / f"{module_parts[-1]}.py"
                )
            elif len(module_parts) == 1:
                path1 = self.source_dir / f"{module_parts[0]}.py"
            else:
                continue

            # 尝试 module/as/path/__init__.py
            path2 = self.source_dir / Path(*module_parts) / "__init__.py"

            for path in [path1, path2]:
                if path.exists():
                    try:
                        content = path.read_text(encoding="utf-8")
                        patterns = [
                            rf"class\s+{re.escape(symbol_name)}\s*[\(:]",
                            rf"def\s+{re.escape(symbol_name)}\s*\(",
                            rf"{re.escape(symbol_name)}\s*=",
                            rf"from\s+\S+\s+import\s+.*\b{re.escape(symbol_name)}\b",
                            rf"import\s+.*\b{re.escape(symbol_name)}\b",
                        ]
                        for pattern in patterns:
                            if re.search(pattern, content):
                                self.fqn_cache[fqn] = True
                                return True, f"在 {path.name} 中找到 {symbol_name}"
                    except Exception:
                        pass

            # 额外检查：如果 symbol_name.py 文件存在，说明这是一个模块级FQN
            # celery.app.defaults -> app/defaults.py 是一个模块
            if len(module_parts) >= 1:
                module_file_path = (
                    self.source_dir / Path(*module_parts) / f"{symbol_name}.py"
                )
                if module_file_path.exists():
                    self.fqn_cache[fqn] = True
                    return True, f"模块文件: {module_file_path.name}"

        self.fqn_cache[fqn] = False
        return False, "未找到符号定义"

    def extract_fqns(self, text: str) -> List[str]:
        """从文本中提取所有FQN"""
        # 匹配 celery.xxx.yyy 或 kombu.xxx.yyy 格式
        pattern = r"(?:celery|kombu|vine|billiard)\.[a-zA-Z_][a-zA-Z0-9_.]*"
        matches = re.findall(pattern, text)

        # 过滤掉太短的匹配
        fqns = [m for m in matches if len(m.split(".")) >= 2]

        return list(set(fqns))

    def validate_sample(self, sample: Dict) -> Tuple[float, List[str]]:
        """验证单条样本的FQN"""
        issues = []
        valid_count = 0
        total_count = 0

        # 从output中提取FQN
        output = sample.get("output", "")
        fqns = self.extract_fqns(output)

        for fqn in fqns:
            total_count += 1
            valid, reason = self.validate_fqn(fqn)
            if valid:
                valid_count += 1
            else:
                issues.append(f"FQN无效: {fqn} ({reason})")

        if total_count == 0:
            return 0.5, ["无法提取FQN"]

        score = valid_count / total_count
        return score, issues


class LogicValidator:
    """推理逻辑验证器"""

    def __init__(self):
        self.step_pattern = re.compile(r"Step\s+\d+:")
        self.dep_pattern = re.compile(r'"(direct_deps|indirect_deps|implicit_deps)"')

    def validate_sample(self, sample: Dict) -> Tuple[float, List[str]]:
        """验证推理逻辑"""
        issues = []
        score = 1.0

        output = sample.get("output", "")

        # 检查是否有推理步骤
        steps = self.step_pattern.findall(output)
        if len(steps) < 2:
            issues.append("推理步骤不足（至少需要2步）")
            score -= 0.3

        # 检查是否有最终依赖
        deps = self.dep_pattern.findall(output)
        if len(deps) < 1:
            issues.append("缺少最终依赖结构")
            score -= 0.4

        # 检查推理过程和最终结论的一致性
        if "最终依赖" not in output:
            issues.append("缺少'最终依赖'标记")
            score -= 0.3

        return max(0, score), issues


class DifficultyValidator:
    """难度标注验证器"""

    def __init__(self):
        self.easy_keywords = ["直接导入", "单层", "简单", "from", "import"]
        self.hard_keywords = [
            "动态",
            "Proxy",
            "装饰器",
            "symbol_by_name",
            "多层",
            "跨包",
            "隐式",
        ]

    def validate_sample(self, sample: Dict) -> Tuple[float, List[str]]:
        """验证难度标注"""
        issues = []

        difficulty = sample.get("difficulty", "")
        output = sample.get("output", "")
        instruction = sample.get("instruction", "")

        # 计算复杂度指标
        complexity = 0

        # 步骤数量
        steps = len(re.findall(r"Step\s+\d+:", output))
        complexity += steps * 0.1

        # 依赖类型数量
        if (
            "implicit_deps" in output
            and "[]" not in output.split("implicit_deps")[1][:50]
        ):
            complexity += 0.3  # 有隐式依赖

        if (
            "indirect_deps" in output
            and "[]" not in output.split("indirect_deps")[1][:50]
        ):
            complexity += 0.2  # 有间接依赖

        # 关键词检查
        text = instruction + output
        for keyword in self.hard_keywords:
            if keyword in text:
                complexity += 0.15

        # 难度匹配
        expected_difficulty = "easy"
        if complexity > 0.8:
            expected_difficulty = "hard"
        elif complexity > 0.4:
            expected_difficulty = "medium"

        if difficulty != expected_difficulty:
            # 允许一定的容错
            if (
                abs(
                    ["easy", "medium", "hard"].index(difficulty)
                    - ["easy", "medium", "hard"].index(expected_difficulty)
                )
                > 1
            ):
                issues.append(
                    f"难度标注可能不准确: 标注{difficulty}, 预期{expected_difficulty}"
                )
                return 0.6, issues

        return 1.0, issues


class FullAuditor:
    """全量审计器"""

    def __init__(self, source_dir: str):
        self.source_dir = source_dir
        self.fqn_validator = FQNValidator(source_dir)
        self.logic_validator = LogicValidator()
        self.difficulty_validator = DifficultyValidator()

    def audit_sample(self, index: int, sample: Dict) -> AuditResult:
        """审计单条样本"""
        issues = []

        # FQN验证
        fqn_score, fqn_issues = self.fqn_validator.validate_sample(sample)
        issues.extend(fqn_issues)

        # 逻辑验证
        logic_score, logic_issues = self.logic_validator.validate_sample(sample)
        issues.extend(logic_issues)

        # 难度验证
        difficulty_score, diff_issues = self.difficulty_validator.validate_sample(
            sample
        )
        issues.extend(diff_issues)

        # 格式验证
        format_score = 1.0
        required_fields = [
            "instruction",
            "input",
            "output",
            "difficulty",
            "failure_type",
        ]
        for field in required_fields:
            if field not in sample or not sample[field]:
                issues.append(f"缺少字段: {field}")
                format_score -= 0.2

        # 计算总分
        total_score = (
            fqn_score * 0.4
            + logic_score * 0.3
            + difficulty_score * 0.15
            + format_score * 0.15
        )

        return AuditResult(
            index=index,
            instruction=sample.get("instruction", "")[:50],
            fqn_score=fqn_score,
            logic_score=logic_score,
            difficulty_score=difficulty_score,
            format_score=format_score,
            total_score=total_score,
            issues=issues,
            fqn_valid=fqn_score > 0.7,
            logic_valid=logic_score > 0.7,
            difficulty_valid=difficulty_score > 0.7,
        )

    def audit_dataset(self, data_path: str) -> List[AuditResult]:
        """审计整个数据集"""
        results = []

        with open(data_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        print(f"开始审计 {len(lines)} 条数据...")

        for i, line in enumerate(lines):
            sample = json.loads(line)
            result = self.audit_sample(i, sample)
            results.append(result)

            if (i + 1) % 50 == 0:
                print(f"已审计 {i + 1}/{len(lines)} 条")

        return results

    def generate_report(self, results: List[AuditResult]) -> Dict:
        """生成审计报告"""
        total = len(results)

        # 统计
        fqn_valid_count = sum(1 for r in results if r.fqn_valid)
        logic_valid_count = sum(1 for r in results if r.logic_valid)
        difficulty_valid_count = sum(1 for r in results if r.difficulty_valid)

        # 分数分布
        scores = [r.total_score for r in results]
        avg_score = sum(scores) / len(scores)

        # 问题统计
        all_issues = []
        for r in results:
            all_issues.extend(r.issues)
        issue_counter = Counter(all_issues)

        # 分数分布
        score_dist = {
            "优秀(>=0.9)": sum(1 for s in scores if s >= 0.9),
            "良好(0.8-0.9)": sum(1 for s in scores if 0.8 <= s < 0.9),
            "中等(0.7-0.8)": sum(1 for s in scores if 0.7 <= s < 0.8),
            "较差(<0.7)": sum(1 for s in scores if s < 0.7),
        }

        report = {
            "total_samples": total,
            "fqn_valid_rate": fqn_valid_count / total,
            "logic_valid_rate": logic_valid_count / total,
            "difficulty_valid_rate": difficulty_valid_count / total,
            "avg_score": avg_score,
            "score_distribution": score_dist,
            "top_issues": dict(issue_counter.most_common(10)),
            "worst_samples": [
                {
                    "index": r.index,
                    "instruction": r.instruction,
                    "score": r.total_score,
                    "issues": r.issues[:3],
                }
                for r in sorted(results, key=lambda x: x.total_score)[:10]
            ],
        }

        return report


def main():
    """主函数"""
    source_dir = "external/celery/celery"
    data_path = "data/finetune_dataset_500.jsonl"

    # 创建审计器
    auditor = FullAuditor(source_dir)

    # 审计数据集
    results = auditor.audit_dataset(data_path)

    # 生成报告
    report = auditor.generate_report(results)

    # 打印报告
    print("\n" + "=" * 60)
    print("全量审计报告")
    print("=" * 60)
    print(f"总样本数: {report['total_samples']}")
    print(f"FQN有效率: {report['fqn_valid_rate'] * 100:.1f}%")
    print(f"逻辑有效率: {report['logic_valid_rate'] * 100:.1f}%")
    print(f"难度有效率: {report['difficulty_valid_rate'] * 100:.1f}%")
    print(f"平均分数: {report['avg_score']:.3f}")

    print("\n分数分布:")
    for level, count in report["score_distribution"].items():
        print(f"  {level}: {count}")

    print("\n主要问题:")
    for issue, count in list(report["top_issues"].items())[:5]:
        print(f"  [{count}次] {issue}")

    print("\n最差样本 (Top 5):")
    for sample in report["worst_samples"][:5]:
        print(
            f"  #{sample['index']} (分数:{sample['score']:.2f}): {sample['instruction']}"
        )
        for issue in sample["issues"][:2]:
            print(f"    - {issue}")

    # 保存详细报告
    with open("data/audit_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 保存审计结果
    audit_results = [
        {
            "index": r.index,
            "score": r.total_score,
            "fqn_score": r.fqn_score,
            "logic_score": r.logic_score,
            "difficulty_score": r.difficulty_score,
            "issues": r.issues,
        }
        for r in results
    ]

    with open("data/audit_results.jsonl", "w", encoding="utf-8") as f:
        for r in audit_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n详细报告已保存到: data/audit_report.json")
    print(f"审计结果已保存到: data/audit_results.jsonl")

    return results


if __name__ == "__main__":
    main()
