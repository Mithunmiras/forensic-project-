# models/

Trained artifacts are generated locally and not committed:

- `sales_model.joblib` - best model + prediction-interval models + form options (~0.8 MiB)
- `metrics.json` - model comparison, feature importance and hold-out results shown in the UI

Create them with `python main.py train` (about 15 seconds). If they are missing
the API trains them automatically on first start.
