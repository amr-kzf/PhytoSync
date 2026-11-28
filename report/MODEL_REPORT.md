# Model report

## Included public baseline

| Field | Value |
|---|---|
| Task | Plant disease image classification |
| Architecture | EfficientNet-B0 |
| Labels | 38 PlantVillage-style classes (`artifacts/public_plantvillage_baseline/class_names.json`) |
| Training/validation images | 45,770 / 11,079 |
| Training metadata | `artifacts/public_plantvillage_baseline/training_config.json` |
| Validation artifacts | `artifacts/public_plantvillage_baseline/evaluation/` |
| Accuracy | 0.9873 |
| Macro-F1 | 0.9795 |
| Field evaluation | Not reported |
| Official held-out evaluation | Not available |

The metrics are from the baseline's local validation split. They do not measure performance on independent field images, and must not be presented as an official or field-test score. Dataset files are not distributed with this repository; consult the upstream dataset's source and license before training or redistribution.

## Limitations

- Domain shift between curated leaf images and field photographs can reduce accuracy.
- Softmax confidence is not a calibrated probability of correctness.
- Image-quality checks are heuristic and may not detect every unsuitable image.
- Predictions and precautions are informational only; consult qualified local agricultural experts and applicable product labels before taking action.

## Reproducibility

The checkpoint, class names, training configuration, class history, duplicate audit, and evaluation metrics are stored beside this report in `artifacts/public_plantvillage_baseline/`. See the [README](../README.md#model-and-evaluation) for setup and training/evaluation commands.
