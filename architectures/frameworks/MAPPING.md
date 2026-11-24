# Vigil Hand-Rolled Patterns → Framework Mapping (F7)

| Vigil concept                      | LangGraph concept    | Notes                           |
| ---------------------------------- | -------------------- | ------------------------------- |
| Python function that mutates state | Graph node           | Node returns updated state dict |
| if/else routing in loop            | Conditional edge     | Edge function chooses next node |
| `messages` list                    | Graph state field    | Passed across nodes each step   |
| `max_iterations` guard             | `recursion_limit`    | Prevents runaway loops          |
| tool dispatch function             | tool node / callable | Can be in-graph or external     |

## Other framework analogies

- CrewAI: specialist agents + manager map well to A4 multi-agent flows.
- LlamaIndex: retrieval orchestration maps to L5 memory + semantic recall.
- OpenAI Agents SDK: tool schema + run loop maps to L4 tool-use loops.
