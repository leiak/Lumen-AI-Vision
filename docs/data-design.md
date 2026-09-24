# 数据设计

## 1. 设计原则

1. 摄像头、区域、车辆、事件、帧、模型结果分别建模。
2. 同一事件允许多个模型结果版本，便于模型迭代对比。
3. 人工复核结果必须可追溯。
4. 关键帧元数据和对象存储地址分离。
5. 所有时间和 ID 使用稳定格式。

## 2. 核心实体

### 2.1 摄像头 camera

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| camera_id | string | 唯一 ID |
| name | string | 摄像头名称 |
| location | string | 安装位置 |
| status | enum | online、offline、disabled |
| stream_url | string | 视频流地址，仅内部保存 |
| edge_node_id | string | 所属边缘节点 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

### 2.2 分析区域 area

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| area_id | string | 区域 ID |
| camera_id | string | 所属摄像头 |
| name | string | 区域名称，如库门口 |
| polygon | json | 多边形坐标 |
| area_type | enum | gate、dock、channel、loading |
| stay_threshold_seconds | int | 默认停留阈值 |
| high_risk_seconds | int | 高风险阈值 |
| enabled | bool | 是否启用 |

### 2.3 车辆轨迹 vehicle_track

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| track_id | string | 轨迹 ID，摄像头内唯一 |
| camera_id | string | 摄像头 ID |
| area_id | string | 关联区域 |
| vehicle_type | enum | car、van、truck、forklift、unknown |
| start_time | timestamp | 轨迹开始 |
| end_time | timestamp | 轨迹结束 |
| enter_area_time | timestamp | 进入区域时间 |
| leave_area_time | timestamp | 离开区域时间 |
| static_seconds | int | 区域内静止时长 |
| status | enum | moving、static、left、lost |

### 2.4 关键帧 keyframe

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| frame_id | string | 帧 ID |
| track_id | string | 车辆轨迹 ID |
| event_id | string | 事件 ID，可后置关联 |
| timestamp | timestamp | 采集时间 |
| storage_url | string | 对象存储地址 |
| width | int | 宽度 |
| height | int | 高度 |
| frame_role | enum | enter、static_start、state_change、timeout、leave、background |
| quality_score | float | 图像质量分 |
| detected_objects | json | 目标检测摘要 |
| privacy_processed | bool | 是否已脱敏 |

### 2.5 业务事件 event

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| event_id | string | 事件 ID |
| camera_id | string | 摄像头 ID |
| area_id | string | 区域 ID |
| track_id | string | 车辆轨迹 ID |
| event_type | enum | abnormal_stay、normal_stay、channel_blocking、loading_unloading |
| risk_level | enum | low、medium、high、critical |
| start_time | timestamp | 事件开始 |
| end_time | timestamp | 事件结束 |
| duration_seconds | int | 停留时长 |
| status | enum | candidate、analyzing、confirmed、rejected、closed |
| summary | text | 系统摘要 |
| created_at | timestamp | 事件创建时间 |

### 2.6 模型结果 model_result

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| result_id | string | 结果 ID |
| event_id | string | 事件 ID |
| model_name | string | 模型名称 |
| model_version | string | 模型版本 |
| model_type | enum | detector、keyframe、temporal、vl |
| label | string | 模型标签 |
| score | float | 置信度 |
| output | json | 完整输出 |
| latency_ms | int | 推理耗时 |
| created_at | timestamp | 创建时间 |

### 2.7 人工复核 review

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| review_id | string | 复核 ID |
| event_id | string | 事件 ID |
| reviewer_id | string | 复核人 |
| result | enum | abnormal、normal、uncertain |
| corrected_event_type | string | 人工纠正类型 |
| corrected_risk_level | string | 人工纠正风险等级 |
| comment | text | 复核备注 |
| reviewed_at | timestamp | 复核时间 |
| used_for_training | bool | 是否回流训练 |

## 3. 关系

1. 一个摄像头可以有多个分析区域。
2. 一次车辆轨迹只属于一个摄像头，但可能跨越多个区域。
3. 一个轨迹可以产生零个或多个事件。
4. 一个事件关联多个关键帧。
5. 一个事件可以有多个模型结果。
6. 一个人工复核记录只对应一个事件。

## 4. 状态机

### 4.1 车辆轨迹状态

```text
moving -> static -> moving -> left
                 \-> lost
```

### 4.2 事件状态

```text
candidate -> analyzing -> confirmed -> closed
                      \-> rejected
```

## 5. 索引建议

| 表 | 索引 |
 | --- | --- |
| vehicle_track | camera_id + start_time |
| vehicle_track | area_id + status |
| keyframe | track_id + timestamp |
| keyframe | event_id |
| event | camera_id + start_time |
| event | area_id + event_type + status |
| event | risk_level + status |
| model_result | event_id + model_name |
| review | event_id |

## 6. 事件上报数据示例

```json
{
  "event": {
    "camera_id": "cam-gate-001",
    "area_id": "area-gate-001",
    "track_id": "track-20260923-0001",
    "event_type_hint": "abnormal_stay",
    "start_time": "2026-09-23T10:00:00+08:00",
    "end_time": "2026-09-23T10:05:30+08:00",
    "duration_seconds": 330
  },
  "vehicle_track": {
    "vehicle_type": "truck",
    "status": "static"
  },
  "keyframes": [
    {
      "frame_id": "frame-0001",
      "timestamp": "2026-09-23T10:00:01+08:00",
      "frame_role": "enter",
      "storage_url": "https://storage.example.com/frame-0001.jpg"
    }
  ]
}
```

