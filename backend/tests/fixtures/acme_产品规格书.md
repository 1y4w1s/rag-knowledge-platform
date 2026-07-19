# AcmeCloud 企业版 v3.2 产品规格书

**文档版本**：3.2  
**发布日期**：2025-07-17  
**产品编号**：AC-ENT-3.2-2025  
**官方文档地址**：https://docs.acmecloud.com/enterprise/v3.2  

---

## 1. 产品概述

AcmeCloud 企业版 v3.2 是面向中大型企业及政府机构的全栈式云原生基础设施管理平台，提供从计算、存储、网络到应用编排的一站式解决方案。本版本在 v3.1 基础上引入了智能资源调度引擎（IRSE 2.0），支持跨数据中心的多集群统一管理，并增强了安全合规能力，满足 SOC 2、ISO 27001 及等保 2.0 三级要求。产品采用微服务架构，核心组件基于 Kubernetes 原生设计，支持裸金属、虚拟机及容器混合部署。通过统一的控制台（AcmeConsole）和开放的 API 体系，运维团队可在 30 分钟内完成标准集群的初始化部署。v3.2 版本重点优化了 GPU 资源池化调度效率（提升 40%），并新增了基于 AI 的异常预测告警功能。平台默认提供 99.99% 的 SLA 保障，支持 10 万级节点规模的水平扩展。

---

## 2. 核心功能列表

以下为 AcmeCloud 企业版 v3.2 的 15 项核心功能，每项均附带简要说明：

| 序号 | 功能名称 | 简要说明 |
|------|----------|----------|
| 1 | **智能资源调度引擎 (IRSE 2.0)** | 基于强化学习的资源调度算法，自动优化 CPU、内存、GPU 分配，支持优先级抢占与弹性伸缩，调度延迟 < 50ms。 |
| 2 | **多集群联邦管理** | 通过单一控制面管理跨地域、跨可用区的多个 Kubernetes 集群，支持资源配额统一管控与策略同步。 |
| 3 | **GPU 资源池化** | 将物理 GPU 切分为 vGPU 实例，支持 MIG 与 vGPU 混合模式，利用率提升至 85% 以上。 |
| 4 | **容器镜像安全扫描** | 集成 Trivy 与 Clair 引擎，自动扫描镜像中的 CVE 漏洞（CVSS ≥ 7.0 自动阻断），支持自定义白名单。 |
| 5 | **应用市场 (AppStore)** | 内置 200+ 企业级 Helm Chart 应用模板，支持一键部署中间件（MySQL、Redis、Kafka 等）。 |
| 6 | **日志审计与合规** | 全量操作审计日志，保留周期 180 天（可配置），支持导出至 S3/OSS，满足等保 2.0 审计要求。 |
| 7 | **AI 异常预测告警** | 基于时序异常检测模型，提前 15 分钟预测节点故障、磁盘 I/O 瓶颈等，准确率 > 92%。 |
| 8 | **网络策略即服务 (NPaaS)** | 基于 Calico 与 Cilium 的零信任网络策略，支持微隔离、南北向/东西向流量可视化。 |
| 9 | **持久化存储管理** | 集成 Ceph、Longhorn 与 NFS，提供块存储、文件存储与对象存储，支持快照、克隆与跨集群迁移。 |
| 10 | **CI/CD 流水线集成** | 原生对接 Jenkins、GitLab CI、ArgoCD，支持 GitOps 模式，实现从代码提交到生产部署的自动化。 |
| 11 | **成本分析与优化** | 按命名空间、标签、应用维度展示资源消耗与费用，提供降本建议（如预留实例推荐）。 |
| 12 | **混合云统一纳管** | 支持接入 AWS EKS、Azure AKS、阿里云 ACK 等公有云集群，实现统一监控与运维。 |
| 13 | **密钥与证书管理** | 集成 HashiCorp Vault，支持动态密钥生成、自动轮换与证书生命周期管理。 |
| 14 | **服务网格 (Service Mesh)** | 基于 Istio 1.20，提供流量管理、熔断、灰度发布与可观测性（Jaeger + Kiali）。 |
| 15 | **灾难恢复 (DR)** | 支持跨数据中心的主备切换，RPO ≤ 5 分钟，RTO ≤ 30 分钟，自动故障转移。 |

