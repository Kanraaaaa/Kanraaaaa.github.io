# ForgeKernel：仓库介绍与工作流程

> 调研日期：2026 年 11 月 3 日  
> 对象：[OpenBMB/ForgeKernel](https://github.com/OpenBMB/ForgeKernel)  
> 本文依据仓库当前 README、设计文档及核心源码整理。性能数字是项目方报告的结果，本文没有独立复现。

## 先用一句话理解

**ForgeKernel 是一套由 coding agent 驱动、通过 GPU 实测来迭代优化 kernel 的框架。**

它本身不等于大模型，也不是一个只靠提示词就能工作的 skill。ForgeKernel 负责把任务交给 agent、组织代码修改和 GPU 验证、记录实验结果，并据此决定继续、回退或重新规划；agent 负责分析和编写 kernel；GPU 则提供正确性与性能结果。

可以把它想象成自动化实验室：

| 角色 | 类比 | 实际工作 |
|---|---|---|
| 用户 | 提出实验目标的人 | 描述算子、输入范围、参考实现和目标硬件 |
| Teacher agent | 设计员 | 分析参考实现和硬件表现，规划优化步骤 |
| Student agent | 实验员/程序员 | 按步骤修改 kernel 代码 |
| ForgeKernel | 实验管理员 | 启动 agent、提交 GPU 作业、检查结果、记录和控制流程 |
| GPU 与分析工具 | 实验设备 | 实际运行候选 kernel，提供正确性、耗时和 profiling 数据 |

## 它由哪些部分组成？

### 1. `forge` 命令行与运行框架

ForgeKernel 是一个可安装的 Python 项目，安装后提供 `forge` 命令。用户通过它初始化任务、创建运行、查看状态、续跑、整理知识和导出结果。运行产物通常保存在 `.artifacts/<任务名>_<运行编号>/`。

框架负责把流程接起来：解析任务配置、调用 agent、提交 GPU 作业、读取判断结果、保存最佳实现和报告。也就是说，ForgeKernel 的主要价值是**管理优化实验的闭环**，而不是替代底层 GPU 编程工具链。

### 2. Agent：实际负责“想”和“写”

ForgeKernel 的流程里有两个逻辑角色：

- **Teacher（架构 agent）**：阅读任务说明、参考实现或硬件测量，生成 milestone 优化计划；当优化停滞或计划需要调整时，再介入诊断和修订。
- **Student（coding agent）**：根据 milestone 逐项实现代码改动。

这两个角色可以配置成不同模型，也可以使用同一模型。它们不是仓库里内置的大模型服务；当前主线的 agent 适配代码会启动外部 **Claude Code CLI**。项目中的 `skills/` 和提示词为 agent 提供工作规范和硬件知识，不能代替 agent 本身。

### 3. GPU 作业、正确性判断与性能分析

候选实现需要在目标 GPU 上运行。任务提供的 judge 检查结果是否正确；基准流程测量候选和参考实现的耗时；配置了 Nsight Compute 时还可以采集更细的性能指标。正确性失败的候选会被回退。

### 4. Milestone 与硬件知识库

- **Milestone** 是每个算子的优化课程，描述决策、参数和约束，不是参考 kernel 的代码副本。项目设计强调先确定结构性决策，再逐步调优。
- **硬件知识库**保存通过 GPU 探针验证的硬件机制，供后续算子任务复用。
- **自进化**指把一轮确认通过的最佳 kernel 作为下一轮参考，再要求新一轮继续超过它；当收益低于噪声阈值或没有确认的新最佳实现时，流程停止。

## 一次任务的大致流程

以仓库自带的 RMSNorm 示例为例：

```text
准备任务
  ├─ description.md：算子语义与合法输入
  ├─ shapes.json：要测试、优化的输入形状
  └─ task.toml：语言、GPU 架构、参考实现、目标、模型和预算
        ↓
forge new：检查配置并创建本次运行目录
        ↓
测量参考实现，建立本次比较基线
        ↓
Teacher 分析问题，生成 milestone 优化计划
        ↓
Student 按计划修改 kernel
        ↓
GPU 作业运行正确性检查、计时和可选 profiling
        ├─ 正确性失败：回退候选改动
        ├─ 正确且有收益：保留为当前最佳，继续下一步
        └─ 多轮停滞或遇到规划问题：Teacher 重新诊断/修订计划
        ↓
最终确认最佳版本，生成报告并导出 kernel
        ↓
可选：将最佳版本作为下一代参考，继续自进化
```

这里的关键点是：**agent 提出的代码不自动算成功，是否接受要看 GPU 上的验证结果。**流程也不是一次性“生成最优代码”，而是重复执行“规划/改代码 → 实测 → 根据证据调整”。

## 用户需要准备什么？

创建任务时通常需要：

1. **算子说明**：输入输出、数学语义、数据类型和合法输入范围。
2. **测试形状与输入**：哪些 workload 代表目标使用场景。
3. **参考实现**：可以是能运行的源码，也可以限制为黑盒测量；项目说明有参考实现时通常更容易优化。
4. **运行环境**：ForgeKernel 所在的 Linux/macOS 环境、Python、Git、Claude Code CLI，以及本机或 SSH 可访问的 GPU 环境和相应工具链。
5. **预算与模型配置**：优化时间、目标提升、Teacher/Student 使用的模型和服务端点。

仓库的快速开始示例以 NVIDIA Hopper（H100，`sm90`）和 Blackwell（B200，`sm100`）为目标；常见实现语言是 CuTe DSL 或 CUDA C++。完整依赖还取决于具体任务。

## 它和 skill 的区别

| | ForgeKernel | Skill |
|---|---|---|
| 本质 | 可安装运行的 Python 框架与实验流程 | agent 使用的任务说明和工具脚本 |
| 主要职责 | 调度 agent 与 GPU 验证，管理运行状态和结果 | 指导 agent 如何完成特定工作 |
| 能否单独完成优化 | 不能，仍需要 agent 和 GPU 环境 | 不能，通常还需要 agent、框架或相应工具 |

ForgeKernel 仓库里包含 skills，但它不仅仅是 skills。更贴切的说法是：**ForgeKernel 是实验平台；agent 是使用平台设计和实现优化的参与者；skill 是给 agent 的操作手册和辅助工具。**

## 结果与实际边界

仓库 README 报告了在 Hopper 和 Blackwell 上对多个算子的实验结果，并公开了相应 kernel。它还报告了 RMSNorm 示例在 B200 上约 1.5 小时达到约 5.2 倍于 PyTorch 参考实现的速度。**这些是仓库方公布的数据，具体结果依赖 workload、参考实现、软件版本和 GPU；本文未独立复现，也不能据此推断任意任务都能获得相同加速。**

项目自己列出的重要限制包括：

- 有可运行的参考实现时效果通常更好；从零写出第一版实现并非它最有把握的场景。
- 自进化停止表示当前流程在给定预算和噪声判断下没有找到足够收益，不是数学意义上的全局最优证明。
- 覆盖范围有限，不能把针对特定 GPU 与算子的结果直接外推到其他架构和任务。
- 一次运行可能消耗数小时 GPU 时间和较多模型调用。
- README 的动态栏提到 CANN/昇腾榜单成绩，但快速开始、任务配置和主线代码文档主要描述 NVIDIA、CUDA 与 CuTe DSL。仅凭榜单动态无法确认当前 `forge run` 已具备通用昇腾后端；若目标是昇腾，应先单独核实对应代码路径和复现步骤。

## 适合怎样理解它？

如果只记一件事，可以记住这个闭环：

> **人定义任务，Teacher 规划，Student 写 kernel，ForgeKernel 组织实验，GPU 验证结果；验证结果再决定下一轮怎么做。**

因此 ForgeKernel 不是“一个专门生成 kernel 的模型”，而是一个围绕 agent 和 GPU 实测构建的**自动化 kernel 优化流程框架**。

## 资料来源

- [ForgeKernel 仓库](https://github.com/OpenBMB/ForgeKernel)
- [中文 README：快速开始、工作原理、任务配置与限制](https://github.com/OpenBMB/ForgeKernel/blob/main/README_zh.md)
- [运行循环源码](https://github.com/OpenBMB/ForgeKernel/blob/main/src/forgekernel/loop/driver.py)
- [Agent 调用适配器](https://github.com/OpenBMB/ForgeKernel/blob/main/src/forgekernel/agents.py)
- [启动与运行设计文档](https://github.com/OpenBMB/ForgeKernel/blob/main/docs/design/v1-launch.md)
- [Milestone 蒸馏设计文档](https://github.com/OpenBMB/ForgeKernel/blob/main/docs/design/milestone-distillation.md)
- [Skills 目录说明](https://github.com/OpenBMB/ForgeKernel/blob/main/skills/README.md)
- [项目关联论文 JustGoal（用于了解项目论文动态，不等同于 ForgeKernel 全部性能结果）](https://arxiv.org/abs/2610.36434)
