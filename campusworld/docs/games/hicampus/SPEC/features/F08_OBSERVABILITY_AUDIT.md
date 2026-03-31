# F08 - Observability & Audit

## Goal

为世界安装、进入、校验、修复全链路提供可观测性与审计能力。

## Scope

- world 管理命令事件日志
- world 入口行为日志
- 审计字段标准化（operator/world_id/action/timestamp）

## Out of Scope

- 业务告警平台接入
- 可视化大盘实现

## Dependencies

- 前置：`F04`（命令事件）与 `F05`（入口事件）
- 可并行：日志规范可先行定义

## DoD

- 关键路径均有 event name 与最小字段集
- 可按 `world_id` 检索完整操作历史
- 错误场景（安装失败/入口失败）具备诊断信息
