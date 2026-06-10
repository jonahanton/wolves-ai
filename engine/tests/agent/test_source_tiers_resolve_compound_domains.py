from wolves.agent.sources import source_tier


def test_source_tiers_resolve_compound_domains():
    assert source_tier("https://ge.globo.com/futebol/selecao/x.html") == 2
    assert source_tier("https://news.dailymail.co.uk/sport/x") == 3
    assert source_tier("https://sports.chosun.com/football/x") == 2
    assert source_tier("https://www.fifa.com/tournaments/x") == 1
    assert source_tier("https://some-unknown-blog.example.com/x") is None
