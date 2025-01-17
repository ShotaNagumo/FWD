import argparse
from pathlib import Path

from fwdnagaoka.main import FwdNagaoka
from fwdutil import logger_initializer


def create_config_file(args):
    pass


def execute_nagaoka(args):
    logconfig_file_path = Path(__file__).parents[2] / "config" / "log_format.yaml"
    logger_initializer.initialize(logconfig_file_path)
    _ = FwdNagaoka()


def _create_argparser() -> argparse.ArgumentParser:
    # parser本体、supparserを作成する
    argparser = argparse.ArgumentParser()
    subparsers = argparser.add_subparsers()

    # 設定ファイルを作成するコマンド定義
    parser_create_config = subparsers.add_parser("create_config")
    parser_create_config.set_defaults(func=create_config_file)

    # 長岡市の処理を実行するコマンド定義
    parser_execute_nagaoka = subparsers.add_parser("execute_nagaoka")
    parser_execute_nagaoka.set_defaults(func=execute_nagaoka)

    # parser本体を返却
    return argparser


def main():
    argparser = _create_argparser()
    args = argparser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
