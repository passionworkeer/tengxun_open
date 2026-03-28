from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Sequence


_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")
_PHRASE_FEATURES = (
    "symbol_by_name",
    "by_name",
    "loader",
    "backend",
    "task_cls",
    "strategy",
    "request",
    "fixup",
    "django",
    "autodiscover",
    "finalize",
    "decorator",
    "proxy",
    "re export",
    "re_export",
    "top level",
    "top-level",
    "helper function",
    "lazy api",
)
_HIGH_SIGNAL_TOKENS = {
    "alias",
    "backend",
    "default",
    "django",
    "finalize",
    "fixup",
    "loader",
    "proxy",
    "request",
    "resolve",
    "strategy",
    "symbol",
    "task",
    "task_cls",
}
_ORDINAL_THRESHOLDS = (2, 3, 4, 5)


@dataclass(frozen=True)
class OrdinalThresholdPrediction:
    predicted_level: int
    should_use_rag: bool
    threshold_probabilities: dict[int, float]
    active_features: tuple[str, ...]


class FeatureVectorizer:
    def __init__(self) -> None:
        self.vocabulary_: dict[str, int] = {}

    def fit(self, feature_rows: Sequence[Counter[str]]) -> None:
        doc_freq: Counter[str] = Counter()
        for row in feature_rows:
            doc_freq.update(row.keys())
        features = [
            feature
            for feature, count in doc_freq.items()
            if count >= 2 or feature.startswith(("flag=", "kw=", "path=", "meta="))
        ]
        self.vocabulary_ = {
            feature: index
            for index, feature in enumerate(sorted(features))
        }

    def transform(self, features: Counter[str]) -> dict[int, float]:
        vector: dict[int, float] = {}
        for feature, value in features.items():
            index = self.vocabulary_.get(feature)
            if index is None:
                continue
            vector[index] = float(value)
        return vector


class LogisticBinaryClassifier:
    def __init__(self, num_features: int) -> None:
        self.num_features = num_features
        self.weights = [0.0] * num_features
        self.bias = 0.0

    def fit(
        self,
        rows: Sequence[dict[int, float]],
        labels: Sequence[int],
        *,
        epochs: int = 220,
        learning_rate: float = 0.16,
        l2: float = 1e-4,
    ) -> None:
        for _ in range(epochs):
            for row, label in zip(rows, labels):
                prediction = self.predict_proba(row)
                error = prediction - float(label)
                for index, value in row.items():
                    self.weights[index] -= learning_rate * (error * value + l2 * self.weights[index])
                self.bias -= learning_rate * error

    def predict_proba(self, row: dict[int, float]) -> float:
        score = self.bias
        for index, value in row.items():
            score += self.weights[index] * value
        if score >= 0:
            exp_term = math.exp(-score)
            return 1.0 / (1.0 + exp_term)
        exp_term = math.exp(score)
        return exp_term / (1.0 + exp_term)


class OrdinalImplicitLevelModel:
    def __init__(self, vectorizer: FeatureVectorizer) -> None:
        self.vectorizer = vectorizer
        self.models: dict[int, LogisticBinaryClassifier] = {}

    def fit(
        self,
        *,
        feature_rows: Sequence[Counter[str]],
        levels: Sequence[int],
    ) -> None:
        self.vectorizer.fit(feature_rows)
        encoded_rows = [self.vectorizer.transform(row) for row in feature_rows]
        num_features = len(self.vectorizer.vocabulary_)
        for threshold in _ORDINAL_THRESHOLDS:
            classifier = LogisticBinaryClassifier(num_features)
            labels = [int(level >= threshold) for level in levels]
            classifier.fit(encoded_rows, labels)
            self.models[threshold] = classifier

    def predict(
        self,
        *,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        rag_threshold: int = 3,
    ) -> OrdinalThresholdPrediction:
        feature_row = extract_feature_row(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
        )
        encoded = self.vectorizer.transform(feature_row)
        probabilities = {
            threshold: self.models[threshold].predict_proba(encoded)
            for threshold in _ORDINAL_THRESHOLDS
        }
        monotonic = _monotonic_threshold_probabilities(probabilities)
        predicted_level = 1
        for threshold in _ORDINAL_THRESHOLDS:
            if monotonic[threshold] >= 0.5:
                predicted_level = threshold
        active_features = tuple(
            feature
            for feature in sorted(feature_row)
            if feature.startswith(("flag=", "kw=", "path=", "meta="))
        )
        return OrdinalThresholdPrediction(
            predicted_level=predicted_level,
            should_use_rag=predicted_level >= rag_threshold,
            threshold_probabilities={
                threshold: round(monotonic[threshold], 4)
                for threshold in _ORDINAL_THRESHOLDS
            },
            active_features=active_features,
        )


