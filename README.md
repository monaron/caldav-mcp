# caldav-mcp

> CalDAV MCP Server — FastMCP 包装 [python-caldav](https://github.com/python-caldav/caldav)
> 为共享 FastMCP 服务，端口 8769。

## 上游

- **caldav**: `python-caldav/caldav` (Apache 2.0), 通过 `requirements.txt` 锁定版本
- **MCP 层**: 自写 `server.py` (~200 行 FastMCP)

## 环境变量

| 变量 | 说明 |
|------|------|
| `CALDAV_URL` | CalDAV 服务地址 |
| `CALDAV_USERNAME` | 用户名 |
| `CALDAV_PASSWORD` | 密码 |
| `PORT` | 服务端口（默认 8769） |

## MCP Tools

| 工具 | 说明 |
|------|------|
| `list_calendars` | 列出所有日历 |
| `list_events` | 按时间范围列出事件 |
| `create_event` | 创建事件 |
| `update_event` | 按 UID 更新事件 |
| `delete_event` | 按 UID 删除事件 |

## 部署

CI push → `ghcr.io/monaron/caldav-mcp:latest` + `:<sha>`
→ ArgoCD Image Updater 检测 digest 变动 → 写回 infrastructure `values.yaml`
→ ArgoCD 同步 → 滚动更新
