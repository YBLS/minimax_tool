# MiniMax 工具集 — 架构设计

## 目标

构建一个本地 Web 工具，统一调用 MiniMax（MiniMax）API 的 4 类生成能力（图像 / 语音 / 音乐 / 视频），
并把 API 凭证、调用记录、生成产物在本地落地，方便日常调试与对比。

## 总体架构

```
┌────────────────────────────────────────────────────────────┐
│                    浏览器 (React SPA)                       │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐ │
│  │ Image    │ Voice    │ Music    │ Video    │ Config   │ │
│  │ Studio   │ Studio   │ Studio   │ Studio   │ Center   │ │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘ │
└───────────────────────────┬────────────────────────────────┘
                            │  REST / JSON  (port 9060)
┌───────────────────────────▼────────────────────────────────┐
│                  FastAPI  (Python 3.13)                    │
│  ┌────────────┬────────────┬────────────┬─────────────┐    │
│  │ /configs   │ /generate  │ /history   │ /secrets    │    │
│  └─────┬──────┴─────┬──────┴─────┬──────┴──────┬──────┘    │
│        │            │            │             │           │
│  ┌─────▼────────────▼────────────▼─────────────▼──────┐    │
│  │         Generation Service (per module)           │    │
│  │  ┌────────┬────────┬────────┬────────┐            │    │
│  │  │ Image  │ Voice  │ Music  │ Video  │            │    │
│  │  │ Svc    │ Svc    │ Svc    │ Svc    │            │    │
│  │  └────────┴────────┴────────┴────────┘            │    │
│  └────────────────────────┬───────────────────────────┘    │
│                           │ httpx                          │
└───────────────────────────┼──────────────────────────────-─┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌──────────────┐                       ┌─────────────────┐
│ PostgreSQL   │                       │ MiniMax API     │
│ (localhost)  │                       │ (api.minimaxi.com) │
└──────────────┘                       └─────────────────┘

本地落盘: ./uploads/  (图片/语音/音乐/视频)
```

## 关键设计原则

1. **凭证永远不入代码 / 不入配置文件**：API Key 通过 Web 界面写入数据库，加密存储。
2. **每个模块独立配置**：base_url、endpoint、model、请求/响应模板都可自定义。
3. **统一抽象**：4 个模块都基于 `BaseGenerator` 实现，差异在"如何把响应解析成媒体文件"。
4. **生成产物本地化**：调用成功后下载到 `uploads/`，前端通过 `/api/media/...` 读取。
5. **单端口部署**：前端 build 产物由 FastAPI 以 `StaticFiles` 挂载，9060 即可访问全栈。

## 数据库表设计

### `api_configs`
| 字段                | 类型          | 说明                                       |
|--------------------|---------------|--------------------------------------------|
| id                 | SERIAL PK     |                                            |
| module             | VARCHAR(50) U | image / voice / music / video              |
| display_name       | VARCHAR(100)  | 人类可读名称                                |
| api_key_encrypted  | TEXT          | Fernet 加密后的 API Key                     |
| base_url           | VARCHAR(500)  | API 根地址                                  |
| endpoint_path      | VARCHAR(500)  | 相对路径                                    |
| model              | VARCHAR(200)  | 模型标识                                    |
| request_template   | JSONB         | 请求体模板（含参数占位）                    |
| response_parser    | JSONB         | 响应解析规则（jsonpath 风格）                |
| default_params     | JSONB         | 默认参数（size / duration / voice_id 等）    |
| enabled            | BOOLEAN       | 是否启用                                    |
| created_at         | TIMESTAMPTZ   |                                            |
| updated_at         | TIMESTAMPTZ   |                                            |

### `generation_history`
| 字段              | 类型          | 说明                                       |
|------------------|---------------|--------------------------------------------|
| id               | SERIAL PK     |                                            |
| module           | VARCHAR(50)   |                                            |
| config_id        | INT FK        | 关联配置                                    |
| prompt           | TEXT          |                                            |
| params           | JSONB         | 调用参数（覆盖 default_params）             |
| request_payload  | JSONB         | 实际发出去的请求                             |
| response_payload | JSONB         | 实际收到的响应                               |
| output_files     | JSONB         | `[{type, url, size, path, mime_type}]`      |
| status           | VARCHAR(20)   | pending / running / success / failed        |
| error_message    | TEXT          |                                            |
| duration_ms      | INT           |                                            |
| created_at       | TIMESTAMPTZ   |                                            |

### `app_secrets`
| 字段              | 类型          | 说明                                       |
|------------------|---------------|--------------------------------------------|
| id               | SERIAL PK     |                                            |
| name             | VARCHAR(100) U| 业务侧引用名                                 |
| value_encrypted  | TEXT          | Fernet 加密后的值                            |
| description      | TEXT          |                                            |
| created_at       | TIMESTAMPTZ   |                                            |
| updated_at       | TIMESTAMPTZ   |                                            |

## API 契约（v1）

```
GET  /api/health
GET  /api/configs
GET  /api/configs/{module}
POST /api/configs
PUT  /api/configs/{id}
DEL  /api/configs/{id}
POST /api/configs/{id}/test        # 校验连通性

POST /api/generate/{module}        # body: {prompt, params?, config_id?}
GET  /api/history?module=&limit=&offset=
GET  /api/history/{id}
DEL  /api/history/{id}

GET  /api/secrets                  # 不返回 value
PUT  /api/secrets/{name}          # body: {value, description?}
DEL  /api/secrets/{name}

GET  /api/media/{path:path}        # 静态读 uploads 下的文件
GET  /                             # React 入口
```

## 加密策略

- 使用 `cryptography.fernet.Fernet`（AES-128-CBC + HMAC-SHA256）。
- 主密钥（master key）保存在项目根的 `.master_key` 文件，权限 0600。
- 也可由 `MASTER_KEY` 环境变量覆盖（便于生产部署）。
- 启动时若 `.master_key` 不存在则自动生成，并提示用户备份。

## 目录布局

```
MinimaxTool/
├── uploads/                 # 生成产物（git ignored）
├── .master_key              # 主密钥（git ignored, 0600）
├── backend/
│   ├── pyproject.toml       # uv 项目
│   ├── .python-version
│   ├── main.py
│   ├── app/                 # 业务代码
│   └── static/              # 前端 build 产物
├── frontend/                # React 源码
├── scripts/                 # 辅助脚本
├── README.md
└── .gitignore
```
