# 方案 B：离线视频真实测试包

方案 B 不依赖现场摄像头，用一段 mp4 视频回放完整验证“边缘检测 → 事件上报 → 云端闭环”。

## 1. 准备资源

### 视频

任选一段包含车辆进入、停止、离开的画面，推荐 10–30 秒、720p 以上：

- 自拍现场视频：优先，最贴近真实业务。
- 客户授权视频/NVR 导出：用于试点验证。
- [Pexels Videos](https://www.pexels.com/search/videos/parking%20lot/)：免费测试素材。
- [Pixabay Videos](https://pixabay.com/videos/search/parking/)：免费测试素材。
- [Coverr](https://coverr.co/)：免费测试素材。

视频保存到本地，例如：

```text
D:/videos/gate-test.mp4
```

不要把大视频提交到 Git。

### YOLO 模型

第一次运行时可从 [Ultralytics YOLOv8](https://docs.ultralytics.com/models/yolov8/) 获取 `yolov8n.pt`，放到：

```text
D:/models/yolov8n.pt
```

## 2. 启动云端

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

检查：

```bash
curl http://localhost:5032/healthz
```

默认账号仍是：

```text
admin / admin123
```

## 3. 初始化测试摄像头和区域

在仓库根目录执行：

```bash
python tools/seed_camera_area.py --base-url http://localhost:5032
```

默认创建：

```text
camera_id=cam-gate-test-001
area_id=area-gate-test-001
停留阈值=30 秒
高风险阈值=60 秒
```

如需更符合真实业务，可改：

```bash
python tools/seed_camera_area.py --stay-threshold-seconds 300 --high-risk-seconds 600
```

同时把 `edge/.env.test.example` 中的阈值改成一致。

## 4. 配置边缘测试环境

复制：

```bash
cp edge/.env.test.example edge/.env.test
```

至少修改：

```env
VIDEO_SOURCE=D:/videos/gate-test.mp4
MODEL_PATH=D:/models/yolov8n.pt
API_BASE_URL=http://localhost:5032
API_KEY=change-this-edge-key
STAY_THRESHOLD_SECONDS=30
HIGH_RISK_SECONDS=60
```

`AREA_POLYGON` 支持两种坐标：

- `0~1` 归一化坐标：适合快速测试；
- 像素坐标：适合真实现场标定，例如 `[[220,180],[1040,180],[1040,720],[220,720]]`。

`MOVEMENT_THRESHOLD_PIXELS` 用于判断车辆是否重新移动。`LOST_TRACK_TOLERANCE_SECONDS` 用于容忍遮挡或短时丢帧，超过该秒数仍找不到轨迹才会重置停留状态。

## 5. 运行离线视频

```bash
cd edge
python -m edge.visual_recognition_edge.main --max-frames 0
```

如果视频较长，可先缩短测试：

```bash
python -m edge.visual_recognition_edge.main --max-frames 900
```

注意：事件只在车辆在区域内静止且达到 `STAY_THRESHOLD_SECONDS` 后上报。

## 6. 校验业务闭环

```bash
python tools/validate_event.py --base-url http://localhost:5032
```

脚本会检查事件时长、风险等级、关键帧数量和关键帧文件可访问性。

然后打开：

```text
http://localhost:5032
```

确认：

1. 事件列表能看到测试事件。
2. 事件详情能看到真实关键帧图片。
3. 复核后事件状态更新。
4. 任务页面能看到待处理任务。
5. 通知页面能看到当前管理员的通知。
6. 指标页面出现事件统计。

## 7. 测试资源来源

| 资源 | 来源 |
| --- | --- |
| 测试视频 | 自拍、客户授权 NVR 导出、Pexels、Pixabay、Coverr |
| 车辆数据集 | UA-DETRAC、AI City Challenge、VisDrone、PKLot、Roboflow Universe、Kaggle |
| 标注工具 | CVAT、Label Studio、Roboflow |
| VL 服务 | Qwen2.5-VL + vLLM/Ollama，或任意 OpenAI 兼容云端服务 |
| 临时 RTSP | FFmpeg 将 mp4 转 RTSP，或 MediaMTX 做本地推流 |

## 8. FFmpeg 转 RTSP 示例

本机验证可用：

```bash
ffmpeg -re -stream_loop -1 -i D:/videos/gate-test.mp4 -c copy -f rtsp rtsp://127.0.0.1:8554/gate-test
```

然后把边缘配置改为：

```env
VIDEO_SOURCE=rtsp://127.0.0.1:8554/gate-test
VIDEO_TIMESTAMP_MODE=realtime
```

真实 RTSP 摄像头也使用同样的方式，只需要替换为摄像头地址，并确保有授权。
