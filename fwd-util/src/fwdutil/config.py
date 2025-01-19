from pathlib import Path

import yaml

# 設定ファイルパス
CONFIGFILE_PATH = Path(__file__).parents[3] / "config" / "fwd-config.yaml"

# 設定ファイルデータ（ファイルI/O削減のためキャッシュする）
SETTING_DATA = None


def get_variable_dir() -> Path:
    """FWDソフトウェアのVariableデータ（実行中に増減するデータ）を保存するディレクトリのパスを取得する

    Raises:
        ValueError: variable_dir未定義
        ValueError: variable_dirがディレクトリパスとして不正

    Returns:
        Path: Variableディレクトリのパス
    """

    # 設定ファイルデータが読み込まれていない場合、データを読み出す
    global SETTING_DATA
    if SETTING_DATA is None:
        SETTING_DATA = yaml.safe_load(CONFIGFILE_PATH.read_text())

    # 読み出したデータをPathに変換する
    if not (variable_dir := SETTING_DATA.get("variable_dir")):
        raise ValueError("variable_dir未定義")
    try:
        variable_path = Path(variable_dir)
        return variable_path
    except Exception:
        raise ValueError("variable_dir不正")


def get_webhook_url(city_name: str) -> str:
    """指定した都市名のWebhook URLを取得する

    Args:
        city_name (str): 都市名

    Raises:
        ValueError: 指定した都市名の設定ブロック未定義
        ValueError: webhook_url未定義

    Returns:
        str: Webhook URL
    """

    # 設定ファイルデータが読み込まれていない場合、データを読み出す
    global SETTING_DATA
    if SETTING_DATA is None:
        SETTING_DATA = yaml.safe_load(CONFIGFILE_PATH.read_text())

    # Webhook URLを取得する
    if not SETTING_DATA.get(city_name):
        raise ValueError("指定した都市名の設定ブロック未定義")
    if not (webhook_url := SETTING_DATA.get(city_name).get("webhook_url")):
        raise ValueError("webhook_url未定義")
    return webhook_url
