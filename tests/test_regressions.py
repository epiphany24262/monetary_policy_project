import json

import pandas as pd


def test_main_volatility_regression_and_auxiliary_result_retained():
    main = json.loads(open("output/results/stock_volatility_main.json", encoding="utf-8").read())
    assert "guidance_novelty" in main["params"]
    assert "guidance_novelty_x_post_2019" in main["params"]
    assert "bootstrap_ci_95_guidance_novelty" in main
    assert "post_2019_total_effect" in main
    auxiliary = json.loads(open("output/results/auxiliary_primary_result.json", encoding="utf-8").read())
    assert auxiliary["pvalues"]["guidance_tone_change"] == 0.5718680236295097
    curve = pd.read_csv("output/results/yield_curve_results.csv")
    assert "auxiliary_1y_m1_p3" in set(curve["model"])
    main_curve = curve[curve["model"] == "main_yield_curve"].iloc[0]
    assert main_curve["dependent"] == "delta_slope_bp_0_3"
    assert main_curve["target"] == "guidance_unexpected_tone"
