SUBOBJECTIVE_PROMPT = """请把回答问题的过程拆成尽可能少的子目标（subobjectives），只输出 Python 列表形式，不要输出任何解释。
示例：
Q: Which of the countries in the Caribbean has the smallest country calling code?
Output: ['Search the countries in the Caribbean', 'Search the country calling code for each Caribbean country', 'Compare the country calling codes to find the smallest one']

Q: {question}
Output:
"""


RELATION_SELECT_PROMPT = """你将看到一个问题、子目标、一个主题实体（topic entity），以及从知识图谱中枚举出的候选谓词（predicate / property）。
请只选择**最少数量**且**高度相关**的谓词，输出为 Python 列表形式（例如 ['wdt:P31','wdt:P17']），不要输出任何解释。

Q: {question}
Subobjectives: {subobjectives}
Topic Entity: {topic_entity_label} ({topic_entity_id})
Candidate Predicates: {predicates}
Output:
"""


ENTITY_PRUNE_PROMPT = """下面给出若干三元组（subject, predicate, object），其中 object 是候选实体列表。
请从候选实体中选择**最少数量**且**最相关**、能够推进回答 Q 的实体，输出为 Python 列表（实体的 label），不要输出任何解释。

Q: {question}
Triples:
{triples}
Output:
"""


REASONING_PROMPT = """你将得到问题、已经检索到的一些知识三元组。请输出 JSON，必须包含字段：
- "A": {{"Sufficient": "Yes/No", "Answer": "..."}}
- "R": "你的简短推理"

规则：
- 如果三元组不足以回答，Sufficient=No 且 Answer="Null"
- 如果可以回答，Sufficient=Yes 且给出最简答案（字符串或列表字符串均可）

Q: {question}
Knowledge Triples:
{knowledge}
Output (JSON):
"""

