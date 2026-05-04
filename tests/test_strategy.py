from raatverse_agent.pipeline.models import CategoryScoreState
from raatverse_agent.services.mock import MockStrategyAgent


def test_strategy_prefers_underused_category_before_high_score():
    strategy = MockStrategyAgent()

    category = strategy.choose_category(
        ["horror", "mystery"],
        [
            CategoryScoreState(category="horror", score=100.0, uploads=3),
            CategoryScoreState(category="mystery", score=1.0, uploads=0),
        ],
    )

    assert category == "mystery"


def test_strategy_uses_score_when_upload_counts_are_equal():
    strategy = MockStrategyAgent()

    category = strategy.choose_category(
        ["horror", "mystery"],
        [
            CategoryScoreState(category="horror", score=10.0, uploads=1),
            CategoryScoreState(category="mystery", score=20.0, uploads=1),
        ],
    )

    assert category == "mystery"


def test_placeholder_category_score_calculation():
    strategy = MockStrategyAgent()

    assert strategy.score_category_performance(views=100, likes=10, uploads=2) == 75.0
    assert strategy.score_category_performance(views=100, likes=10, uploads=0) == 0.0
