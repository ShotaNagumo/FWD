import unicodedata
from logging import getLogger

import requests


def download_webpage(webpage_url: str, webpage_enc: str, timeout_sec=10) -> str:
    """出動情報が掲載されているWebページの情報を取得する

    Args:
        webpage_url (str): WebページのURL
        webpage_enc (str): Webページのエンコーディング
        timeout_sec (int, optional): Webページのダウンロードタイムアウト（秒）. Defaults to 10.

    Returns:
        str: 取得したWebページのテキスト
    """
    try:
        # loggerを取得
        logger = getLogger("requests")

        # WebpageデータをGET
        logger.info(f"GET: {webpage_url}")
        res = requests.get(webpage_url, timeout=timeout_sec)  # GET処理
        res.raise_for_status()  # HTTPレスポンスコードに応じたExceptionをraiseする

        # 取得成功した場合、取得データのエンコード、正規化を行い返却
        logger.info(
            f"Download SUCCEED. Status={res.status_code}, Length={len(res.text)}."
        )
        res.encoding = webpage_enc
        text_data: str = unicodedata.normalize("NFKC", res.text)
        return text_data

    except requests.ConnectionError:
        logger.error(f"Download FAILED. ConnectionError, Status={res.status_code}.")
        raise
    except requests.HTTPError:
        logger.error(f"Download FAILED. HTTPError, Status={res.status_code}.")
        raise
    except requests.Timeout:
        logger.error(f"Download FAILED. Timeout, Status={res.status_code}.")
        raise
    except requests.RequestException:
        logger.error(f"Download FAILED. RequestException, Status={res.status_code}.")
        raise


        raise
    except requests.HTTPError:
        logger.exception(f"Download FAILED. HTTPError, Status={res.status_code}.")
        raise
    except requests.Timeout:
        logger.exception(f"Download FAILED. Timeout, Status={res.status_code}.")
        raise
    except requests.RequestException:
        logger.exception(
            f"Download FAILED. RequestException, Status={res.status_code}."
        )
        raise
