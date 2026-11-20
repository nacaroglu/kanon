import kanon


def test_package_version_is_non_empty_string():
    assert isinstance(kanon.__version__, str)
    assert kanon.__version__
