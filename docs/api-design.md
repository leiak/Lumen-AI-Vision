# API 设计

## 1. 总体约定

1. 使用 REST 风格。
2. 数据格式为 JSON。
3. 时间使用 ISO 8601。
4. ID 使用字符串。
5. 接口统一返回业务状态码和错误信息。
6. 边缘设备使用设备 Token 认证，控制台用户使用用户 Token 认证。

统一响应示例：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

## 2. 边缘侧接口

### 2.1 上报事件候选

`POST /api/v1/edge/events`

```json
{
  "camera_id": "cam-gate-001",
  "area_id": "area-gate-001",
  "track_id": "track-20260923-0001",
  "event_type_hint": "abnormal_stay",
  "start_time": "2026-09-23T10:00:00+08:00",
  "end_time": "2026-09-23T10:05:30+08:00",
  "duration_seconds": 330,
  "keyframes": [
    {
      "frame_id": "frame-0001",
      "timestamp": "2026-09-23T10:00:01+08:00",
      "frame_role": "enter"
    }
  ]
}
```

响应：

```json
{
  "event_id": "evt-20260923-0001",
  "accepted_keyframes": ["frame-0001"]
}
```

### 2.2 上传关键帧

`POST /api/v1/edge/keyframes`

使用 `multipart/form-data` 上传，字段包括：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| event_id | string | 是 | 事件 ID |
| frame_id | string | 是 | 帧 ID |
| timestamp | string | 是 | 采集时间 |
| frame_role | string | 是 | 帧角色 |
| image | file | 是 | 图片文件 |

### 2.3 上报轨迹状态

`POST /api/v1/edge/tracks/{track_id}/status`

```json
{
  "camera_id": "cam-gate-001",
  "area_id": "area-gate-001",
  "vehicle_type": "truck",
  "status": "left",
  "timestamp": "2026-09-23T10:06:10+08:00"
}
```

### 2.4 拉取边缘配置

`GET /api/v1/edge/config`

返回摄像头、区域、阈值、模型版本和抽帧策略。

## 3. 云端模型接口

### 3.1 时空分类

`POST /api/v1/models/temporal/classify`

```json
{
  "event_id": "evt-20260923-0001",
  "keyframe_ids": [
    "frame-0001",
    "frame-0002"
  ]
}
```

响应：

```json
{
  "event_id": "evt-20260923-0001",
  "label": "abnormal_stay",
  "score": 0.87
}
```

### 3.2 VL 语义理解

`POST /api/v1/models/vl/explain`

```json
{
  "event_id": "evt-20260923-0001",
  "keyframe_ids": [
    "frame-0001",
    "frame-0002"
  ],
  "context": {
    "area_name": "库门口",
    "duration_seconds": 330
  }
}
```

响应：

```json
{
  "event_id": "evt-20260923-0001",
  "summary": "一辆货车在库门口停留约5分30秒，期间车门打开，有人员出现。",
  "behavior": [
    "车辆进入库门口区域",
    "车辆停止",
    "车门打开",
    "人员出现"
  ],
  "possible_reason": "疑似装卸或异常滞留，需要人工确认。"
}
```

## 4. 业务查询接口

### 4.1 事件列表

`GET /api/v1/events`

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| camera_id | string | 否 | 按摄像头过滤 |
| area_id | string | 否 | 按区域过滤 |
| event_type | string | 否 | 按事件类型过滤 |
| risk_level | string | 否 | 按风险等级过滤 |
| status | string | 否 | 按事件状态过滤 |
| start_time | string | 否 | 开始时间 |
| end_time | string | 否 | 结束时间 |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20 |

### 4.2 事件详情

`GET /api/v1/events/{event_id}`

返回事件基础信息、关键帧、模型结果、轨迹摘要和复核状态。

### 4.3 人工复核

`POST /api/v1/events/{event_id}/review`

```json
{
  "result": "abnormal",
  "corrected_event_type": "channel_blocking",
  "corrected_risk_level": "high",
  "comment": "货车长时间占用库门口通道。"
}
```

## 5. 配置接口

### 5.1 区域配置

`POST /api/v1/areas`

```json
{
  "camera_id": "cam-gate-001",
  "name": "库门口",
  "area_type": "gate",
  "polygon": [[0, 0], [100, 0], [100, 80], [0, 80]],
  "stay_threshold_seconds": 300,
  "high_risk_seconds": 600
}
```

### 5.2 更新抽帧策略

`PUT /api/v1/cameras/{camera_id}/sampling-policy`

```json
{
  "motion_threshold": 0.08,
  "similarity_threshold": 0.92,
  "min_interval_ms": 800,
  "max_frames_per_event": 12
}
```

## 6. 错误码

| code | 含义 |
| ---: | --- |
| 0 | 成功 |
| 10001 | 参数错误 |
| 10101 | 设备未认证 |
| 10201 | 摄像头不存在 |
| 10301 | 事件不存在 |
| 10401 | 关键帧上传失败 |
| 10501 | 模型推理失败 |
| 10601 | 权限不足 |
| 50000 | 服务内部错误 |

