# 模拟数据测试 vs 真实环境测试数据

## 已经覆盖：模拟数据 E2E 测试

`backend/tests/test_e2e_simulation.py` 在**完全合成数据**下走完了完整业务流：

| 步骤 | 模拟数据来源 |
|---|---|
| 用户（admin / operator / supervisor / security / duty_admin / ops_lead） | 脚本内创建 |
| 摄像头 ×3 + 区域 ×4 + AreaGroup | 脚本内创建 |
| 30 个边缘事件上报 | 随机 vehicle_plate_hash / 时长 |
| 关键帧（含隐私脱敏状态） | numpy 噪声 → JPEG 字节 |
| 时序分类 + VL 解释 | 走本地回退解释 |
| 复审 5 个事件 | 脚本内循环 |
| 模型准确率统计 | 脚本内构造 TrainingSample |
| 任务升级 | 脚本内插入 due_at 过期的 Task |
| 通知分发 | 走 in_app 渠道（无外部依赖） |
| CSV 导出 | 流式写入响应 |
| 数据保留清理 | 脚本内插入 100 天前事件 |

**运行方式**：

```bash
# 本地
make e2e-test

# Docker（无外部依赖，最快）
make test-up
```

测试结果（2026-09-26 实测）：
- 本地 pytest 全套：**37 + 10 = 47 passed**
- Docker 测试 compose：**37 + 1 passed**

## 还需要外部数据才能验证的真实业务点

下面这些点用合成数据只能验证接口/逻辑，**无法**验证算法/精度/视觉。  
如果你有下列任何一项，可以让验证更接近真实。

### 1. 离线视频（强烈推荐）
一段 10–30 秒、720p 以上的视频，画面包含"车辆进入 → 静止 → 离开"。

| 来源 | 说明 |
|---|---|
| 自拍现场 | 最贴近真实业务 |
| 客户授权 NVR 导出 | 用于试点验证 |
| [Pexels Parking Lot 视频](https://www.pexels.com/search/videos/parking%20lot/) | 免费素材 |
| [Pixabay Parking 视频](https://pixabay.com/videos/search/parking/) | 免费素材 |
| [Coverr](https://coverr.co/) | 免费素材 |

保存到本地（**不要提交到 Git**）：`D:/videos/gate-test.mp4`

### 2. YOLO 模型权重（运行边缘必需）
| 文件 | 来源 |
|---|---|
| `yolov8n.pt` | [Ultralytics](https://docs.ultralytics.com/models/yolov8/) |
| `yolov8n-pose.pt` | 同上 |

仓库根目录已有占位文件（如果你需要替换为更准的型号）。

### 3. 真实 RTSP 流（可选）
如果只有 mp4，可以用 FFmpeg 模拟 RTSP：

```bash
ffmpeg -re -stream_loop -1 -i D:/videos/gate-test.mp4 \
  -c copy -f rtsp rtsp://127.0.0.1:8554/gate-test
```

### 4. 标注数据（可选，用于训练样本回灌）
| 数据集 | 用途 |
|---|---|
| [UA-DETRAC](https://detrac-db.rit.albany.edu/) | 车辆检测/跟踪 |
| [AI City Challenge](https://www.aicitychallenge.org/) | 多摄像头车辆重识别 |
| [VisDrone](http://aiskyeye.com/) | 无人机车辆/行人 |
| [PKLot](https://pklot.wordpress.com/) | 车位检测 |
| [Roboflow Universe](https://universe.roboflow.com/) | 通用 |

### 5. VL 大模型 API（可选，用于解释质量）
走本地回退的解释只生成时长模板。要验证真正的视觉解释，需要：

```env
VL_API_URL=https://your-vl-endpoint
VL_API_KEY=your-key
VL_MODEL_NAME=qwen2.5-vl
```

任意 OpenAI 兼容接口都行（vLLM、Ollama 等本地服务亦可）。

### 6. 真实摄像头 + 现场环境（部署阶段）
- 现场摄像头 RTSP 地址
- 现场区域多边形坐标（pixel）
- 现场用户名单（admin / supervisor / security / duty_admin / ops_lead）
- 现场时区（默认 Asia/Shanghai）

## 完整测试入口汇总

```bash
# 1. 单元/集成测试（mock）
make test

# 2. 端到端模拟测试（mock 数据）
make e2e-test

# 3. Docker 中的端到端模拟（无外部依赖）
make test-up

# 4. 开发 compose（Postgres + Redis + RabbitMQ + MinIO + 后端 + worker + beat + 前端）
make dev-up
make dev-down

# 5. 生产 compose（含 Prometheus + Grafana）
make prod-up
make prod-down

# 6. 真实视频回放（需要外部视频 + 模型权重）
# 详见 tools/README-real-test.md
```