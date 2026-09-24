# 库门口异常停留识别系统

## 项目简介

本项目面向仓储、制造和物流园区，构建“端边云协同 + 小模型初筛 + 大模型理解”的异常停留识别系统。边缘侧负责视频接入、车辆检测、区域判断和关键帧抽取；云端负责异常分类、VL 语义解释、事件管理、人工复核和持续优化。

## 当前阶段

项目已完成第一版可运行业务闭环：边缘事件接入、异常判定、事件管理、人工复核、任务闭环、通知、审计、样本回流和基础前端页面。

## 已实现功能

- 用户登录与角色鉴权。
- 摄像头、区域配置管理。
- 边缘事件与关键帧上报。
- 事件列表、详情、模型结果查询。
- 时空分类与 VL 语义解释接口。
- 人工复核与样本回流。
- 处理任务、超时升级、通知已读。
- 审计日志与运营指标。
- MinIO 关键帧存储与本地存储回退。
- OpenAI 兼容 VL 服务接入，未配置时自动使用本地解释回退。
- Webhook 和邮件通知分发能力。

## 设计文档

| 文档 | 内容 |
| --- | --- |
| [业务设计](docs/business-design.md) | 业务场景、用户角色、事件流程、规则、指标与合规 |
| [模型设计](docs/model-design.md) | 三层模型架构、候选模型、评估、训练与部署 |
| [数据设计](docs/data-design.md) | 核心实体、关系、状态机、索引和事件示例 |
| [API 设计](docs/api-design.md) | 边缘上报、模型调用、业务查询、配置与错误码 |
| [运维与治理](docs/operation-design.md) | 事件终态、任务、告警、权限、隐私、去重与模型版本 |
| [技术栈选型](docs/tech-stack.md) | 前后端、模型、存储、部署和监控的唯一选型 |
| [落地路线图](docs/roadmap.md) | 从 M0 到 M6 的阶段计划、验收标准和风险 |

## 核心流程

1. 边缘侧识别车辆进入库门口区域。
2. 根据轨迹判断车辆是否静止，并启动停留计时。
3. 在进入、静止、状态变化、超时、驶离等节点抽取关键帧。
4. 云端先用轻量时空模型判断是否异常。
5. 疑似异常事件交给 VL 模型生成中文行为描述。
6. 事件进入风险分级、人工复核、统计和样本回流流程。

## 首期目标

| 指标 | 目标 |
| --- | ---: |
| 异常停留发现率 | ≥ 90% |
| 误报率 | ≤ 15% |
| 事件识别延迟 | ≤ 10 秒 |
| VL 描述延迟 | ≤ 30 秒 |
| 上传数据量下降比例 | ≥ 90% |

## 下一步

1. 确认试点摄像头和区域边界。
2. 准备边缘设备、对象存储和基础服务。
3. 建立样本采集与标注规范。
4. 编写技术架构与部署设计。
5. 启动 M1 边缘链路验证。

## 本地启动

### 1. 后端

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

后端默认使用 SQLite，接口文档地址：

```text
http://localhost:8000/docs
```

默认管理员账号：

```text
admin / admin123
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端地址：

```text
http://localhost:5173
```

### 3. 完整依赖

```bash
docker compose up -d
```

该命令会启动 PostgreSQL、Redis、RabbitMQ、MinIO、后端和前端。边缘服务建议部署在摄像头附近的边缘设备上。

### 4. 生产部署

```bash
make prod-up
```

生产编排会额外启动 Celery Worker，并使用 Nginx 提供前端静态资源、反向代理后端 API。生产环境必须在启动前替换：

```env
SECRET_KEY=change-this-in-production
EDGE_API_KEY=change-this-edge-key
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
POSTGRES_PASSWORD=...
RABBITMQ_DEFAULT_USER=...
RABBITMQ_DEFAULT_PASS=...
```

### 4. 数据库迁移

```bash
cd backend
alembic upgrade head
```

### 5. VL 服务配置

在后端 `.env` 中配置 OpenAI 兼容服务：

```env
VL_API_URL=http://your-vllm-host:8000/v1
VL_API_KEY=your-api-key
VL_MODEL_NAME=qwen2.5-vl
```

未配置时，系统会使用本地规则解释，保证开发环境可以完整跑通。
