# spec-toolkit

`spec-toolkit` 是协议规格仓库的公共工具库，用于服务多个规格数据仓库，例如：

- `AT-Spec`：AT 指令规格数据仓库
- `CPS-Spec`：写频 / CPS / 二进制结构体协议规格数据仓库
- 后续可扩展：`Upgrade-Spec`、`RSC-Spec`、`Calibration-Spec` 等

## 设计目标

公共工具库只维护“怎么校验、怎么生成、怎么发布”，不维护具体产品协议数据。

建议职责边界：

```text
spec-toolkit/
├─ spec_toolkit/        # Python 公共库
├─ schemas/             # 通用 schema 或 schema 基类
├─ templates/           # 通用模板基类
├─ scripts/             # 通用命令入口
└─ docs/                # 工具库说明
```

具体协议数据继续放在各自仓库：

```text
AT-Spec/
├─ commands/
├─ profiles/
├─ models/
└─ raw/

CPS-Spec/
├─ messages/
├─ structs/
├─ profiles/
├─ models/
└─ raw/
```

## 推荐迁移步骤

### 第 1 阶段：兼容拆分

- `AT-Spec` 仍保留原有 `scripts/`、`templates/`、`schemas/`，保证现有发布流程可用。
- `spec-toolkit` 先建立公共库结构。
- 新增功能优先放到 `spec-toolkit`，旧功能逐步迁移。

### 第 2 阶段：抽公共能力

优先迁移这些通用能力：

- YAML 加载与合并
- profile/model 组合逻辑
- variant 选择逻辑
- Markdown/HTML/PDF 生成框架
- release 校验
- 版本差异报告
- 机器可读 catalog 输出

### 第 3 阶段：协议插件化

不同协议通过 plugin / adapter 接入：

```text
AT adapter  -> commands / profiles / models
CPS adapter -> messages / structs / profiles / models
```

这样 `AT-Spec` 和 `CPS-Spec` 可以共用同一套生成、校验、发布流程。