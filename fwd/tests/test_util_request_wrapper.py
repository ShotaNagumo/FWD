from fwd.src.util_request_wrapper import download_webpage


class TestUtilRequestWrapper:
    def test_download_webpage(self):
        webpage_text = download_webpage("https://www.google.com", "utf-8")
        assert webpage_text
