"""模型准确率统计服务。

以「复核标签 vs 模型预测」为依据，按 model_type 分桶输出：
  - 样本数
  - 精确率（precision）
  - 召回率（recall）
  - F1 分数

数据流：
  ModelResult.label/score  ←  模型预测（事件解释或时序分类输出）
  TrainingSample.label      ←  人工复核标签（groundtruth）
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import ModelResult, TrainingSample


# 业务约定：
#   模型预测 "abnormal_stay" / 时序 label "abnormal_stay"   ↔  复核 label "abnormal"
#   其他 label                                                ↔  复核 label "normal"
def _is_positive(label: str | None) -> bool:
    return label == "abnormal_stay"


@dataclass
class AccuracyReport:
    model_type: str
    sample_count: int
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        if denominator == 0:
            return 0.0
        return self.true_positive / denominator

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        if denominator == 0:
            return 0.0
        return self.true_positive / denominator

    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)


def compute_accuracy(db: Session) -> list[AccuracyReport]:
    """根据已复核事件计算每种模型类型的准确率。"""
    rows: list[AccuracyReport] = []
    grouped: dict[str, list[tuple[bool, bool]]] = defaultdict(list)

    samples: Iterable[tuple[str, str]] = (
        (sample.event_id, sample.label)
        for sample in db.query(TrainingSample).all()
    )
    for event_id, gt_label in samples:
        if not event_id:
            continue
        groundtruth_positive = gt_label == "abnormal"
        results = db.query(ModelResult).filter(ModelResult.event_id == event_id).all()
        for result in results:
            predicted_positive = _is_positive(result.label)
            grouped[result.model_type].append((predicted_positive, groundtruth_positive))

    for model_type, pairs in grouped.items():
        tp = sum(1 for pred, gt in pairs if pred and gt)
        fp = sum(1 for pred, gt in pairs if pred and not gt)
        fn = sum(1 for pred, gt in pairs if not pred and gt)
        tn = sum(1 for pred, gt in pairs if not pred and not gt)
        rows.append(
            AccuracyReport(
                model_type=model_type,
                sample_count=len(pairs),
                true_positive=tp,
                false_positive=fp,
                false_negative=fn,
                true_negative=tn,
            )
        )
    rows.sort(key=lambda report: report.model_type)
    return rows