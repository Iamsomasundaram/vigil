"""
Sidebar navigation and guide links for the Vigil learning UI.

Pure data (no Streamlit import) so a test can check it against the page registry and the guide
pages. The groups mirror the sections of the learning guide in docs/.

NAV_GROUPS:  group -> {label: page key}
GUIDE_PAGES: page key -> guide page slug (docs/src/<slug>.md), shown as a "read the guide" link
GUIDE_LINKS: guide pages worth linking directly from the sidebar
"""

NAV_GROUPS: dict[str, dict[str, str]] = {
    "1) Start": {
        "🏠 Home":                      "home",
        "📖 Glossary":                  "glossary",
        "📋 Prod Readiness":            "checklist",
    },
    "2) Levels": {
        "L0 — Single LLM Call":         "l0",
        "L1 — Prompt Chain":            "l1",
        "L2 — Parallel Fan-out":        "l2",
        "L3 — Conditional Routing":     "l3",
        "L4 — Tool Use":                "l4",
        "L4b — Multimodal":             "l4b",
        "L5 — Memory & Feedback":       "l5",
        "L6 — Autonomous Monitor":      "l6",
    },
    "3) Architectures": {
        "A1 — ReAct":                   "a1",
        "A2 — Plan-and-Execute":        "a2",
        "A3 — Reflection":              "a3",
        "A4 — Multi-Agent":             "a4",
    },
    "4) Reliability": {
        "R1 — Guardrails":              "r1",
        "R2 — Evaluation":              "r2",
        "R3 — Observability":           "r3",
        "R4 — Resilience":              "r4",
        "R5 — Cost Control":            "r5",
        "R6 — Drift Monitoring (F17)":  "f17",
        "R7 — Action Governance (F18)": "f18",
        "R8 — Supply Chain (F19)":      "f19",
        "R9 — Release Safety (F20)":    "f20",
    },
    "5) Foundations": {
        "F4 — Tokenization":            "f4",
        "F6 — Prompt Techniques":       "f6",
        "F8 — Tool Discovery & MCP":    "f8",
        "F11 — Retrieval Quality":      "f11",
        "F12 — Retrieval Metrics":      "f12",
        "F13 — Factuality":             "f13",
        "F14 — Prompt Lifecycle":       "f14",
        "F15 — Privacy":                "f15",
        "F16 — Hybrid Retrieval":       "f16",
        "F21 — Fine-tune Advisor":      "f21",
        "F22 — Claude Model Select":    "f22",
        "F23 — Responsible AI":         "f23",
        "F24 — Semantic Cache":         "f24",
    },
    "6) Extensions": {
        "E1 — Semantic Memory":         "e1",
        "E2 — Human-in-the-Loop":       "e2",
        "E3 — Agent Communication":     "e3",
        "E4 — Inference Layer":         "e4",
    },
    "7) Themes": {
        "T1 — Incident Response Ops":   "t1_incident",
    },
    "8) Projects": {
        "P1 — Autonomous Tester":       "p1",
    },
}

GUIDE_PAGES: dict[str, str | None] = {
    "home": "index",
    "glossary": "glossary",
    "checklist": "reliability",
    "l0": "l0", "l1": "l1", "l2": "l2", "l3": "l3", "l4": "l4", "l4b": "l4b", "l5": "l5", "l6": "l6",
    "a1": "a1", "a2": "a2", "a3": "a3", "a4": "a4",
    "r1": "r1", "r2": "r2", "r3": "r3", "r4": "r4", "r5": "r5",
    "f17": "r6", "f18": "r7", "f19": "r8", "f20": "r9",
    "f4": "tokenization",
    "f6": "prompting",
    "f8": "l4",
    "f11": "retrieval", "f12": "retrieval", "f16": "retrieval",
    "f13": "factuality",
    "f14": "prompt-lifecycle",
    "f15": "privacy",
    "f21": "finetuning",
    "f22": "model-selection",
    "f23": "responsible-ai",
    "f24": "semantic-cache",
    "e1": "l5", "e2": "a2", "e3": "a4", "e4": "model-selection",
    "t1_incident": "incident-ops",
    "p1": None,  # the guide's Projects section arrives with P1.5
}

# Guide pages with no UI page of their own, linked straight from the sidebar.
GUIDE_LINKS: list[tuple[str, str]] = [
    ("Guide home", "index"),
    ("Getting started", "getting-started"),
    ("How LLMs work", "concepts"),
    ("Learning path", "learning-path"),
    ("Glossary", "glossary"),
    ("API security defaults", "security"),
]


def all_page_keys() -> list[str]:
    return [key for group in NAV_GROUPS.values() for key in group.values()]
