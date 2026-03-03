# Step 1: Freeze the Trained Model

## Purpose

After training the TinyLlama model with a LoRA adapter for QA Automation, the trained weights must be treated as **immutable infrastructure**. This ensures consistent, reproducible behavior across all deployments.

## Critical Rules

### DO NOT

- ❌ Retrain the model without explicit approval and versioning
- ❌ Modify adapter weights directly
- ❌ Use different base model versions with the same adapter
- ❌ Share adapter files without version tracking

### DO

- ✅ Treat adapter files as read-only artifacts
- ✅ Version control adapter files (Git LFS or artifact storage)
- ✅ Document training run metadata
- ✅ Create checksums for integrity verification

## Files to Preserve

```
models/tinyllama-lora-qa/
├── adapter_config.json      # LoRA configuration
└── adapter_model.safetensors # Trained LoRA weights
```

### adapter_config.json

Contains LoRA hyperparameters:
- `r` (rank)
- `lora_alpha`
- `target_modules`
- `lora_dropout`
- `bias`

**Example:**
```json
{
  "base_model_name_or_path": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "bias": "none",
  "lora_alpha": 16,
  "lora_dropout": 0.05,
  "r": 8,
  "target_modules": ["q_proj", "v_proj"],
  "task_type": "CAUSAL_LM"
}
```

### adapter_model.safetensors

Contains the trained LoRA weights in safetensors format. This file is typically 10-50MB depending on LoRA rank.

## Versioning Strategy

### 1. Semantic Versioning

```
models/tinyllama-lora-qa-v1.0.0/
models/tinyllama-lora-qa-v1.0.1/
models/tinyllama-lora-qa-v1.1.0/
```

- **Major (1.x.x)**: Breaking changes to output format
- **Minor (x.1.x)**: New capabilities, backward compatible
- **Patch (x.x.1)**: Bug fixes to training data

### 2. Metadata Documentation

Create a `training_metadata.json`:

```json
{
  "version": "1.0.0",
  "training_date": "2025-01-24",
  "base_model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "dataset_hash": "sha256:abc123...",
  "training_steps": 1000,
  "hyperparameters": {
    "learning_rate": 2e-4,
    "batch_size": 4,
    "epochs": 3,
    "lora_r": 8,
    "lora_alpha": 16
  },
  "evaluation_metrics": {
    "gherkin_validity": 0.95,
    "refusal_accuracy": 0.92
  }
}
```

### 3. Checksum Verification

Generate SHA256 checksums:

```bash
sha256sum adapter_model.safetensors > checksums.txt
sha256sum adapter_config.json >> checksums.txt
```

Verify before deployment:

```bash
sha256sum -c checksums.txt
```

## Git LFS Setup (Recommended)

For version controlling large model files:

```bash
# Install Git LFS
git lfs install

# Track safetensors files
git lfs track "*.safetensors"

# Add to git
git add .gitattributes
git add models/
git commit -m "Add trained LoRA adapter v1.0.0"
```

## Alternative: Artifact Storage

For larger teams or CI/CD pipelines:

1. **AWS S3**
   ```bash
   aws s3 cp models/tinyllama-lora-qa/ s3://your-bucket/models/v1.0.0/ --recursive
   ```

2. **Azure Blob Storage**
   ```bash
   az storage blob upload-batch -d models -s models/tinyllama-lora-qa/
   ```

3. **HuggingFace Hub**
   ```python
   from huggingface_hub import upload_folder
   upload_folder(
       folder_path="models/tinyllama-lora-qa",
       repo_id="your-org/tinyllama-lora-qa",
       repo_type="model"
   )
   ```

## Rollback Procedure

If issues are discovered with a new model version:

1. Identify the problematic version
2. Switch to previous known-good version:
   ```python
   # In config.py or .env
   LOCAL_LLM_LORA_PATH=models/tinyllama-lora-qa-v0.9.0
   ```
3. Document the issue and resolution
4. Create hotfix if needed

## Compliance Notes

The LoRA adapter:
- Contains NO client data (trained on synthetic/public data only)
- Represents learned QA engineering patterns, not client-specific information
- Can be shared across projects safely
