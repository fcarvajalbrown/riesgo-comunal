from report import Summary, report, summarize


def test_summarize_counts_failures_and_marker_steps():
    runs = [
        {"databaseId": 1, "conclusion": "success"},
        {"databaseId": 2, "conclusion": "failure"},
        {"databaseId": 3, "conclusion": "success"},
        {"databaseId": 4, "conclusion": "cancelled"},
    ]
    steps = {1: {"Run build"}, 2: set(), 3: {"Hostinger upload missed", "Region setup failed"}, 4: set()}
    summary = summarize(runs, steps.__getitem__)
    assert (summary.finished, summary.succeeded) == (3, 2)
    assert summary.failed == [2]
    assert summary.hostinger_missed == [3]
    assert summary.region_failed == [3]
    assert summary.bad


def test_clean_day_is_not_bad():
    summary = summarize([{"databaseId": 1, "conclusion": "success"}], lambda _id: {"Run build"})
    assert not summary.bad
    assert report(summary, "o/r", 24).startswith("Last 24 h: 1 of 1 runs succeeded.")


def test_report_links_runs():
    body = report(Summary(finished=1, failed=[7]), "o/r", 24)
    assert "[7](https://github.com/o/r/actions/runs/7)" in body