---

## 3. 系统要求

### 3.1 服务器要求

| 组件 | 最低配置 | 推荐配置 | 说明 |
|------|----------|----------|------|
| **管理节点 (Master)** | 4 vCPU / 16 GB RAM / 100 GB SSD | 8 vCPU / 32 GB RAM / 500 GB SSD | 至少 3 节点实现高可用 |
| **计算节点 (Worker)** | 8 vCPU / 32 GB RAM / 200 GB SSD | 16 vCPU / 64 GB RAM / 1 TB NVMe | 支持 GPU 节点（NVIDIA A100/H100） |
| **存储节点 (Storage)** | 8 vCPU / 64 GB RAM / 4 TB HDD | 16 vCPU / 128 GB RAM / 10 TB NVMe | 建议使用 RAID 10 或 Ceph 副本 |
| **GPU 节点** | 1× NVIDIA A100 / 16 vCPU / 64 GB RAM | 4× NVIDIA H100 / 32 vCPU / 256 GB RAM | 需安装 NVIDIA 驱动 535+ 及 CUDA 12.0+ |

**操作系统**：Ubuntu 22.04 LTS / Rocky Linux 9.2 / CentOS 7.9（内核 ≥ 5.10）  
**容器运行时**：containerd 1.7+ / Docker 24.0+  
**Kubernetes 版本**：v1.28 ~ v1.30

### 3.2 客户端要求

| 客户端类型 | 支持浏览器/工具 | 最低版本 | 备注 |
|------------|----------------|----------|------|
| **Web 控制台** | Chrome / Edge / Firefox | Chrome 115+ / Edge 115+ / Firefox 115+ | 需启用 JavaScript 与 WebSocket |
| **CLI 工具** | acmectl (AcmeCloud CLI) | v3.2.0 | 支持 Linux/macOS/Windows (WSL) |
| **API 客户端** | curl / Postman / Python | curl 7.68+ / Python 3.8+ | 需配置 Bearer Token |

### 3.3 网络要求

| 网络类型 | 要求 | 端口范围 | 说明 |
|----------|------|----------|------|
| **管理网络** | 1 Gbps 以上，低延迟 (< 2ms) | TCP 6443 (K8s API), 2379-2380 (etcd), 10250 (kubelet) | 节点间通信 |
| **数据网络** | 10 Gbps 以上，建议 25 Gbps | TCP 30000-32767 (NodePort), 80/443 (Ingress) | 应用流量 |
| **存储网络** | 10 Gbps 以上，独立 VLAN | TCP 6789 (Ceph), 3260 (iSCSI) | 存储后端通信 |
| **公网访问** | 固定公网 IP 或负载均衡器 | TCP 443 (HTTPS), 22 (SSH 管理) | 外部访问 |

**防火墙规则**：需开放以下端口：
- 入站：443 (HTTPS), 6443 (K8s API), 22 (SSH)
- 出站：80 (HTTP 更新), 443 (HTTPS 镜像仓库)

---

## 4. 部署架构

### 4.1 单机部署（开发/测试环境）

适用于功能验证、开发测试场景，所有组件部署于单台物理机或虚拟机。

```
+----------------------------------------+
|          AcmeCloud 单机节点             |
|  +----------------------------------+  |
|  |  Master + Worker + Storage 合一  |  |
|  |  - kube-apiserver                |  |
|  |  - etcd (单实例)                 |  |
|  |  - kube-scheduler                |  |
|  |  - kube-controller-manager       |  |
|  |  - containerd                    |  |
|  |  - Ceph (单 OSD)                 |  |
|  +----------------------------------+  |
|  |  AcmeConsole (Web UI)            |  |
|  |  acmectl (CLI)                   |  |
|  +----------------------------------+  |
+----------------------------------------+
```

