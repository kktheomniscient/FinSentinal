from app.agent.nodes import _grounded, parse_json, verifier_node


def test_parse_json_tolerant():
    assert parse_json('Sure! ```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json("no json") is None


def test_grounded():
    corpus = "Net sales 94,036 and net income 23,434".replace(",", "")
    assert _grounded(94036, corpus) and _grounded(-23434, corpus)
    assert not _grounded(94037, corpus) and not _grounded(9403, corpus)
    # a derived ratio must not "match" a stray 0 via rounding
    assert not _grounded(0.3967, "Net sales 94036 and 0 items 10") and not _grounded(39.7, "values 40 and 39")
    assert _grounded(36629.0, "net income 36629") and _grounded(7.5, "up 7.5 %")


def test_verifier_flags_invented_number():
    state = {"memo": "Net sales were 94,036 million [S1], up 7.5% and EPS 9.99.",
             "chunks": [{"text": "Net sales 94,036 up 7.5%"}]}
    v = verifier_node(state)["verification"]
    assert v["unverified"] == ["9.99"] and v["numbers_checked"] == 3


def test_verifier_accepts_trillion_scale_market_cap():
    state = {"memo": "Market cap is about $4.98 trillion [M].", "market": {"market_cap": 4975383019520.0}}
    assert verifier_node(state)["verification"]["unverified"] == []


def test_verifier_reports_where_figures_come_from():
    state = {
        "memo": "Revenue was 92,279 million [S2], a net margin of 39.69% [C1], at $342.37 [M].",
        "chunks": [{"tag": "S1", "text": "other 11,111", "metadata": {"section": "Part I Item 1", "period_end": "2025-01-01"}},
                   {"tag": "S2", "text": "Total revenue | 92,279 | 77,673 Net income | 36,629",
                    "metadata": {"section": "Part I Item 2", "period_end": "2026-09-30"}}],
        "calcs": [{"tool": "net_margin", "inputs": {"net_income": 36629, "revenue": 92279}, "result": 39.69}],
        "market": {"price": 342.37},
    }
    v = verifier_node(state)["verification"]
    by = {g["figure"]: g for g in v["grounding"]}
    assert v["unverified"] == []
    assert by["92,279"]["tag"] == "S2" and by["92,279"]["period_end"] == "2026-09-30"
    assert "Total revenue | 92,279" in by["92,279"]["snippet"] and by["92,279"]["source_text"] == "92,279"
    assert by["39.69"]["kind"] == "calc" and by["$342.37"]["kind"] == "market"


def test_verifier_ignores_form_names_and_time_units():
    state = {"memo": "Standard 10-Qs; it files 20-F and 6-K and traded over 52 weeks and 52-week range; revenue 92,279 [S1].",
             "chunks": [{"tag": "S1", "text": "Total revenue | 92,279", "metadata": {"section": "x", "period_end": "2026-09-30"}}]}
    v = verifier_node(state)["verification"]
    assert v["unverified"] == [] and v["numbers_checked"] == 1


def test_verifier_ignores_calendar_dates():
    state = {"memo": "For the quarter ended September 30, 2026 revenue was 92,279 [S1].",
             "chunks": [{"tag": "S1", "text": "Total revenue | 92,279", "metadata": {"section": "x", "period_end": "2026-09-30"}}]}
    v = verifier_node(state)["verification"]
    assert [g["figure"] for g in v["grounding"]] == ["92,279"] and v["numbers_checked"] == 1


def test_verifier_matches_magnitude_of_negative_calc_results():
    state = {"memo": "Revenue fell 0.17% [C1], from $28,095 million to $28,046 million [S1].",
             "chunks": [{"tag": "S1", "text": "Total revenues | 28,046 | 28,095", "metadata": {"section": "x", "period_end": "2026-09-30"}}],
             "calcs": [{"tool": "yoy_growth", "inputs": {"current": 28046, "previous": 28095}, "result": -0.17}]}
    assert verifier_node(state)["verification"]["unverified"] == []
