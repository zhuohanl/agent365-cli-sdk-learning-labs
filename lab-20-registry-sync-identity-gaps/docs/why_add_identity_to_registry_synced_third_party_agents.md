限定到这份 fleet 后，给 AWS 和 GCP 配置身份就有明确用途了：让它们实际使用 Entra 认证，并向 Agent 365 上报活动，而不是单纯补齐清单里的 ID。 但“缺少上报身份”和“页面显示 unmanaged”仍要分开看。

1. 当前范围确实可以收窄到 AWS 和 GCP

我读了  agent_fleet.md ，具体是：

┌───────────────────────┬──────────────────────────────────────────────────┐
│ 平台                  │ 当前讨论的接入范围                               │
├───────────────────────┼──────────────────────────────────────────────────┤
│ AWS AgentCore Runtime │ 自定义 Observability + Governance                │
├───────────────────────┼──────────────────────────────────────────────────┤
│ Google agent runtime  │ 自定义 Observability + Governance                │
├───────────────────────┼──────────────────────────────────────────────────┤
│ Salesforce Agentforce │ 不做自定义接入；文档仍保留展示平台自带能力的目标 │
├───────────────────────┼──────────────────────────────────────────────────┤
│ Claude Managed Agent  │ Observability、Governance 均为 NA                │
└───────────────────────┴──────────────────────────────────────────────────┘

另外，文档明确说： completed  代表基础 agent 已完成，不代表 A365 SDK、AWS sidecar 等后续接入已经完成。

2. Governance：AWS sidecar、GCP federation 可以作为接入方向

你的理解基本正确：

• **AWS：**通过 Entra Auth SDK／sidecar 帮助 agent 获取 Entra token。不过这里是 AgentCore Runtime，仍需确认认证组件的实际部署方式，不能直接把普通 Docker sidecar 示例视为已经适配。
• **GCP：**通过 workload identity federation，用可被 Entra 信任的 Google 身份换取 Entra token。具体要用运行环境实际能取得的令牌，不能仅凭它有 Google Agent Identity 就认定已能直接联合认证。

两者解决的都是 “如何证明自己是谁、取得 token”。随后还需要 MCP server 根据这个身份执行权限控制；GCP 的 PII 检测、AWS 的数据权限等，也不是有了 token 就自动实现。

3. Observability：你描述的阻塞有实际意义，但要准确命名

Application Insights 已接通这一点，我们按你同事提供的现状理解。 更准确的说法是“不需要 Entra Agent Identity”，而不是“不需要任何认证或接入配置”。

Agent 365 则是另一条上报通道：

已有的 OTel 活动数据
    ├─→ Application Insights：已接通
    └─→ Agent 365：还需要上报认证、权限和正确的身份关联

Agent 365 Observability SDK 文档明确要求为 exporter 提供获取 token 的方法。因此，如果目前没有可用于上报的 Entra 身份和相应授权，“身份接入缺失阻塞了 A365 上报”是合理的描述。

但不能直接把它写成：

Registry Sync 显示 unmanaged，所以 SDK 不能上报。

这里实际有三个独立环节：

┌────────────────┬───────────────────────────────────────────────────────────────┐
│ 环节           │ 需要解决的问题                                                │
├────────────────┼───────────────────────────────────────────────────────────────┤
│ 上报认证       │ 用哪个 Entra 身份取得 A365 遥测服务的 token，并获准写入？     │
├────────────────┼───────────────────────────────────────────────────────────────┤
│ 数据上报       │ 活动格式、身份信息、许可等是否满足接收要求？                  │
├────────────────┼───────────────────────────────────────────────────────────────┤
│ 清单关联与展示 │ 活动最终显示在哪条记录上：原始 synced agent，还是 companion？ │
└────────────────┴───────────────────────────────────────────────────────────────┘

创建 Blueprint + Agent Identity 可以为第一环节提供身份基础，但不会自动完成后两个环节。 当前官方观测文档也支持普通 Entra app registration，所以“需要可用的 Entra 上报身份”和“必须创建 Blueprint + Agent Identity”并不是完全相同的结论。

不过，对于你这里同时需要 agent 级访问治理的 AWS/GCP，采用 Blueprint + Agent Identity 是有明确理由的设计选择：让同一个逻辑 agent 的工具访问和活动上报使用一致的身份归属，但分别申请目标服务的 token 和权限。

因此，现在可以把 Lab 20 的目的明确为：

为 AWS/GCP agent 建立实际可用的 Entra Agent Identity，支撑 MCP 访问控制和 Agent 365 活动上报；另外解决该身份与 Registry Sync 清单记录的关联。

这样，companion registration 是最后这部分的候选解决手段，而不再被当作“创建后就能自动开启 Activity”的开关。

==================================

可以把这个目的翻译成为准确的英文吗

Enable agents hosted on AWS and GCP to use Microsoft Entra Agent Identities for identity-based access control to MCP servers and activity telemetry reporting to Microsoft Agent 365. Separately, establish the association between these identities and the corresponding Registry Sync inventory records.