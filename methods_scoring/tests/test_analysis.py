"""Tests of numerical aggregation, eligibility and rank inference."""
import unittest
import sys
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'methods_scoring'))
sys.path.insert(0,str(ROOT/'user_study/data'))
import numpy as np
from scipy.stats import kendalltau
from scoring import INPUTS,score_views,eligible,hard_gate,tau_batch,joint_draws
from legal_expert_validation import exact_pooled_permutation_p,bh_fdr
import pandas as pd

class ScientificAnalysisTests(unittest.TestCase):
    def test_b5_confidentiality_in_default_and_task_cases(self):
        self.assertEqual(INPUTS['regulations']['MDR']['required']['confidentiality'], .5)
        cases = json.loads((ROOT/'methods_scoring/inputs/legal_task_cases.json').read_text())
        for case in cases:
            if 'MDR' in case['weights']:
                self.assertEqual(case['weights']['MDR']['confidentiality'], .5)
    def test_confidentiality_can_break_a_threshold_tie(self):
        x = np.array([[4, 2], [3, 3]], dtype=float)
        self.assertEqual(score_views(x, [1, 0])['threshold'].tolist(), [1., 1.])
        result = score_views(x, [1, .5])['threshold']
        self.assertAlmostEqual(result[0], 2/3)
        self.assertEqual(result[1], 1.)
    def test_property_weighted_mean(self):
        got=score_views([5,1,1],[1,1,1])
        self.assertAlmostEqual(got['soft'],7/15)
        self.assertNotAlmostEqual(got['soft'],.6)
    def test_mandatory_criterion_cannot_be_compensated(self):
        self.assertEqual(hard_gate(1,{'disclosure':True,'recipient':None}),0)
        self.assertEqual(hard_gate(.8,{'disclosure':True,'recipient':True}),.8)
    def test_question_scope_and_replacement(self):
        self.assertFalse(eligible('PDP','GDPR+AIA86+MiFID25','what_feature'))
        for name,meta in INPUTS['methods'].items():
            if meta.get('requires_model_replacement') or meta.get('component_only'):
                self.assertFalse(eligible(name,'MDR','what_feature'))
    def test_tau_with_ties_matches_scipy(self):
        rng=np.random.default_rng(1729)
        for _ in range(30):
            x=rng.integers(1,6,(20,4));y=rng.integers(1,6,4)
            expected=np.array([kendalltau(z,y).statistic for z in x])
            np.testing.assert_allclose(tau_batch(x,y),expected,equal_nan=True)
    def test_shared_draw_reproducibility(self):
        names=['PDP','RuleFit'];regs=['MDR','DSA17']
        a=joint_draws(names,regs,23,42);b=joint_draws(names,regs,23,42)
        for k in regs:np.testing.assert_array_equal(a[k],b[k])
    def test_paired_exact_test_uses_independent_context_labels(self):
        x=np.array([1,2,3,4]);y=np.array([4,1,3,2]);ratings=pd.DataFrame([[1,3,2,4],[1,2,4,3],[4,3,2,1],[2,4,1,3]],index=['E08','E11','E13','E18'])
        p=exact_pooled_permutation_p(x,ratings,y,ratings)
        order=[2,0,3,1]
        q=exact_pooled_permutation_p(x,ratings,y[order],ratings.iloc[:,order])
        self.assertAlmostEqual(p,q)
    def test_bh_adjusts_whole_family(self):
        result=bh_fdr([.01,.04,.03,.5])
        np.testing.assert_allclose(result,[.04,.053333333333,.053333333333,.5])

if __name__=='__main__':unittest.main()
