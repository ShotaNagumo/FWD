import pytest
import requests
from pytest_mock import MockFixture

from fwd.src.util_request_wrapper import download_webpage, post_to_discord


class TestUtilRequestWrapper:
    def test_download_webpage(self):
        webpage_text = download_webpage("https://www.google.com", "utf-8")
        assert webpage_text

    def test_download_webpage_connection_error(self, mocker: MockFixture):
        mocker.patch("requests.get", side_effect=requests.ConnectionError)
        with pytest.raises(requests.ConnectionError):
            _ = download_webpage("https://www.google.com", "utf-8")

    def test_download_webpage_http_error(self, mocker: MockFixture):
        mocker.patch("requests.get", side_effect=requests.HTTPError)
        with pytest.raises(requests.HTTPError):
            _ = download_webpage("https://www.google.com", "utf-8")

    def test_download_webpage_timeout(self, mocker: MockFixture):
        mocker.patch("requests.get", side_effect=requests.Timeout)
        with pytest.raises(requests.Timeout):
            _ = download_webpage("https://www.google.com", "utf-8")

    def test_download_webpage_request_exception(self, mocker: MockFixture):
        mocker.patch("requests.get", side_effect=requests.RequestException)
        with pytest.raises(requests.RequestException):
            _ = download_webpage("https://www.google.com", "utf-8")

    def test_post_to_discord_success(self, mocker: MockFixture):
        mocker.patch("requests.post", return_value=mocker.Mock(status_code=200))
        post_to_discord("dummy_url", "dummy_message")

    def test_post_to_discord_connection_error(self, mocker: MockFixture):
        mocker.patch("requests.post", side_effect=requests.ConnectionError)
        with pytest.raises(requests.ConnectionError):
            post_to_discord("dummy_url", "dummy_message")

    def test_post_to_discord_http_error(self, mocker: MockFixture):
        mocker.patch("requests.post", side_effect=requests.HTTPError)
        with pytest.raises(requests.HTTPError):
            post_to_discord("dummy_url", "dummy_message")

    def test_post_to_discord_timeout(self, mocker: MockFixture):
        mocker.patch("requests.post", side_effect=requests.Timeout)
        with pytest.raises(requests.Timeout):
            post_to_discord("dummy_url", "dummy_message")

    def test_post_to_discord_request_exception(self, mocker: MockFixture):
        mocker.patch("requests.post", side_effect=requests.RequestException)
        with pytest.raises(requests.RequestException):
            post_to_discord("dummy_url", "dummy_message")
