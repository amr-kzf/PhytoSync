# PhytoSync walkthrough

For installation, configuration, commands, API routes, and limitations, see the project [README](../README.md).

## Local applications

1. Install the dependencies and copy `.env.example` to `.env`.
2. Set a random `SECRET_KEY`; add optional service credentials only when using those integrations.
3. Run the Flask platform with `python app.py` and open `http://127.0.0.1:5144`.
4. Optionally run `python -m uvicorn fieldguard.main:app --reload --host 127.0.0.1 --port 8000` to use the standalone FastAPI service and its `/docs` page.
5. Run the automated tests with `python -m unittest discover -s tests -v`.

The applications are prototypes for local development, not production deployments. The Flask app initializes a local database and seeds sample content. Do not use seeded accounts or sample advice with real user data.

## Model notes

The repository includes a 38-class PlantVillage baseline and its evaluation outputs in `artifacts/public_plantvillage_baseline/`. Its recorded validation metrics are 98.73% accuracy and 0.9795 macro-F1. This is a validation-split result, not a held-out field benchmark or official evaluation.

Training and evaluation commands are maintained in the [README](../README.md#model-and-evaluation). Dataset files are not included. Obtain datasets from their official sources and follow their separate licenses and evaluation protocols. Do not train on a held-out test set.
