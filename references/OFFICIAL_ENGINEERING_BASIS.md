# 提示词工程依据

本包的提示词结构依据以下官方 Codex 文档设计（请在执行时重新核验最新内容）：

1. OpenAI Codex Best practices  
   https://developers.openai.com/codex/learn/best-practices
2. Custom instructions with AGENTS.md  
   https://developers.openai.com/codex/guides/agents-md
3. Codex Prompting  
   https://developers.openai.com/codex/prompting
4. Iterate on difficult problems  
   https://developers.openai.com/codex/use-cases/iterate-on-difficult-problems
5. Agent Skills  
   https://developers.openai.com/codex/skills
6. Analyze datasets and ship reports  
   https://developers.openai.com/codex/use-cases/datasets-and-reports

设计对应关系：

- `AGENTS.md` 只放长期、稳定、可自动加载的规则；
- 大任务拆成六个阶段，每阶段有确定性检查；
- 明确 Goal/Context/Constraints/Done when；
- 使用评分、停止规则和迭代日志；
- 技能按阶段择优，而非强制堆叠；
- 最终要求可测试、可复现、可审阅的产物。
