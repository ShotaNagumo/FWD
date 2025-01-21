import argparse
from pathlib import Path

from fwdnagaoka.fwd_nagaoka import FwdNagaoka
from fwdutil import logger_initializer


def create_config_file(args):
    pass


def setup_fwd(args):
    FwdNagaoka.setup()


def execute_nagaoka(args):
    logconfig_file_path = Path(__file__).parents[2] / "config" / "log_format.yaml"
    logger_initializer.initialize(logconfig_file_path)
    fwd_nagaoka = FwdNagaoka()
    fwd_nagaoka.execute()


def store_old_nagaoka(args):
    logconfig_file_path = Path(__file__).parents[2] / "config" / "log_format.yaml"
    logger_initializer.initialize(logconfig_file_path)
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


def main():
    argparser = _create_argparser()
    args = argparser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
