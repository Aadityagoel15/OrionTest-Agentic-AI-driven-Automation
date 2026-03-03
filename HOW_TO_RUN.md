# 🚀 How to Run BDD Automation AI Agents

This project provides an **AI‑driven BDD automation framework** that converts requirements into executable tests.

> ✅ **Important Design Principle**
>
> * This framework is **configuration‑driven**
> * Users should **only configure environment variables or config files**
> * **No framework code changes are required** to test against real APIs

---

## 1️⃣ Clone and enter the project

```powershell
git clone <your-github-url>.git
cd "BDD Automation"
```

---

## 2️⃣ Install dependencies

```powershell
pip install -r requirements.txt
```

---

## 3️⃣ Configure environment (`.env`) ✅ **PRIMARY CONFIGURATION POINT**

Create a `.env` file in the project root (you can copy from `env_template.txt`):

```text
# Choose ONE backend:
# - Cloud (Groq): USE_LOCAL_LLM=false and GROQ_API_KEY is required
# - Local (TinyLlama + LoRA): USE_LOCAL_LLM=true and GROQ_API_KEY is optional
USE_LOCAL_LLM=true

# Local LLM Configuration (only used when USE_LOCAL_LLM=true)
LOCAL_LLM_BASE_MODEL=TinyLlama/TinyLlama-1.1B-Chat-v1.0
LOCAL_LLM_LORA_PATH=models/tinyllama-lora-qa
LOCAL_LLM_DEVICE=auto
LLM_MAX_TOKENS=512

# RAG Configuration (used by local backend)
RAG_ENABLED=true

# Cloud LLM (optional fallback; required only when USE_LOCAL_LLM=false)
GROQ_API_KEY=your_actual_groq_api_key_here

# BASE_URL is required for web discovery/execution (optional for pure generation)
BASE_URL=http://localhost:8080
```

### 🔑 Notes

- `GROQ_API_KEY` is **mandatory only when** `USE_LOCAL_LLM=false` (cloud mode).
- `BASE_URL` is **required for web discovery/execution** and any real execution against a running app/API. If you omit it, generation can still work, but execution/discovery will fail.

  * Required only if you want to hit a **real running API**
  * If not provided, test generation still works, but execution may fail

---

## 4️⃣ Optional: Configure via `bdd.config.yaml`

You may optionally define project‑level defaults using `bdd.config.yaml`:

```yaml
project:
  type: api        # api | web
  base_url: http://localhost:8080
```

### 📌 Precedence Rule

1. `.env` values (highest priority)
2. `bdd.config.yaml`
3. Auto‑detection (fallback)

> ⚠️ You **do NOT need to edit this file** unless you want repository‑level defaults.

---

## 5️⃣ Verify system setup

From the project root:

```powershell
python test_system.py
```

Expected output:

```text
[PASS] ALL TESTS PASSED - System is ready to use!
```

If this fails:

* Verify Python version
* Run `pip install -r requirements.txt`
* If using cloud mode (`USE_LOCAL_LLM=false`), ensure `.env` exists and contains `GROQ_API_KEY`
* If using local mode (`USE_LOCAL_LLM=true`), ensure your LoRA path exists at `LOCAL_LLM_LORA_PATH`

---

## 6️⃣ Run the full AI pipeline (example)

This runs the full flow:
**requirements → (web) discovery → feature → step definitions → execution → reports → defects**

> ℹ️ For web projects, set `BASE_URL` in `.env` or `bdd.config.yaml` so discovery and Behave can reach the site.

```powershell
python orchestrator.py \
  --requirements "As a user, I want to authenticate using valid credentials so that I can access protected resources." \
  --feature-name login_feature
```

### What this does

* Generates a feature file → `features/login_feature.feature`
* Generates step definitions → `features/steps/login_feature_steps.py`
* (Web) Discovers UI and writes locators to `reports/ui_locators.properties`
* Executes Behave tests against `BASE_URL`
* Writes reports and defect summaries under `reports/`

> ⚠️ If the target app/API at `BASE_URL` is unreachable, Behave will fail execution after generation completes.

---

## 7️⃣ Run with your own requirements

### Inline requirements

```powershell
python orchestrator.py --requirements "Your API requirements here" --feature-name my_feature
```

### Requirements from file

Create a requirements file (e.g., `requirements/my_test.txt`) and run:

```powershell
python orchestrator.py --requirements requirements/my_test.txt --feature-name my_feature
```

### Example Requirements

Below are example requirements you can use as templates for your own tests:

#### Example 1: Simple Web Navigation
```
Navigate to the URL https://your-application-url.com/
Click on the "Dashboard" link
Verify that the dashboard page is displayed
Verify page title contains "Dashboard"
```

#### Example 2: Login Flow (Generic)
```
Navigate to the URL https://your-application-url.com/
Login with username "your_username" and password "your_password"
Verify that login was successful
Verify user is redirected to the home page
```

