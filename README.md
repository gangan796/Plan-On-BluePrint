# PoBL：最简 PoG 流程框架（Ollama + Wikidata）

这是一个**最小可运行**的 PoG-like 流程骨架，用于复现 PoG 的关键思想：

- **Plan（规划）**：LLM 将问题拆成子目标（subobjectives）
- **on Graph（图探索）**：从知识图谱枚举候选谓词 → LLM 选关系 → SPARQL 扩展一跳三元组 → LLM 剪枝实体
- **Reason（推理）**：LLM 基于收集到的三元组给出答案，并判断信息是否充分（Sufficient）

本实现按你的要求做了两点改动：

- **LLM 调用**：改为调用本地 Ollama（HTTP API），并且 **预留模型选择空档**（通过 `--ollama_model` 传入）。本项目不负责安装 Ollama。
- **知识图谱**：不使用 Freebase，改为请求 **Wikidata SPARQL**：`https://query.wikidata.org/sparql`（公共端点）。

> Wikidata SPARQL 控制台可在 [Wikidata Query Service](https://query.wikidata.org/) 直接测试查询。

---

## 目录结构

- `main.py`：主入口，串起「子目标→关系选择→一跳扩展→实体剪枝→最终推理」
- `llm_ollama.py`：Ollama 客户端（`/api/generate`）
- `wikidata.py`：Wikidata SPARQL 封装（列谓词、扩展一跳）
- `prompts.py`：最小 prompt 集合
- `utils.py`：解析 LLM 输出（列表/JSON）的工具

---

## 安装依赖

```bash
pip install -r PoBL/requirements.txt
```

---

## 运行示例

1) 确保你的本机已经启动了 Ollama 服务（默认 `http://localhost:11434`），并且该服务能访问到你指定的模型。

2) 运行（建议手动指定 topic entity，避免最小版 entity linking 失败）：

```bash
python PoBL/main.py ^
  --question "What is the currency used in Kenya?" ^
  --topic "Kenya" ^
  --ollama_model "<在这里填你的模型名>" ^
  --depth 2
```

输出会是一个 JSON，其中包含：

- `subobjectives`：子目标列表
- `topic_entity`：选择的 Wikidata 实体（QID + label）
- `knowledge`：检索到的三元组（简化表示）
- `llm`：最终推理的原始输出
- `parsed`：如果能解析出 JSON，会放这里

---

## 重要说明（“最简单”意味着的取舍）

- 这是**流程框架骨架**：目前只对 frontier 的第一个节点做一跳扩展，并不完整实现 PoG 的多实体、多分支、多跳自校正搜索。
- 若要更接近论文版 PoG，你可以在此基础上增加：
  - 多 frontier 实体并行扩展
  - 对 object label 反查 QID、把 object 作为下一层 topic entity（多跳）
  - 记忆 `mem` 的持续更新与自校正（reverse / add entity）闭环
  - 更强的 entity linking（NER + 候选召回 + 排序）

