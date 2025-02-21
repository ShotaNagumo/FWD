# 動作保証環境
## ハードウェア
Raspberry Pi 3 model B

## カーネル
```
uname -a
```
出力結果
> Linux raspberrypi 5.10.52-v7+ #1441 SMP Tue Aug 3 18:10:09 BST 2021 armv7l GNU/Linux


## OS
```
lsb_release -a
```
出力結果
> No LSB modules are available.
> Distributor ID: Raspbian
> Description:    Raspbian GNU/Linux 10 (buster)
> Release:        10
> Codename:       buster


# インストール手順
## OSのインストール、一般ユーザの作成
記載割愛

## uvのインストール
一般ユーザで下記を実行し、uvをインストールする
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```