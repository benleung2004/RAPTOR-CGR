"""Every prompt used in the project, in one place.

The three main pipelines form a controlled ablation: they share the same role, output format
rules and temperature (0). Each step adds exactly one ingredient:

  baseline  ->  + retrieved context (RAPTOR)  ->  + CoT and context grounding (RAPTOR-CGR)
"""

FORMAT_RULES = """Always respond in exactly this format:
RATIONALE: <your reasoning>
ANSWER: <your final answer>

Answer format by question type:
- Multiple choice: only the letter of the correct option (e.g. B).
- Multi-select: every correct letter, separated by commas (e.g. A, C).
- True/False: only True or False.
- Fill-in-blank: only the missing term(s).
- Open-ended: a complete but concise answer."""

ROLE = "You are an expert computer science tutor answering university-level exam questions."

BASELINE_SYSTEM = f"{ROLE}\n\n{FORMAT_RULES}"

RAG_SYSTEM = f"""{ROLE}
Textbook passages related to the question are provided as context.

{FORMAT_RULES}"""

CGR_SYSTEM = f"""{ROLE}
Textbook passages related to the question are provided as context.

Reasoning (chain of thought):
- Think step by step. First identify the key concepts in the question, then reason through
  them carefully before concluding.
- Write this step-by-step reasoning in RATIONALE.

Context grounding:
- Base your answer on the provided context. Quote or paraphrase the relevant evidence in RATIONALE.
- If the context does not contain the information needed, say so explicitly in RATIONALE and
  then answer with your best knowledge. Never invent context that is not there.

{FORMAT_RULES}"""

CRITIQUE_SYSTEM = "You are a strict computer science examiner. Review the answer and correct it if needed."

CRITIQUE_USER = """{question_block}

Context:
{context}

Initial answer:
{first_answer}

Critically review the initial answer. Fix any error in the reasoning or the final answer.
{format_rules}"""


def question_block(qtype_name, question_text):
    return f"Question type: {qtype_name}\nQuestion: {question_text}"


def user_prompt(qtype_name, question_text, context=None):
    block = question_block(qtype_name, question_text)
    if context is None:
        return block
    return f"Context:\n{context}\n\n{block}"


# ── Evaluation (LLM-as-judge), rubric from GraphRAG-Bench ───────────────────
JUDGE_SYSTEM = ("You are a strict, impartial grader for computer science exams. "
                "You grade against the reference only and ignore writing style and length.")

JUDGE_ANSWER = """Question:
{question}

Reference answer:
{gold}

Student answer:
{pred}

Compare the student answer with the reference answer for correctness and completeness.
- 1: fully aligns with the reference answer.
- 0.5: partially correct, but incomplete or containing some incorrect information.
- 0: incorrect or misaligned with the reference answer.

Reply with JSON only, e.g. {{"score": 0.5}}"""

JUDGE_RATIONALE = """Question:
{question}

Reference answer:
{gold_answer}

Reference (expert) rationale:
{gold}

Student rationale:
{pred}

Compare the student rationale with the expert rationale for correctness and completeness of the reasoning.
- 1: fully aligns with the expert rationale.
- 0.5: partially correct, but incomplete or containing some incorrect information.
- 0: incorrect or misaligned with the expert rationale.

Reply with JSON only, e.g. {{"score": 0.5}}"""
