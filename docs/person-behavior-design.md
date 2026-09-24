# 人体姿态与时序行为识别落地设计

> **当前状态：设计文档。** 本文描述的是业务落地路径和阶段 A 的开发范围；截至当前，人员姿态、人员跟踪和行为规则尚未实现。

## 1. 目标

在现有“车辆检测 + ByteTrack + 区域停留 + 关键帧上传 + 人工复核”的业务闭环上，增加人体姿态、人员跟踪和行为时序能力，使系统能够回答三个更具体的问题：

1. 车辆旁是否有人活动？
2. 人在车辆旁做什么？
3. 该行为是否需要提高或降低风险等级？

本方案遵循“先落业务、后训模型”的原则：

1. 第一阶段先用姿态模型和规则引擎产生可解释业务结果，不依赖大量标注数据。
2. 第二阶段缓存关键点序列，为 GRU/LSTM 时序模型积累样本。
3. 第三阶段在数据充足后再升级为 ST-GCN 或更复杂时序模型。

## 2. 当前基础

| 能力 | 当前状态 | 本次是否重复建设 |
| --- | --- | --- |
| 车辆检测 | 已使用 YOLOv8n | 否 |
| 车辆跟踪 | 已使用 supervision.ByteTrack | 否 |
| 区域停留判断 | 已有区域交叠和静止计时 | 否 |
| 关键帧上传 | 已有 MinIO / 本地存储 | 否 |
| 人员姿态 | 无 | 新增 |
| 人员跨帧 ID | 无 | 新增，复用 ByteTrack 实例 |
| 行为时序识别 | 无 | 新增 |

不引入 OC-SORT，除非现网 ByteTrack 出现大量人员 ID 切换。

## 3. 业务场景

### 3.1 需要识别

| 场景 | 业务含义 |
| --- | --- |
| 车辆旁有人长时间停留 | 需要确认是否滞留、闲逛或异常接触 |
| 多人聚集 | 关注是否存在异常交接、争执或围堵 |
| 人员上下车 | 判断是否为正常作业或疑似异常进入 |
| 弯腰、蹲下、搬运 | 判断是否为装卸作业 |
| 人员跌倒 | 需要立即提醒现场人员 |
| 长时间徘徊 | 关注异常踩点、反复接触车辆或滞留 |

### 3.2 MVP 明确不做

| 场景 | 原因 |
| --- | --- |
| 人脸识别 | 隐私风险高，业务价值不是第一优先级 |
| 身份识别 | 不在库门口异常停留主流程内 |
| 精确判断车门开关 | 仅靠人体姿态不可靠，后续需要车辆门区标定或额外检测模型 |
| 复杂斗殴、偷盗细粒度识别 | 样本不足，先靠人工复核兜底 |

## 4. 推荐技术组合

第一阶段采用最容易与现有栈融合的组合：

```text
YOLOv8n 车辆检测
+ ByteTrack 车辆跟踪
+ YOLOv8n-pose 人体姿态
+ ByteTrack 人员跟踪
+ 规则引擎 + 行为序列缓存
+ 后续 GRU/LSTM 时序分类
```

选择理由：

1. YOLOv8n-pose 与当前 YOLOv8n 同属 Ultralytics 生态，接入成本低。
2. ByteTrack 已经在边缘管线中使用，人员跟踪可复用同一实现。
3. GRU/LSTM 训练和部署成本低于 ST-GCN/TSM，适合第一阶段验证。
4. 行为序列缓存可以先积累数据，不阻塞业务上线。

## 5. 边缘处理流程

### 5.1 主流程

```text
视频帧
  -> YOLOv8n 车辆检测
  -> ByteTrack 车辆跟踪
  -> 判断车辆中心点是否在区域
  -> 判断车辆是否静止
  -> 仅对静止车辆附近区域触发人体姿态
  -> YOLOv8n-pose 人体关键点
  -> ByteTrack 人员跟踪
  -> 人员与车辆关联
  -> 关键点序列缓存
  -> 规则引擎 / 时序模型
  -> 关键帧 + 结构化行为结果上报
```

### 5.2 触发策略

为避免边缘算力被打满：

1. 车辆未进入区域：只做车辆检测，不做人体姿态。
2. 车辆进入但持续移动：只记录轨迹，不做行为识别。
3. 车辆静止后：按 2 到 5 FPS 低频触发人体姿态。
4. 单个车辆旁最多跟踪 5 个 person track。
5. 行为模型按滑动窗口触发，例如每 12 帧推理一次。

### 5.3 人员与车辆关联

人员 track 不直接独立生成事件，而是优先关联到车辆 track。

关联依据按优先级排序：

1. 人员包围框与车辆包围框的 IoU。
2. 人员中心点与车辆包围框的距离。
3. 人员进入车辆附近的时间先后关系。
4. 同一摄像头内的空间一致性。

每个 `person_track_id` 应保留关联的 `vehicle_track_id`，后续行为结果必须带上这两个 ID。

## 6. 行为标签体系