**规格要求**：16 vCPU / 64 GB RAM / 1 TB SSD  
**适用场景**：功能测试、POC 验证、培训环境  
**限制**：不支持高可用、不支持 GPU 池化、最大节点数 1

### 4.2 集群部署（生产环境）

适用于生产环境，支持高可用与水平扩展。推荐最小 3 管理节点 + 3 计算节点 + 3 存储节点。

```
+-------------------+     +-------------------+     +-------------------+
|  管理节点 1 (M1)  |     |  管理节点 2 (M2)  |     |  管理节点 3 (M3)  |
| - kube-apiserver  |     | - kube-apiserver  |     | - kube-apiserver  |
| - etcd (member)   |     | - etcd (member)   |     | - etcd (member)   |
| - scheduler       |     | - scheduler       |     | - scheduler       |
| - controller-mgr  |     | - controller-mgr  |     | - controller-mgr  |
+--------+----------+     +--------+----------+     +--------+----------+
         |                         |                         |
         +-------------------------+-------------------------+
                                  |
                    +-------------+-------------+
                    |                           |
         +---------+---------+       +---------+---------+
         |  计算节点池 (W1-WN) |       |  存储节点池 (S1-SN) |
         | - kubelet          |       | - Ceph OSD         |
         | - kube-proxy       |       | - Longhorn         |
         | - GPU 驱动         |       | - NFS-Ganesha      |
         +-------------------+       +-------------------+
                    |                           |
                    +-------------+-------------+
                                  |
                     +-----------+-----------+
                     |   负载均衡器 (LB)      |
                     | - HAProxy / Nginx     |
                     +-----------+-----------+
                                 |
                     +-----------+-----------+
                     |   AcmeConsole (Web)   |
                     |   API Gateway         |
                     +-----------------------+
```

**规格要求**：
- 管理节点：3 台，8 vCPU / 32 GB RAM / 500 GB SSD
- 计算节点：≥ 3 台，16 vCPU / 64 GB RAM / 1 TB NVMe
- 存储节点：≥ 3 台，16 vCPU / 128 GB RAM / 10 TB NVMe

**高可用特性**：
- etcd 集群：3 节点，容忍 1 节点故障
- kube-apiserver：负载均衡器分发，无状态
- 存储：Ceph 三副本，容忍 1 副本故障
- 网络：BGP 动态路由 + VIP 漂移

**扩展能力**：
- 计算节点：支持在线添加，最大 10,000 节点
- 存储节点：支持在线扩容，最大 100 PB
- GPU 节点：支持热插拔，最大 1,024 张 GPU

---

## 5. API 接口说明

以下为 5 个关键 RESTful API 接口，所有接口需携带 `Authorization: Bearer <token>` 请求头。基础 URL：`https://api.acmecloud.com/v3.2`

### 5.1 创建集群

- **端点**：`POST /clusters`
- **描述**：创建一个新的 Kubernetes 集群
- **请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| name | string | 是 | 集群名称，长度 3-63 字符，小写字母、数字、连字符 |
| region | string | 是 | 地域代码，如 `cn-beijing`、`us-east-1` |
| version | string | 否 | Kubernetes 版本，默认 `1.30.0` |
| node_pools | array | 是 | 节点池配置列表 |
| network | object | 否 | 网络配置，默认使用 VPC-CNI |

- **请求示例**：
```json
{
  "name": "prod-cluster-01",
  "region": "cn-beijing",
  "version": "1.30.0",
  "node_pools": [
    {
      "name": "worker-pool-1",
      "node_count": 3,
      "instance_type": "acme.c8m32",
      "disk_size_gb": 200
    }
  ],
  "network": {
    "cidr": "10.100.0.0/16",
    "service_cidr": "10.200.0.0/16"
  }
}
```

- **返回值**：
```json
{
  "cluster_id": "cls-abc123def456",
  "status": "creating",
  "created_at": "2025-07-17T10:30:00Z",
  "api_server_endpoint": "https://prod-cluster-01.api.acmecloud.com:6443"
}
```

