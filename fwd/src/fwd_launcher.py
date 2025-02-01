import argparse
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

CONFIG_DIR = Path(__file__).parents[2] / "config"
CONFIG_FILE_PATH = CONFIG_DIR / "fwd_config.yaml"
LOG_FORMAT_FILE_PATH = CONFIG_DIR / "fwd_log_format.yaml"


def create_config_file(args):
    # Jinja2設定
    _template_dir = Path(__file__).parents[1] / "resource" / "template"
    _j2_env = Environment(loader=FileSystemLoader(_template_dir))

    # 設定する値を読み取り
    data = {}
    data["variable_dir"] = input("variable_dir: ")
    data["nagaoka_webhook_url"] = input("webhook_url(nagaoka): ")

    # 設定ファイルを作成する
    fwd_config_template = _j2_env.get_template("fwd_config.j2")
    fwd_config_data = fwd_config_template.render(data)
    CONFIG_FILE_PATH.write_text(fwd_config_data, encoding="utf-8")
    print(f'Generated config file: "{CONFIG_FILE_PATH}"')

    # ログフォーマットファイルを作成する
    fwd_log_format_template = _j2_env.get_template("fwd_log_format.j2")
    fwd_log_format_data = fwd_log_format_template.render(data)
    LOG_FORMAT_FILE_PATH.write_text(fwd_log_format_data, encoding="utf-8")
    print(f'Generated log_format file: "{LOG_FORMAT_FILE_PATH}"')


def setup_fwd(args):
    # 設定ファイル未作成の状態でlauncher実行した場合に
    # エラーとなることを防ぐためここでインポート
    import util_logger_initializer
    from nagaoka_main import FwdNagaoka

    util_logger_initializer.initialize(LOG_FORMAT_FILE_PATH)
    FwdNagaoka.setup()


def execute_nagaoka(args):
    # 設定ファイル未作成の状態でlauncher実行した場合に
    # エラーとなることを防ぐためここでインポート
    import util_logger_initializer
    from nagaoka_main import FwdNagaoka

    util_logger_initializer.initialize(LOG_FORMAT_FILE_PATH)
    fwd_nagaoka = FwdNagaoka()
    fwd_nagaoka.execute()


def store_old_nagaoka(args):
    # 設定ファイル未作成の状態でlauncher実行した場合に
    # エラーとなることを防ぐためここでインポート
    import util_logger_initializer
    from nagaoka_main import FwdNagaoka

    util_logger_initializer.initialize(LOG_FORMAT_FILE_PATH)
    fwdNagaoka = FwdNagaoka()
    fwdNagaoka.store_old_data(args.text_dir)


def _create_argparser() -> argparse.ArgumentParser:
    # parser本体、supparserを作成する
    argparser = argparse.ArgumentParser()
    subparsers = argparser.add_subparsers()

    # 設定ファイルを作成するコマンド定義
    parser_create_config = subparsers.add_parser("create_config")
    parser_create_config.set_defaults(func=create_config_file)

    # 各FWDクラスをセットアップするコマンド定義
    parser_setup_fwd = subparsers.add_parser("setup_fwd")
    parser_setup_fwd.set_defaults(func=setup_fwd)

    # 長岡市の処理を実行するコマンド定義
    parser_execute_nagaoka = subparsers.add_parser("execute_nagaoka")
    parser_execute_nagaoka.set_defaults(func=execute_nagaoka)

    # 長岡市の過去データを設定するコマンド定義
    parser_store_old_nagaoka = subparsers.add_parser("store_old_nagaoka")
    parser_store_old_nagaoka.add_argument("text_dir", type=str)
    parser_store_old_nagaoka.set_defaults(func=store_old_nagaoka)

    # parser本体を返却
    return argparser


if __name__ == "__main__":
    argparser = _create_argparser()
    args = argparser.parse_args()
    args.func(args)
