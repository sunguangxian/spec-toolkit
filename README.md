# spec-toolkit

`spec-toolkit` 是协议规格仓库的公共工具库，用于服务多个规格数据仓库，例如：

- `AT-Spec`：AT 指令规格数据仓库
- `CPS-Spec`：写频 / CPS / 二进制结构体协议规格数据仓库
- 后续可扩展：`Upgrade-Spec`、`RSC-Spec`、`Calibration-Spec` 等

## 当前结构

```text
spec-toolkit/
├─ scripts/             # 通用命令入口和 Python 工具实现
├─ scripts/atspec/      # AT-Spec 适配器与共享逻辑
├─ schemas/             # JSON schema
├─ templates/           # Markdown / HTML / CSS 模板
└─ docs/                # 工具库说明（后续扩展）
```

工具库只维护“怎么校验、怎么生成、怎么发布”，不维护具体产品协议数据。

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

## 作为 submodule 使用

推荐在规格数据仓库中挂载到：

```text
tools/spec-toolkit
```

例如：

```powershell
git submodule add ../spec-toolkit tools/spec-toolkit
git submodule update --init --recursive
```

AT-Spec 为了兼容旧命令，保留 `scripts/*.py` 作为轻量入口。真实实现位于：

```text
tools/spec-toolkit/scripts/
```

因此旧命令仍然可用：

```powershell
python scripts/validate_all.py
python scripts/build_doc.py --model dp5x --format html
```

也可以直接调用工具库脚本：

```powershell
python tools/spec-toolkit/scripts/validate_all.py
python tools/spec-toolkit/scripts/build_doc.py --model dp5x --format html
```

## 路径约定

- `SPEC_ROOT` 环境变量可显式指定规格数据仓库根目录。
- 未设置 `SPEC_ROOT` 时，工具默认使用当前工作目录作为规格数据仓库根目录。
- `schemas/` 和 `templates/` 从 `spec-toolkit` 读取。
- `commands/`、`profiles/`、`models/`、`output/`、`releases/` 从调用方规格仓库读取或写入。

日常建议在规格数据仓库根目录执行命令。