### 5.2 部署应用

- **端点**：`POST /clusters/{cluster_id}/applications`
- **描述**：在指定集群上部署 Helm Chart 应用
- **请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| cluster_id | string | 路径参数 | 集群 ID |
| name | string | 是 | 应用名称 |
| chart_name | string | 是 | Chart 名称，如 `nginx-ingress` |
| chart_version | string | 否 | Chart 版本，默认最新 |
| namespace | string | 否 | 命名空间，默认 `default` |
| values | object | 否 | 自定义 values 配置 |

- **请求示例**：
```json
{
  "name": "my-nginx",
  "chart_name": "nginx",
  "chart_version": "15.0.0",
  "namespace": "web",
  "values": {
    "replicaCount": 3,
    "service.type": "ClusterIP"
  }
}
```

- **返回值**：
```json
{
  "application_id": "app-xyz789uvw",
  "status": "deploying",
  "release_name": "my-nginx",
  "chart": "nginx-15.0.0"
}
```

### 5.3 查询节点状态

- **端点**：`GET /clusters/{cluster_id}/nodes`
- **描述**：获取集群中所有节点的状态信息
- **请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| cluster_id | string | 路径参数 | 集群 ID |
| status | string | 否 | 过滤状态，可选 `Ready`、`NotReady`、`Unknown` |
| page | integer | 否 | 页码，默认 1 |
| per_page | integer | 否 | 每页数量，默认 20，最大 100 |

- **返回值**：
```json
{
  "total": 5,
  "page": 1,
  "per_page": 20,
  "nodes": [
    {
      "name": "worker-01",
      "ip": "10.0.1.101",
      "status": "Ready",
      "kubelet_version": "v1.30.0",
      "cpu_cores": 16,
      "memory_gb": 64,
      "gpu_count": 1,
      "gpu_model": "NVIDIA A100",
      "created_at": "2025-07-15T08:00:00Z"
    }
  ]
}
```

### 5.4 获取审计日志

- **端点**：`GET /audit/logs`
- **描述**：查询操作审计日志，支持时间范围与过滤
- **请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| start_time | string | 是 | 开始时间，ISO 8601 格式，如 `2025-07-16T00:00:00Z` |
| end_time | string | 是 | 结束时间 |
| user | string | 否 | 按用户名过滤 |
| action | string | 否 | 按操作类型过滤，如 `create`、`delete` |
| resource_type | string | 否 | 资源类型，如 `cluster`、`application` |

- **返回值**：
```json
{
  "total": 150,
  "logs": [
    {
      "id": "log-001",
      "timestamp": "2025-07-17T09:15:30Z",
      "user": "admin@acmecloud.com",
      "action": "create",
      "resource_type": "cluster",
      "resource_id": "cls-abc123def456",
      "details": "Created cluster prod-cluster-01",
      "source_ip": "192.168.1.100"
    }
  ]
}
```

### 5.5 触发成本分析报告

- **端点**：`POST /cost/reports`
- **描述**：生成指定时间范围的成本分析报告，异步返回
- **请求参数**：

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| start_date | string | 是 | 开始日期，格式 `YYYY-MM-DD` |
| end_date | string | 是 | 结束日期 |
| granularity | string | 否 | 粒度，可选 `daily`、`weekly`、`monthly`，默认 `daily` |
| group_by | array | 否 | 分组维度，可选 `namespace`、`cluster`、`label` |

- **请求示例**：
```json
{
  "start_date": "2025-07-01",
  "end_date": "2025-07-15",
  "granularity": "daily",
  "group_by": ["namespace"]
}
```

- **返回值**：
```json
{
  "report_id": "rpt-456def789ghi",
  "status": "processing",
  "estimated_completion": "2025-07-17T10:05:00Z",
  "download_url": "https://api.acmecloud.com/v3.2/cost/reports/rpt-456def789ghi/download"
}
```

---

