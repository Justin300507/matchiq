from app.utils.name_matching import names_match


def test_matches_when_one_name_is_a_substring_of_the_other():
    assert names_match("Arsenal", "Arsenal FC") is True
    assert names_match("Arsenal FC", "Arsenal") is True


def test_matches_case_insensitively():
    assert names_match("arsenal", "ARSENAL FC") is True


def test_does_not_match_unrelated_names():
    assert names_match("Arsenal", "Chelsea") is False
