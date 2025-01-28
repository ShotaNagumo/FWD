from logging import config
from pathlib import Path

import yaml


def initialize(logger_config_file: Path):
    try:
        # ログ設定ファイルから情報を読みだす
        setting_data: dict = yaml.safe_load(
            logger_config_file.read_text(encoding="utf-8")
        )

        # ファイルに出力するhandlerがある場合は、そのファイルが入るディレクトリを作成する
        # このディレクトリ作成処理は、config.dictConfig()よりも前に行う必要がある。
        handlers = setting_data.get("handlers")
        for handler_name in handlers.keys():
            if file_name := handlers[handler_name].get("filename", None):
                log_out_dir = Path(file_name).parent
                if not log_out_dir.exists():
                    log_out_dir.mkdir()

        # ログ設定情報をloggingモジュールに設定する
        config.dictConfig(setting_data)

    except Exception as err:
        # エラー処理
        # loggerモジュールの初期化に失敗したためログファイルへの保存は出来ないため
        # print()にて出力する
        print("*** LOGGER INITIALIZE ERROR ***")
        print(f"{err}")

        # 呼び出し元モジュールで失敗を検知できるようにExceptionを再raiseする
        raise