第一阶段先使用粗粒度标签，避免样本不足时过度细分。

| 标签 | 中文含义 | 判定来源 |
| --- | --- | --- |
| `no_person` | 无人活动 | 附近区域未检出人员 |
| `person_present` | 有人存在 | 人员持续出现在车辆附近 |
| `person_moving` | 人员移动 | 关键点中心或包围框位移 |
| `person_static` | 人员静止 | 关键点位移低于阈值 |
| `multiple_persons` | 多人聚集 | 附近人员数量超过阈值 |
| `bending_or_crouching` | 弯腰或蹲下 | 髋、膝、肩关键点相对关系 |
| `loading_unloading` | 疑似装卸 | 弯腰/蹲下 + 手部反复活动 + 车辆旁人员 |
| `person_entering_vehicle` | 疑似进入车辆 | 人员中心进入车辆框且持续存在 |
| `long_time_loitering` | 长时间徘徊 | 人员在附近停留超过阈值 |
| `fall_down` | 疑似跌倒 | 躯干角度异常、中心高度骤降 |
| `unknown_behavior` | 行为未知 | 关键点质量低或序列不足 |

第一阶段优先保证：

1. `person_present`
2. `person_static`
3. `person_moving`
4. `multiple_persons`
5. `bending_or_crouching`
6. `long_time_loitering`

这些标签已足够支撑风险分级和人工复核。

## 7. 风险分级规则

行为标签不能直接替代风险等级，必须与停留时长、区域类型和车辆状态联合判断。

| 停留时长 | 行为状态 | 初始风险 | 处理策略 |
| --- | --- | --- | --- |
| 未超时 | 无人 | low | 仅记录轨迹 |
| 未超时 | 疑似装卸 | low | 记录，不推送 |
| 超时 | 无人 | medium | 进入复核队列 |
| 超时 | 有人静止 | medium | 进入复核队列 |
| 超时 | 有人移动或徘徊 | high | 实时提醒 |
| 超时 | 多人聚集 | high | 实时提醒 |
| 任意时长 | 疑似跌倒 | critical | 立即提醒 |
| 任意时长 + 高风险区域 | 疑似进入车辆 | high/critical | 立即提醒 |

第一阶段规则只做增强，不改变现有 `low / medium / high / critical` 体系。

## 8. 关键数据结构

### 8.1 边缘输出的人员对象

```json
{
  "person_track_id": "track-cam-001-person-12",
  "vehicle_track_id": "track-cam-001-7",
  "bbox": [320, 180, 560, 720],
  "confidence": 0.91,
  "keypoints": [
    {"index": 0, "name": "nose", "x": 430.2, "y": 210.5, "score": 0.94}
  ],
  "person_state": "person_static",
  "near_vehicle_seconds": 62.5,
  "sample_fps": 2.0
}
```

### 8.2 行为推理结果

```json
{
  "person_track_id": "track-cam-001-person-12",
  "vehicle_track_id": "track-cam-001-7",
  "behavior_label": "loading_unloading",
  "behavior_confidence": 0.82,
  "sequence_frame_count": 12,
  "sequence_start_time": "2026-09-24T15:10:02+08:00",
  "sequence_end_time": "2026-09-24T15:10:08+08:00",
  "model_type": "rule",
  "model_version": "person-behavior-rule-v1"
}
```

`model_type` 初始支持：

1. `rule`：基于姿态关键点和业务规则的判断。
2. `gru`：后续接入的 GRU/LSTM 时序模型。

### 8.3 云端扩展字段

现有 `KeyframeCreate.detected_objects` 可以继续承载检测结果，但事件层建议增加结构化行为信息：

```json
{
  "person_track_id": "track-cam-001-person-12",
  "vehicle_track_id": "track-cam-001-7",
  "behavior_label": "long_time_loitering",
  "behavior_confidence": 0.88,
  "near_vehicle_seconds": 312.0,
  "sequence_frame_count": 12,
  "pose_model_version": "yolov8n-pose",
  "behavior_model_type": "rule",
  "behavior_model_version": "person-behavior-rule-v1"
}
```

云端建议新增或扩展三类数据：

| 对象 | 作用 |
| --- | --- |
| 人员轨迹 `PersonTrack` | 保存人员跨帧 ID、首末时间、关联车辆轨迹 |
| 行为序列 `BehaviorSequence` | 保存关键点序列摘要或对象存储地址 |
| 行为结果 `BehaviorResult` | 保存行为标签、置信度、模型类型、模型版本 |

## 9. 模型落地路径

### 阶段 A：规则引擎上线

目标：不依赖训练数据，先产生业务结果。

1. 接入 YOLOv8n-pose。
2. 增加 person ByteTrack。
3. 建立 person track 与 vehicle track 关联。
4. 提取关键点序列。
5. 用规则输出 `person_present`、`person_static`、`person_moving`、`multiple_persons`。
6. 把行为结果写入事件详情和复核页。

验收：

