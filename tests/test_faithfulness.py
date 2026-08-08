import asyncio

from evals.faithfulness import check_faithfulness


def test_check_faithfulness_returns_fallback_score():
    score = asyncio.run(
        check_faithfulness(
            "What treatment is recommended for hypertension?",
            ["Hypertension is treated with lifestyle changes and medication."],
            "The recommended treatment is lifestyle changes and medication.",
        )
    )

    assert 0.0 <= score <= 1.0