## 6. 定价方案

AcmeCloud 企业版 v3.2 提供三个版本，按管理节点数 + 计算节点数计费。所有价格单位为人民币（CNY），含 6% 增值税。

### 6.1 基础版 (Basic)

| 项目 | 价格 | 说明 |
|------|------|------|
| **管理节点** | ¥1,200/月/节点 | 最多 3 个管理节点 |
| **计算节点** | ¥800/月/节点 | 最多 20 个计算节点 |
| **存储节点** | ¥600/月/节点 | 最多 5 个存储节点 |
| **GPU 节点** | ¥2,500/月/GPU | 仅支持 NVIDIA A100 |
| **技术支持** | 5×8 工作日 | 工单响应时间 ≤ 4 小时 |

**功能限制**：
- 不支持多集群联邦管理
- 不支持 GPU 资源池化
- 日志保留 30 天
- 无 AI 异常预测功能

### 6.2 专业版 (Professional)

| 项目 | 价格 | 说明 |
|------|------|------|
| **管理节点** | ¥2,000/月/节点 | 最多 7 个管理节点 |
| **计算节点** | ¥1,200/月/节点 | 最多 200 个计算节点 |
| **存储节点** | ¥900/月/节点 | 最多 50 个存储节点 |
| **GPU 节点** | ¥4,000/月/GPU | 支持 A100 与 H100 |
| **技术支持** | 7×24 小时 | 工单响应时间 ≤ 1 小时 |

**功能差异**（相比基础版新增）：
- 支持多集群联邦管理（最多 5 个集群）
- 支持 GPU 资源池化（vGPU 模式）
- 日志保留 90 天
- 包含 AI 异常预测告警
- 支持 CI/CD 流水线集成

### 6.3 企业版 (Enterprise)

| 项目 | 价格 | 说明 |
|------|------|------|
| **管理节点** | ¥3,500/月/节点 | 无上限 |
| **计算节点** | ¥2,000/月/节点 | 无上限 |
| **存储节点** | ¥1,500/月/节点 | 无上限 |
| **GPU 节点** | ¥6,000/月/GPU | 支持所有 NVIDIA 数据中心 GPU |
| **技术支持** | 7×24 小时 + 专属 TAM | 工单响应时间 ≤ 15 分钟 |

**功能差异**（相比专业版新增）：
- 无限制多集群联邦管理
- 支持混合云统一纳管（AWS/Azure/阿里云）
- 日志保留 180 天（可定制）
- 包含灾难恢复 (DR) 功能
- 专属客户成功经理 (TAM)
- 每年 2 次现场巡检
- 定制化开发支持

### 6.4 附加服务

| 服务项目 | 价格 | 说明 |
|----------|------|------|
| **现场部署** | ¥50,000/次 | 工程师上门部署，含 3 天培训 |
| **定制开发** | ¥2,000/人天 | 按需开发插件或集成 |
| **安全审计** | ¥30,000/次 | 第三方渗透测试与合规审计 |
| **存储扩容** | ¥1,000/TB/月 | 超出套餐的存储空间 |

**计费示例**：  
某企业选择专业版，部署 3 管理节点 + 50 计算节点 + 10 存储节点 + 8 张 GPU：  
月费 = 3×¥2,000 + 50×¥1,200 + 10×¥900 + 8×¥4,000 = ¥6,000 + ¥60,000 + ¥9,000 + ¥32,000 = **¥107,000/月**

---

## 7. 常见问题 (FAQ)

### Q1: AcmeCloud 企业版 v3.2 与开源 Kubernetes 有何区别？

**A**: AcmeCloud 企业版在原生 Kubernetes 基础上提供了以下增值能力：
- **企业级管理控制台**：图形化界面，无需手动编辑 YAML 文件。
- **内置安全合规**：自动满足等保 2.0、SOC 2 要求，无需额外配置。
- **智能运维**：AI 异常预测、成本分析、自动扩缩容。
- **商业支持**：7×24 小时技术支持，SLA 保障 99.99%。
- **集成生态**：预装 200+ 企业级应用模板，一键部署。
开源 Kubernetes 需要自行集成监控、日志、安全等组件，运维成本较高。