1. 静止车辆旁有人时，事件能显示“有人活动”。
2. 人员跨帧 ID 稳定。
3. 边缘姿态推理延迟可被监控。
4. 行为结果可追溯到模型版本。

### 阶段 B：样本积累

目标：为时序模型准备数据。

1. 将关键点序列按事件缓存。
2. 保存人工复核结果。
3. 保存误报原因和纠正标签。
4. 建立行为标注队列。
5. 每周输出标签分布和难例数量。

验收：

1. 每个行为结果都有 `person_track_id`、`vehicle_track_id` 和时间窗口。
2. 人工复核可以纠正行为标签。
3. 样本可导出为训练集。

### 阶段 C：GRU/LSTM 时序模型

目标：用模型替代部分规则，提升稳定性和召回。

1. 输入 8 到 16 帧关键点序列。
2. 输出行为标签和置信度。
3. 与规则引擎并行运行。
4. 两者结果不一致时进入难例队列。
5. 灰度通过后再切换为主判断。

验收：

1. 行为分类准确率不低于 85%。
2. 异常行为召回率不低于 90%。
3. 单序列推理延迟不高于 300 ms。
4. 行为结果可按模型版本追溯。

### 阶段 D：复杂行为增强

目标：在数据充足后再提升细粒度能力。

1. 引入 ST-GCN 建模关键点图结构。
2. 引入更多现场样本训练 `loading_unloading`、`person_entering_vehicle`。
3. 对高风险区域增加专用规则。
4. 与 VL 模型结合，生成更准确的事件解释。

## 10. 前端与复核

事件详情页需要展示：

1. 车辆停留时长。
2. 关联人员数量。
3. 每个 person track 的行为标签和置信度。
4. 关键点可视化帧。
5. 行为模型类型和版本。
6. 人工复核纠正后的行为标签。

复核操作需要支持：

| 操作 | 用途 |
| --- | --- |
| 确认行为 | 正常样本回流 |
| 纠正行为标签 | 模型再训练 |
| 标记姿态失败 | 反馈关键点质量 |
| 标记人员 ID 切换 | 反馈跟踪质量 |
| 标记误报 | 降低后续误报 |

## 11. 监控指标

| 指标 | 目标 |
| --- | ---: |
| 姿态推理成功率 | ≥ 98% |
| 人员跟踪 ID 保持率 | ≥ 95% |
| 行为序列完整率 | ≥ 95% |
| 行为推理延迟 | ≤ 300 ms |
| 行为规则误报率 | ≤ 20% |
| 时序模型误报率 | ≤ 15% |
| 高风险行为召回率 | ≥ 90% |

Prometheus 建议增加：

1. `vr_pose_inference_total`
2. `vr_pose_inference_failures_total`
3. `vr_pose_inference_latency_seconds`
4. `vr_person_tracks_total`
5. `vr_person_track_id_switch_total`
6. `vr_behavior_predictions_total`
7. `vr_behavior_confidence_bucket`

## 12. 隐私与合规

1. 不上传原始连续视频。
2. 只上传关键帧、脱敏特征和结构化行为结果。
3. 姿态关键点不用于身份识别。
4. 前端展示时优先使用人脸模糊后的图像。
5. 行为序列数据按业务期限保留，到期清理。
6. 算法人员默认只能访问脱敏样本。
7. 关键帧访问、模型调用和数据导出必须记录审计日志。

## 13. 实施清单

### 第一批

1. 新增 `pose_model_path`、`pose_sample_fps`、`person_max_tracks` 配置。
2. 新增 `PersonPoseDetector`。
3. 新增 person ByteTrack 实例。
4. 建立 `person_track_id -> vehicle_track_id` 映射。
5. 实现行为序列缓存。
6. 实现第一阶段行为规则。
7. 扩展边缘事件上报 payload。
8. 扩展事件详情展示。

### 第二批

1. 新增行为序列表和行为结果表。
2. 增加复核纠正字段。
3. 增加行为指标埋点。
4. 增加样本导出工具。
5. 训练 GRU/LSTM 基线。
6. 增加灰度开关，支持规则模型与时序模型并行。

## 14. 上线验收标准

业务验收：

1. 静止车辆旁有人活动时，事件不再只有“停留时长”，还能展示行为标签。
2. 正常装卸可以通过行为结果降低误报。
3. 长时间徘徊、多人聚集、疑似跌倒能进入更高风险处理流程。
4. 人工复核可以纠正行为标签，并回流为样本。

工程验收：

1. 不破坏现有车辆事件闭环。
2. 不上传原始视频。
3. 所有行为结果都有模型版本。
4. 边缘推理失败时，车辆停留事件仍能正常上报。
5. Prometheus 能看到姿态和行为推理指标。

## 15. 当前建议

先实现阶段 A：

```text
YOLOv8n-pose
+ person ByteTrack
+ person/vehicle 关联
+ 规则行为标签
+ 事件详情展示
```

不要一开始就训练 GRU，也不要替换现有 ByteTrack。等阶段 A 的真实数据积累后，再进入阶段 B 和阶段 C。
