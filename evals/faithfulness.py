import os
import re
from typing import List

from dotenv import load_dotenv

load_dotenv()

try:
    from langchain_aws import ChatBedrockConverse
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness
    from ragas.dataset_schema import SingleTurnSample
except Exception:  # pragma: no cover - optional dependency fallback
    ChatBedrockConverse = None
    LangchainLLMWrapper = None
    Faithfulness = None
    SingleTurnSample = None

# Judge is a SEPARATE model from the agent (self-judging inflates scores).
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")
JUDGE_MODEL_ID = os.getenv("JUDGE_MODEL_ID", "anthropic.claude-sonnet-4-6")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

if ChatBedrockConverse is not None and LangchainLLMWrapper is not None and Faithfulness is not None and SingleTurnSample is not None:
    _judge_llm = ChatBedrockConverse(model=JUDGE_MODEL_ID, region_name=BEDROCK_REGION, temperature=0)
    _evaluator_llm = LangchainLLMWrapper(_judge_llm)
    _faithfulness = Faithfulness(llm=_evaluator_llm)
else:
    _faithfulness = None


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _heuristic_faithfulness(retrieved_chunks: List[str], answer: str) -> float:
    if not retrieved_chunks or not answer:
        return 0.0

    answer_tokens = set(_tokenize(answer))
    if not answer_tokens:
        return 0.0

    chunk_text = " ".join(retrieved_chunks)
    chunk_tokens = set(_tokenize(chunk_text))
    if not chunk_tokens:
        return 0.0

    overlap = len(answer_tokens & chunk_tokens) / len(answer_tokens)
    return round(min(1.0, max(0.0, overlap)), 3)


async def check_faithfulness(user_query: str, retrieved_chunks: list[str], answer: str) -> float:
    """0.0-1.0: fraction of claims in `answer` actually supported by `retrieved_chunks`."""
    if _faithfulness is None:
        return _heuristic_faithfulness(retrieved_chunks, answer)

    sample = SingleTurnSample(
        user_input=user_query,
        retrieved_contexts=retrieved_chunks,
        response=answer,
    )
    return await _faithfulness.single_turn_ascore(sample)