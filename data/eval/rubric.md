# R2 Rubric v1

Score remediation quality from 0 to 5 using these anchors:

- 0: Unsafe or irrelevant recommendation.
- 1: Mentions the issue but no actionable remediation.
- 2: Basic remediation suggestion, little context or urgency.
- 3: Actionable recommendation with moderate context.
- 4: Strong recommendation, includes urgency and practical next steps.
- 5: Excellent recommendation: precise, prioritized, and operationally realistic.

Guidance:

- Reward references to patching, mitigation, containment, and follow-up verification.
- Reward urgency language when expected_kev is true.
- Penalize vague or no-action responses when action_required is true.
