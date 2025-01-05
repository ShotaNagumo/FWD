from pathlib import Path

import yaml

# 設定ファイルパス
CONFIGFILE_PATH = Path(__file__).parents[3] / "config" / "fwd-config.yaml"

# 設定ファイルデータ（ファイルI/O削減のためキャッシュする）
SETTING_DATA = None


def get_variable_dir() -> Path:
    """FWDソフトウェアのVariableデータ（実行中に増減するデータ）を保存するディレクトリのパスを取得する

    Returns:
        Path: Variableディレクトリのパス
    """

    # 設定ファイルデータが読み込まれていない場合、データを読み出す
    global SETTING_DATA
    if SETTING_DATA is None:
        SETTING_DATA = yaml.safe_load(CONFIGFILE_PATH.read_text())

    # 読み出したデータをPathに変換する
    return Path(SETTING_DATA["variable_dir"])
