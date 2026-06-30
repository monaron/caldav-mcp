# caldav-mcp

> CalDAV MCP Server — FastMCP 包装 python-caldav。
> 端口 8769，部署于 relay 命名空间。

## 强制前置

> **共享层规范**：目前无共享文件依赖。

> 运维日志 → `./LOGBOOK.md`

## 仓库

```
caldav-mcp/
├── AGENTS.md                 # AI agent 指令
├── LOGBOOK.md                # 运维日志
├── README.md                 # 项目文档
├── .gitignore
├── Dockerfile                # CI 构建
├── server.py                 # FastMCP 服务入口
├── requirements.txt          # caldav + fastmcp
└── .github/
    └── workflows/deploy.yml  # CI/CD → ghcr.io
```

## 部署

通过 CI/CD 推送至 `ghcr.io/monaron/caldav-mcp`，ArgoCD 同步部署。

## 约定

- 提交信息：中文，动词开头 ("添加"、"修复"、"更新")
- 不提交 `.env`、backup 文件、临时 zip、`.DS_Store`
- 配置变更后同步更新 `LOGBOOK.md`
