"""동일한 profile을 A·B에서 읽고 기존 기준값을 보존하는지 확인합니다."""
import json
import tempfile
import unittest
from pathlib import Path
from filename_bench.common import ROOT, load_config

class ProfileTests(unittest.TestCase):
    def config(self):
        return ROOT/'configs'/('a_quality.json' if (ROOT/'a_quality.py').exists() else 'b_local.json')
    def test_relative_paths_and_override(self):
        original=load_config(self.config())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ((root/'prompt.txt').resolve()).write_text('테스트 프롬프트')
            (root/'schema.json').write_text('{}')
            profile=root/'profile.json'
            profile.write_text(json.dumps({'baseline':{'short_edge_px':320},'prompt_path':'prompt.txt','schema_path':'schema.json'}))
            cfg=load_config(self.config(),profile)
            self.assertEqual(cfg['baseline']['short_edge_px'],320)
            self.assertEqual(cfg['baseline']['max_new_tokens'],original['baseline']['max_new_tokens'])
            self.assertEqual(cfg['backend'],original['backend'])
            self.assertEqual(Path(cfg['prompt_path']),(root/'prompt.txt').resolve())
            self.assertEqual(load_config(self.config()),original)
    def test_unknown_profile_field_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.json';path.write_text('{"backend": {}}')
            with self.assertRaises(ValueError):load_config(self.config(),path)

if __name__=='__main__':unittest.main()
