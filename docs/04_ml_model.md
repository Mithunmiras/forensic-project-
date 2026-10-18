# Sales Prediction Model - Methodology

The exact accuracy figures from the latest training run are in `docs/generated/model_report.md` and are shown on the Prediction page. This document explains how the model is built and how to interpret it.

## Target and inputs
- **Target:** `sales`, the sales value of one order line.
- **Inputs:** category, sub-category, market, customer segment, ship mode, order priority, quantity, discount, shipping days, and calendar features (year, week number, month, quarter, day of week) derived from the order date. Optionally the shipping cost.
- **Never used:** `profit` (it is computed from sales) and identifiers such as row id, order id, customer id and product id.

## Two variants: handling target leakage
In the Superstore data the shipping cost scales with the order value (a Spearman correlation of about 0.91 with sales). Using it makes the model much more accurate, but it is effectively using a proxy of the answer. RetailIQ therefore trains two variants:

- **with_shipping_cost** - highest accuracy; used only when the caller supplies a shipping cost.
- **without_shipping_cost** - the leakage-safe variant using order attributes only; this is the default when no shipping cost is given.

The prediction response always states which variant produced the estimate. The accuracy of the leakage-safe variant is much lower, which is the honest measure of what order attributes alone can explain.

## Training and evaluation protocol
- Random 80/20 train/test split with `random_state=42`; the test set is used once, only for reporting.
- Candidates for each variant: a mean-predictor baseline, Ridge regression, a Decision Tree, a Random Forest and Gradient Boosting.
- Model selection uses 5-fold cross-validation on the training split only (best mean R-squared). The baseline cannot be selected.
- Reported metrics on the hold-out set: MAE, RMSE, R-squared and median absolute error. Training is repeatable with `python scripts/train_model.py`.
- The cross-validated R-squared is higher than the hold-out R-squared because sales are heavy-tailed and the hold-out set contains a few very large orders that dominate RMSE.

## Prediction interval
The 80% interval comes from two additional Gradient Boosting models trained for the 10th and 90th percentiles (quantile regression). It is not a guarantee: the empirical coverage measured on the hold-out set is reported next to it, and is slightly different from 80%.

## How to interpret an estimate
- It is a statistical estimate for one order line, not a forecast of future total sales.
- Values outside the training ranges (for example a quantity larger than any seen, or dates outside 2011-2014) trigger warnings because the estimate is then an extrapolation.
- Defaults applied for fields you leave out (segment, ship mode, priority, shipping days, date) are listed in the response as assumptions.

## Limitations
- Only 2011-2014 data; no knowledge of promotions, product attributes or customer history.
- Sales values are heavy-tailed, so typical errors are smaller than RMSE suggests but large orders are hard to predict.
- The model is not retrained automatically; retraining is an explicit, protected administrative action.
