"""只读复用v5组件；不改写旧版任何文件。"""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
V5=HERE.parent/'v5'
sys.path.insert(0,str(V5))
import model as v5_model
import data as v5_data
import losses as v5_losses
import source_io
from paths import CACHE,REVISION,OFFICIAL
# 重建函数的缓存仍共用，所有本轮来源记录改写到第六版。
source_io.HERE=HERE
# 组件已加载，恢复搜索路径，避免同名tests等误导入旧版。
sys.path.remove(str(V5))
