# MiniMax Tool

> 一个用于 MiniMax 翻译与多媒体生成的轻量 Web 工具。

[English](README.md)

本版本基于 v0.1 调整，新增翻译模块、统一 API Key 管理、历史记录脱敏与生产安全加固。默认支持连接自定义 PostgreSQL，也提供 PostgreSQL 18 一体化 Docker Compose 部署。

## 功能

- 多语言翻译与源语言识别
- 图片、语音、音乐生成
- T2V、I2V、FL2V 视频生成
- API Key 加密、历史脱敏、本地媒体持久化
- 可选 HTTP Basic 认证

## 使用外部 PostgreSQL

要求 Docker Compose v2 和 PostgreSQL 16+。

```bash
cp config/database.yaml.example config/database.yaml
$EDITOR config/database.yaml
touch .master_key && chmod 600 .master_key
docker compose up -d --build
```

## 集成 PostgreSQL 18

```bash
cp config/database.pg18.yaml.example config/database.pg18.yaml
touch .master_key && chmod 600 .master_key
export POSTGRES_PASSWORD='请替换为高强度密码'
docker compose -f docker-compose.pg18.yml up -d --build
```

默认使用 Docker 命名卷 `minimax_pg18_data` 和 `minimax_uploads`。

自定义命名卷：

```bash
PG_VOLUME_NAME=my_pg_data UPLOAD_VOLUME_NAME=my_uploads \
  docker compose -f docker-compose.pg18.yml up -d
```

挂载到指定宿主机目录：

```bash
PG_DATA_PATH=/srv/minimax/postgres UPLOAD_DATA_PATH=/srv/minimax/uploads \
  docker compose -f docker-compose.pg18.yml up -d
```

每次执行 Compose 命令时都应提供相同的 `POSTGRES_PASSWORD`。PostgreSQL 18 按官方镜像要求将数据目录挂载到 `/var/lib/postgresql`。

启动后访问 <http://localhost:9060>，在 **Config Center → API Keys** 中添加 MiniMax API Key。

## 文档

- [使用说明](docs/USAGE.md)
- [部署说明](docs/DEPLOY.md)
- [安全说明](docs/SECURITY.md)
- [架构说明](docs/ARCHITECTURE.md)

## License

[MIT](LICENSE) © 2026 MiniMax Tool contributors.
