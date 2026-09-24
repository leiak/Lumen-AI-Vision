# 技术栈选型

## 1. 选型原则

1. 每个功能层只选择一个主技术。
2. 优先选择社区活跃、资料丰富、招聘和运维成本低的方案。
3. 优先支持本地化部署和后续扩展。
4. 不做备选方案并列，避免实施阶段反复摇摆。

## 2. 总体技术栈

| 层级 | 唯一选型 | 作用 |
| --- | --- | --- |
| 前端框架 | Vue 3 | 事件台、复核台、配置管理界面 |
| 前端语言 | TypeScript | 提升接口调用和组件维护稳定性 |
| 前端构建 | Vite | 开发和构建工具 |
| 前端 UI | Element Plus | 后台管理常用组件库 |
| 图表 | ECharts | 事件量、误报率、处理闭环率展示 |
| 状态管理 | Pinia | 用户、权限、页面状态管理 |
| 后端语言 | Python 3.11 | AI、视频处理和后端统一 |
| 后端框架 | FastAPI | REST API、边缘接入、业务服务 |
| 数据校验 | Pydantic v2 | 请求、响应、配置模型校验 |
| ORM | SQLAlchemy 2.0 | PostgreSQL 数据访问 |
| 数据库迁移 | Alembic | 数据库版本管理 |
| 主数据库 | PostgreSQL 16 | 摄像头、区域、事件、任务、审计数据 |
| 缓存 | Redis 7 | 会话、限流、任务状态、热点配置 |
| 消息队列 | RabbitMQ | 边缘事件、模型任务、通知任务解耦 |
| 对象存储 | MinIO | 关键帧、脱敏图片、导出文件 |
| 异步任务 | Celery 5 | 模型调用、通知发送、统计任务 |
| 边缘视频处理 | OpenCV | 视频解码、抽帧、图像预处理 |
| 边缘目标检测 | YOLOv8n | 车辆检测 |
| 边缘目标跟踪 | ByteTrack | 车辆轨迹关联 |
| 关键帧特征 | MobileNetV3-Small | 帧特征提取和相似度过滤 |
| 边缘推理 | ONNX Runtime | 边缘模型统一推理 |
| 模型训练 | PyTorch 2.x | 异常分类模型训练 |
| VL 模型 | Qwen2.5-VL | 事件语义描述 |
| VL 推理服务 | vLLM | VL 模型高吞吐部署 |
| 模型实验管理 | MLflow | 数据集、模型版本、评估记录 |
| 认证方式 | OAuth2 + JWT | 用户登录和接口鉴权 |
| 容器化 | Docker | 统一部署环境 |
| 编排部署 | Kubernetes | 云端服务扩缩容和发布 |
| 监控 | Prometheus + Grafana | 服务、模型、边缘节点监控 |
| 日志 | Loki | 集中日志查询 |
| API 文档 | OpenAPI | FastAPI 自动生成接口文档 |
| 后端测试 | pytest | 单元测试和接口测试 |

## 3. 功能与技术映射

### 3.1 视频接入与关键帧

| 功能 | 技术 |
| --- | --- |
| 视频流读取 | OpenCV |
| 视频解码 | OpenCV / FFmpeg |
| 车辆检测 | YOLOv8n |
| 车辆跟踪 | ByteTrack |
| 区域判断 | Python 规则引擎 + PostgreSQL 配置 |
| 停留计时 | Redis + 边缘状态机 |
| 关键帧筛选 | MobileNetV3-Small + NumPy |
| 图像保存 | MinIO |

### 3.2 云端分析与事件管理

| 功能 | 技术 |
| --- | --- |
| 事件接收 | FastAPI |
| 事件存储 | PostgreSQL |
| 模型任务调度 | RabbitMQ + Celery |
| 异常停留分类 | PyTorch |
| VL 语义解释 | Qwen2.5-VL + vLLM |
| 模型版本管理 | MLflow |
| 结果展示 | Vue 3 + Element Plus + ECharts |

### 3.3 运营治理

| 功能 | 技术 |
| --- | --- |
| 用户认证 | OAuth2 + JWT |
| 权限控制 | FastAPI + PostgreSQL 权限模型 |
| 审计日志 | PostgreSQL + Loki |
| 告警通知 | Celery + RabbitMQ |
| 服务监控 | Prometheus + Grafana |
| 日志查询 | Loki |
| 容器部署 | Docker |
| 云端编排 | Kubernetes |

## 4. 推荐版本

| 组件 | 版本 |
| --- | --- |
| Python | 3.11 |
| Node.js | 20 LTS |
| PostgreSQL | 16 |
| Redis | 7 |
| RabbitMQ | 3.13 |
| PyTorch | 2.x |
| FastAPI | 最新稳定版 |
| Vue | 3.x |
| Vite | 最新稳定版 |
| Element Plus | 最新稳定版 |
| Docker | 最新稳定版 |
| Kubernetes | 1.29+ |

## 5. 部署形态

### 5.1 边缘侧

1. 边缘设备部署 Docker。
2. 使用 Python + OpenCV 读取视频流。
3. 使用 YOLOv8n 做车辆检测。
4. 使用 ByteTrack 做车辆跟踪。
5. 使用 ONNX Runtime 执行边缘模型。
6. 关键帧压缩后上传 MinIO。

### 5.2 云端

1. FastAPI 提供 REST API。
2. PostgreSQL 保存核心业务数据。
3. RabbitMQ 解耦事件、模型和通知任务。
4. Celery 执行异步任务。
5. MinIO 保存关键帧。
6. vLLM 部署 Qwen2.5-VL。
7. Kubernetes 管理云端服务扩缩容。

### 5.3 前端

1. Vue 3 + Vite 构建管理后台。
2. Element Plus 提供表单、表格、弹窗等组件。
3. ECharts 展示事件趋势和模型效果。
4. Pinia 管理登录和权限状态。

## 6. 为什么是这些技术

| 技术 | 选择理由 |
| --- | --- |
| Python | AI 和后端生态统一，视频处理库成熟 |
| FastAPI | 异步性能好，自动生成 OpenAPI 文档 |
| PostgreSQL | 业务数据结构清晰，支持 JSON 和事务 |
| Redis | 缓存、限流、状态管理简单可靠 |
| RabbitMQ | 事件模型和模型任务解耦，稳定性高 |
| MinIO | 兼容 S3 协议，支持本地化部署 |
| YOLOv8n | 精度和边缘速度均衡，社区资源多 |
| ByteTrack | 多目标跟踪效果好，实现成熟 |
| MobileNetV3-Small | 轻量特征提取，适合关键帧过滤 |
| ONNX Runtime | 边缘推理兼容性好 |
| PyTorch | 模型训练生态最完善 |
| Qwen2.5-VL | 中文视觉理解和事件解释能力强 |
| vLLM | VL 模型部署吞吐高 |
| Vue 3 | 后台管理开发效率高，生态成熟 |
| Docker / Kubernetes | 本地化和云端扩展都友好 |

## 7. 后续建议

1. 先用 Docker Compose 完成本地联调。
2. 试点稳定后再迁移到 Kubernetes。
3. 后端从 FastAPI 项目骨架开始实现。
4. 边缘端先实现视频接入、检测、跟踪和关键帧上传。
5. 前端先做事件列表、事件详情和人工复核。