#### Example 3: Form Submission
```
Navigate to the URL https://your-application-url.com/contact
Enter "John Doe" into the "name" field
Enter "john@example.com" into the "email" field
Enter "This is a test message" into the "message" field
Click the "Submit" button
Verify that the success message "Thank you for your message!" is displayed
```

#### Example 4: Search Functionality
```
Navigate to the URL https://your-application-url.com/
Enter "search term" into the "search" field
Click the "Search" button
Verify that search results are displayed
Verify results contain "search term"
```

#### Example 5: API Testing - User Registration
```
Test POST /api/users endpoint
Request body: {"username": "testuser", "email": "test@example.com", "password": "testpass123"}
Verify response status is 201
Verify response contains "user_id"
Verify response contains "username" field with value "testuser"
```

#### Example 6: API Testing - Get Data
```
Test GET /api/products endpoint
Verify response status is 200
Verify response is a JSON array
Verify each item in array contains "id", "name", and "price" fields
```

#### Example 7: Multi-Step Workflow
```
Navigate to the URL https://your-application-url.com/
Click on the "Settings" menu
Click on "Profile" option
Enter "New Name" into the "full name" field
Enter "newemail@example.com" into the "email" field
Click the "Save" button
Verify that the success message "Profile updated successfully" is displayed
```

#### Example 8: Data Validation
---

## 🔍 Handling Locators on New Sites

The framework is site-agnostic. Locator resolution order:
1) Discovered selectors
2) Overrides in `reports/ui_locators.properties`
3) Heuristics (camelCase/kebab/nospace/underscore)
4) Visible text fallback

For reliability on unfamiliar sites, add critical locators to `reports/ui_locators.properties`, for example:
```text
first-name=[data-test="firstName"]
submit-button=#submit
```

Then rerun:
```powershell
python orchestrator.py --requirements requirements/my_test.txt --feature-name my_test
```
```
Navigate to the URL https://your-application-url.com/register
Enter "invalid-email" into the "email" field
Click the "Register" button
Verify that error message "Please enter a valid email address" is displayed
```

#### Example 9: Navigation Flow
```
Navigate to the URL https://your-application-url.com/
Click on the "About" link
Verify user is on the about page
Click on the "Contact" link
Verify user is on the contact page
Click on the "Home" link
Verify user is back on the home page
```

#### Example 10: Button/Action Testing
```
Navigate to the URL https://your-application-url.com/
Click the "Download" button
Verify that download started
OR
Click the "Export" button
Verify that export file is generated
Verify file contains expected data
```

### Writing Requirements Tips

- **Use plain English** to describe what should happen
- **Include URLs, button names, field names** as they appear in your app
- **Specify verification steps** to check expected outcomes
- **Use quotes** for exact text matches: "Submit", "Error message"
- **Describe user actions**: click, enter, select, navigate
- **Use verification verbs**: verify, check, should see, should contain

### Common Patterns

- **Navigation**: `Navigate to the URL ...`
- **Actions**: `Click on ...`, `Enter ... into ...`, `Select ...`
- **Verification**: `Verify that ...`, `Check if ...`, `Should see ...`
- **Login**: `Login with username ... and password ...`

The framework will automatically convert these to executable test steps!

---

## 8️⃣ Output locations

| Artifact         | Location                                 |
| ---------------- | ---------------------------------------- |
| Feature files    | `features/{feature_name}.feature`        |
| Step definitions | `features/steps/{feature_name}_steps.py` |
| Execution report | `reports/execution_report_*.json`        |
| AI test report   | `reports/test_report_*.json`             |
| Summary report   | `reports/test_report_summary_*.txt`      |
| Defect report    | `reports/defects_*.json`                 |
| UI locators (web)| `reports/ui_locators.properties`         |

---

## 9️⃣ What NOT to modify ❌ (Critical)

Do **NOT** edit:

* `agents/`
* `features/*.feature`
* `features/steps/*.py`
* `orchestrator.py`
* Base step helpers under `features/steps/base/`

✔️ **Only configure via `.env` or `bdd.config.yaml`**

---

## 🔧 Troubleshooting (Quick)

### Module not found / import error

```powershell
pip install -r requirements.txt
```

---

### Groq API errors

* Ensure `.env` exists
* Ensure `GROQ_API_KEY` is valid

---

### Behave execution errors

* Ensure `BASE_URL` points to a running API
* Or run pipeline only for generation and ignore execution failures

---

## ✅ Summary

* ✔️ Plug‑and‑play for company teams
* ✔️ Safe for real API testing
* ✔️ No framework code changes required
* ✔️ Configuration‑driven and scalable

---

For deeper details, see:

* `README.md` – high‑level overview
* `SETUP_GUIDE.md` – complete setup steps
* `ARCHITECTURE.md` – pipeline and agent roles
* `FILE_STRUCTURE.md` – required/generated files
* `TESTING.md` – ways to verify the system
