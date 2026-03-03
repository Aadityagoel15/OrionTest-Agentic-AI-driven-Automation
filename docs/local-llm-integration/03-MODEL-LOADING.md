# Step 3: Load Model Correctly (Base + LoRA)

## Critical Loading Order

The model MUST be loaded in this specific order:

```
1. Tokenizer    ─── From BASE model (TinyLlama)
2. Base Model   ─── TinyLlama-1.1B-Chat-v1.0
3. LoRA Adapter ─── Attach using PEFT
4. Eval Mode    ─── Set to inference mode
```

### Why This Order Matters

1. **Tokenizer from Base**: LoRA doesn't modify the tokenizer. Using a different tokenizer will cause token mismatch errors.

2. **Base Model First**: The LoRA adapter is a delta on top of the base model. It cannot exist standalone.

3. **LoRA Last**: PEFT's `PeftModel.from_pretrained()` wraps the base model with the adapter weights.

4. **Eval Mode**: Disables dropout and other training-specific behaviors for deterministic inference.

## Implementation

### Tokenizer Loading

```python
from transformers import AutoTokenizer

# ALWAYS use the base model name for tokenizer
tokenizer = AutoTokenizer.from_pretrained(
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    trust_remote_code=True
)

# Ensure pad token exists
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
```

### Base Model Loading

```python
from transformers import AutoModelForCausalLM
import torch

# Determine dtype based on device
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device == "cuda" else torch.float32

# Load base model
base_model = AutoModelForCausalLM.from_pretrained(
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    torch_dtype=dtype,
    device_map="auto" if device == "cuda" else None,
    trust_remote_code=True
)

# Move to CPU if needed
if device == "cpu":
    base_model = base_model.to("cpu")
```

### LoRA Adapter Attachment

```python
from peft import PeftModel

# Attach LoRA adapter
lora_path = "models/tinyllama-lora-qa"
model = PeftModel.from_pretrained(base_model, lora_path)

# Set to evaluation mode (CRITICAL for determinism)
model.eval()
```

## Complete Loading Code

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

def load_model():
    BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    LORA_PATH = "models/tinyllama-lora-qa"
    
    # Set reproducibility
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)
    
    # 1. Tokenizer from BASE model
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # 2. Determine device and dtype
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    
    # 3. Load base model
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=dtype,
        device_map="auto" if device == "cuda" else None
    )
    
    if device == "cpu":
        base_model = base_model.to("cpu")
    
    # 4. Attach LoRA
    model = PeftModel.from_pretrained(base_model, LORA_PATH)
    
    # 5. Set eval mode
    model.eval()
    
    return model, tokenizer
```

## Memory Requirements

### GPU (CUDA)

| Component | Memory |
|-----------|--------|
| Base Model (FP16) | ~2.2 GB |
| LoRA Adapter | ~50 MB |
| Inference Overhead | ~500 MB |
| **Total** | **~2.7 GB** |

### CPU

| Component | Memory |
|-----------|--------|
| Base Model (FP32) | ~4.4 GB |
| LoRA Adapter | ~100 MB |
| Inference Overhead | ~1 GB |
| **Total** | **~5.5 GB** |

## Lazy Loading

The LocalLLMClient uses lazy loading to defer model loading until first use:

```python
class LocalLLMClient:
    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._is_loaded = False
    
    def _ensure_loaded(self):
        if self._is_loaded:
            return
        
        # Load model here
        self._model, self._tokenizer = load_model()
        self._is_loaded = True
    
    def generate_response(self, prompt, system_prompt=None):
        self._ensure_loaded()  # Loads on first call
        # ... generation logic
```

Benefits:
- Faster application startup
- Model only loaded when needed
- Configuration can be changed before loading

## Common Errors

### Error: "Can't load tokenizer for 'models/tinyllama-lora-qa'"

**Cause**: Attempting to load tokenizer from LoRA path instead of base model.

**Fix**: Always use base model name for tokenizer:
```python
# WRONG
tokenizer = AutoTokenizer.from_pretrained(lora_path)

# CORRECT
tokenizer = AutoTokenizer.from_pretrained("TinyLlama/TinyLlama-1.1B-Chat-v1.0")
```

### Error: "CUDA out of memory"

**Cause**: Insufficient GPU memory.

**Fix**: 
1. Use CPU: Set `device="cpu"`
2. Use quantization (8-bit or 4-bit)
3. Reduce batch size / max tokens

### Error: "ValueError: Tokenizer class ... does not exist"

**Cause**: Missing `trust_remote_code=True`

**Fix**: Add `trust_remote_code=True` to both tokenizer and model loading.

## Quantization (Optional)

For lower memory usage on GPU:

```python
from transformers import BitsAndBytesConfig

quantization_config = BitsAndBytesConfig(
    load_in_8bit=True
)

base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    quantization_config=quantization_config,
    device_map="auto"
)
```

**Note**: Quantization may slightly affect output quality. Test thoroughly before production use.
