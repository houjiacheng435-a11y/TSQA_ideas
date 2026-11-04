"""固定公开数据与源码版本，所有新增产物仅写入第五版或外部缓存。"""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "sources"
REVISION = "eb86b2ecc46b2f26b3a4e1768d7b479dc9abc521"
CACHE = Path(os.environ.get("UKDALE_CACHE", str(HERE.parents[2]/"data/qsample-v4-ukdale"/REVISION)))
TEXT_DIR = HERE.parents[2]/"data/qsample-text-bert-tiny"
TEXT_REVISION = "6f75de8b60a9f8a2fdf7b69cbd86d9e64bcb3837"
OFFICIAL = Path(os.environ.get("TS_HAYSTACK_SOURCE", "/root/autodl-tmp/cf-run/vendor/v020/TS-Haystack"))
