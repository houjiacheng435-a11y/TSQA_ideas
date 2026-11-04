"""验证远程索引与官方重采样的关键语义；测试不访问网络或使用测试答案。"""
import io
import unittest
from unittest.mock import patch

import numpy as np

from signal_diagnostic import Meter,official_function


class IndexTests(unittest.TestCase):
    def test_remote_index_matches_numpy_with_realistic_gaps(self):
        # 使用不规则时间间隔和长缺测，独立地用 NumPy 全数组搜索作为参照。
        rng=np.random.default_rng(7)
        increments=rng.integers(5,9,size=80000).astype(np.int64)*10**9
        increments[9000]=50000*10**9
        increments[50000]=100000*10**9
        timestamps=1350000000000000000+increments.cumsum()
        values=np.arange(len(timestamps),dtype=np.float32)
        files={}
        for suffix,array in ((".t.npy",timestamps),(".npy",values)):
            stream=io.BytesIO();np.save(stream,array)
            files["signals/h99/m1"+suffix]=stream.getvalue()
        def read(relative,start,stop):return files[relative][start:stop]
        meter=Meter(99,1)
        targets=list(rng.integers(timestamps[0]-1,timestamps[-1]+2,size=100))
        targets += [timestamps[0]-1,timestamps[-1]+1,timestamps[2047],timestamps[2048],timestamps[8999]+1]
        with patch("signal_diagnostic.byte_range",side_effect=read):
            for target in targets:
                self.assertEqual(meter.lower_bound(target),int(np.searchsorted(timestamps,target)))
            a,b=int(timestamps[8998]),int(timestamps[9010])
            actual_t,actual_x=meter.window(a,b)
            chosen=(timestamps>=a)&(timestamps<b)
            np.testing.assert_array_equal(actual_t,timestamps[chosen])
            np.testing.assert_array_equal(actual_x,values[chosen])

    def test_official_resampling_is_preceding_hold_not_nearest(self):
        function=official_function("src/datasets/uk_dale_haystack/loader.py","resample_to_grid",
                                   dict(np=np,NOMINAL_DT_S=6.0))
        timestamps=np.array([0,10,100],dtype=np.int64)*10**9
        signal=np.array([1,2,3],dtype=np.float32)
        actual=function(timestamps,signal,0,42*10**9,6.0)
        # t=6 应取前一个值 1；t=36 的源点已超过 24 秒有效期，应为 0。
        np.testing.assert_array_equal(actual,[1,1,2,2,2,2,0])


if __name__=="__main__":unittest.main()