### Q2: 如何从 v3.1 升级到 v3.2？是否影响现有业务？

**A**: 升级流程如下：
1. 登录 AcmeConsole，进入“系统设置” → “版本升级”。
2. 系统自动检测当前版本与目标版本差异，生成升级计划。
3. 支持滚动升级（Rolling Update），管理节点逐个升级，计算节点分批升级。
4. 升级期间，现有应用不受影响，API 服务持续可用。
5. 升级完成后，系统自动重启相关组件，预计耗时 30-60 分钟（取决于集群规模）。
**注意**：v3.2 引入了新的 etcd 存储格式，升级后不可回退至 v3.1。建议先在测试环境验证。

### Q3: 是否支持将现有自建 Kubernetes 集群迁移至 AcmeCloud？

**A**: 支持。AcmeCloud 提供迁移工具 `acmectl migrate`，支持以下场景：
- **同构迁移**：从原生 Kubernetes v1.28+ 迁移至 AcmeCloud，保留所有工作负载与配置。
- **异构迁移**：从 OpenShift、Rancher 等平台迁移，需手动调整部分资源定义。
- **数据迁移**：支持通过 Velero 迁移持久卷数据，支持跨集群快照恢复。
迁移步骤：
1. 在源集群安装 AcmeCloud Agent。
2. 在目标集群创建对应命名空间与资源配额。
3. 执行 `acmectl migrate start --source-context=old --target-context=new`。
4. 验证迁移结果后，切换 DNS 流量。
详细文档请参考：https://docs.acmecloud.com/enterprise/v3.2/migration

### Q4: 平台如何处理 GPU 资源分配？是否支持多用户共享 GPU？

**A**: AcmeCloud 企业版 v3.2 支持两种 GPU 共享模式：
- **vGPU 模式**：基于 NVIDIA vGPU 技术，将物理 GPU 切分为多个虚拟 GPU 实例，每个实例分配固定显存与计算资源。支持 MIG（Multi-Instance GPU）与标准 vGPU。
- **时间片共享模式**：多个 Pod 共享同一物理 GPU，通过时间片轮转调度，适合推理场景。
资源分配策略：
- 用户可通过 `spec.gpu.resources` 指定显存需求（如 `nvidia.com/gpu-memory: 8Gi`）。
- 管理员可在命名空间级别设置 GPU 配额（如 `limits.nvidia.com/gpu: 2`）。
- 调度器自动选择最优 GPU 节点，支持 GPU 亲和性与反亲和性。
**注意**：vGPU 模式需要 NVIDIA vGPU License Server，企业版已包含 10 个并发 License。

### Q5: 如果遇到平台故障，如何获取技术支持？SLA 如何保障？

**A**: 技术支持渠道：
- **工单系统**：登录 AcmeConsole → 右上角“帮助” → “提交工单”，支持附件上传。
- **电话支持**：400-888-ACME（仅专业版与企业版），7×24 小时。
- **专属 TAM**：企业版用户可联系专属客户成功经理。
SLA 保障条款：
- **可用性**：控制台与 API 服务可用性 ≥ 99.99%（按月度计算）。
- **故障响应**：P1 故障（核心功能不可用）15 分钟内响应，P2 故障（部分功能异常）1 小时内响应。
- **故障修复**：P1 故障 4 小时内修复，P2 故障 8 小时内修复。
- **赔偿**：若可用性低于 99.99%，按月度费用的 10% 赔偿；低于 99.9%，赔偿 30%。
详细 SLA 文档请参考：https://docs.acmecloud.com/enterprise/v3.2/sla

---

**文档结束**  
© 2025 AcmeCloud Inc. 保留所有权利。  
本文档仅供参考，实际功能与价格以官方最新公告为准。  
更新日期：2025-07-17 | 文档编号：AC-SPEC-ENT-3.2-20250717