def extract_feature_row(
    *,
    question: str,
    entry_symbol: str = "",
    entry_file: str = "",
) -> Counter[str]:
    text = " ".join(part for part in (question, entry_symbol, entry_file) if part)
    lowered = text.lower()
    question_tokens = [token.lower() for token in _TOKEN_PATTERN.findall(question)]
    all_tokens = [token.lower() for token in _TOKEN_PATTERN.findall(text)]
    features: Counter[str] = Counter()

    for token in all_tokens:
        if len(token) >= 4 or token in _HIGH_SIGNAL_TOKENS:
            features[f"tok={token}"] += 1

    for left, right in zip(question_tokens, question_tokens[1:]):
        if left in _HIGH_SIGNAL_TOKENS or right in _HIGH_SIGNAL_TOKENS:
            features[f"bigram={left}_{right}"] += 1

    if any(quote in question for quote in ("`", "'", '"')):
        features["flag=has_literal_marker"] = 1
    if "." in question or "." in entry_symbol:
        features["flag=has_dotted_reference"] = 1
    if entry_symbol:
        features["flag=has_entry_symbol"] = 1
    if any(ord(char) > 127 for char in question):
        features["flag=has_non_ascii_question"] = 1

    entry_depth = entry_symbol.count(".")
    if entry_depth >= 3:
        features["meta=deep_entry_symbol"] = 1
    if len(question_tokens) >= 18:
        features["meta=long_question"] = 1

    for phrase in _PHRASE_FEATURES:
        if phrase in lowered:
            features[f"kw={phrase.replace(' ', '_')}"] = 1

    for part in entry_file.replace("\\", "/").split("/"):
        stem = part.split(".", 1)[0].lower()
        if len(stem) >= 4:
            features[f"path={stem}"] = 1

    return features


def cross_validated_predictions(
    *,
    cases: Sequence[object],
    threshold: int = 3,
    num_folds: int = 6,
) -> dict[str, OrdinalThresholdPrediction]:
    folds = _build_stratified_folds(cases, num_folds=num_folds)
    predictions: dict[str, OrdinalThresholdPrediction] = {}

    for fold in folds:
        test_ids = set(fold)
        train_cases = [case for case in cases if getattr(case, "case_id") not in test_ids]
        test_cases = [case for case in cases if getattr(case, "case_id") in test_ids]
        train_rows = [
            extract_feature_row(
                question=case.question,
                entry_symbol=case.entry_symbol,
                entry_file=case.entry_file,
            )
            for case in train_cases
        ]
        train_levels = [max(1, int(case.implicit_level or 1)) for case in train_cases]
        vectorizer = FeatureVectorizer()
        model = OrdinalImplicitLevelModel(vectorizer)
        model.fit(feature_rows=train_rows, levels=train_levels)
        for case in test_cases:
            predictions[case.case_id] = model.predict(
                question=case.question,
                entry_symbol=case.entry_symbol,
                entry_file=case.entry_file,
                rag_threshold=threshold,
            )
    return predictions


def _build_stratified_folds(
    cases: Sequence[object],
    *,
    num_folds: int,
) -> list[list[str]]:
    buckets: dict[int, list[str]] = defaultdict(list)
    for case in sorted(cases, key=lambda item: getattr(item, "case_id")):
        level = max(1, int(getattr(case, "implicit_level", 1) or 1))
        buckets[level].append(getattr(case, "case_id"))

    folds: list[list[str]] = [[] for _ in range(max(2, num_folds))]
    for case_ids in buckets.values():
        for index, case_id in enumerate(case_ids):
            folds[index % len(folds)].append(case_id)
    return [fold for fold in folds if fold]


def _monotonic_threshold_probabilities(
    probabilities: dict[int, float]
) -> dict[int, float]:
    monotonic = dict(probabilities)
    previous = 1.0
    for threshold in _ORDINAL_THRESHOLDS:
        previous = min(previous, monotonic[threshold])
        monotonic[threshold] = previous
    return monotonic
