# Model Training Specification

## Purpose

Define repository-supported preparation and fine-tuning workflows for producing compatible local bag-detection model artifacts.

## Requirements

### Requirement: YOLO-format dataset preparation
The repository SHALL provide tooling to convert supported annotations into YOLO text labels and split images/labels into train and validation subsets.

#### Scenario: LabelMe annotation is converted
- **WHEN** a recognized LabelMe label is processed
- **THEN** the converter writes a YOLO label row containing class ID and normalized center/width/height coordinates

#### Scenario: Annotation label is unknown
- **WHEN** a LabelMe shape uses a label not present in the configured class map
- **THEN** that shape is skipped and a warning is emitted

### Requirement: Reproducible train/validation split
The dataset helper SHALL support a deterministic randomized train/validation split when the same seed and source set are used.

#### Scenario: Dataset is split with default seed
- **WHEN** the same image set is processed repeatedly with seed 42 and the same train ratio
- **THEN** the train/validation membership is reproducible

### Requirement: Ultralytics model fine-tuning
The training helper SHALL support fine-tuning a configurable Ultralytics base model against a supplied YOLO `data.yaml` dataset and writing run outputs under a configurable project/name path.

#### Scenario: Training completes with best weights
- **WHEN** a training run produces `best.pt`
- **THEN** the helper can copy that artifact to the configured project model destination

### Requirement: Model validation and optional export
The training helper SHALL run validation after training and SHOULD support optional ONNX export, including an optional INT8 export path when the underlying Ultralytics environment supports it.

#### Scenario: ONNX export is requested
- **WHEN** training completes and export is enabled
- **THEN** the helper requests an ONNX export from the trained model
