---
title: Getting started
summary: Install Vigil, prove it works offline, then run your first level.
section: Start here
order: 2
---

# Getting started

This takes about 15 minutes. Steps 1 to 3 need **no API key and cost nothing**, so you can confirm everything works before you spend a cent.

## What you need

- **Python 3.11 or newer.** Check with `python --version`.
- **Git**, to clone the repository.
- **An OpenAI API key**, but only from step 4. Get one from the OpenAI platform. Running the levels uses a small amount of paid credit.
- **Docker** is optional. You only need it for levels L5 and L6, which use a database.

## Step 1. Get the code and install it

On macOS or Linux:

```bash
git clone https://github.com/Iamsomasundaram/vigil.git
cd vigil
python -m venv .venv
source .venv/bin/activate
pip install -e ".[full,dev,foundations,notebooks]"
```

On Windows PowerShell:

```powershell
git clone https://github.com/Iamsomasundaram/vigil.git
cd vigil
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[full,dev,foundations,notebooks]"
```

> **Tip** If PowerShell refuses to run the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or skip activation and call `.venv\Scripts\python.exe` directly.

A *virtual environment* (`.venv`) is a private folder of Python packages for this project, so it cannot clash with anything else on your machine.

## Step 2. Prove it works, offline

```bash
python -m pytest -q
```

Every test replaces the real model with a stand-in, so this makes no network calls. You should see a long row of dots and a summary such as `passed, skipped`. A few tests are skipped when an optional package is missing, which is normal. Any **failure** on a fresh install is a bug worth reporting.

## Step 3. Look around with a notebook

```bash
jupyter lab notebooks/
```

Open `00_setup.ipynb`. The notebooks run fully offline and let you change one value at a time to see what happens.

## Step 4. Add your API key

```bash
cp .env.example .env          # Windows: Copy-Item .env.example .env
```

Open `.env` and set the key:

```text
OPENAI_API_KEY=your-key-here
```

> **Warning** `.env` holds a secret. It is already listed in `.gitignore`, so git will not commit it. Never paste the key into code, chat, or a screenshot.

## Step 5. Run Level 0

```bash
python levels/l0_single_call.py CVE-2021-44228
```

You should see a header with the model name and CVE, then one panel containing a plain-English explanation of Log4Shell. The exact wording changes on every run; that is normal for a language model.

Now open [Level 0](l0.md) and read the code next to the output you just produced.

## If something goes wrong

| What you see | What it usually means |
| --- | --- |
| `The api_key client option must be set` | The key was not loaded. Check `.env` exists in the repo root and run from there. |
| `ModuleNotFoundError: vigil` | You skipped `pip install -e ...` or the virtual environment is not active. |
| PowerShell blocks the activate script | See the tip above. |
| `pip install` fails with `No such file or directory` on a long path (Windows) | Windows limits paths to 260 characters. Clone into a short folder such as `C:\src\vigil`. |
| A `401` or `insufficient_quota` error | The key is wrong, or the account has no credit. |

The README has a longer troubleshooting table.

## Optional: the web interface

If you prefer clicking to typing, start the API and the Streamlit interface in two terminals:

```bash
uvicorn vigil.api:app --reload
streamlit run ui/app.py
```

Then open the address Streamlit prints (normally `http://localhost:8501`). There is one page per level.

> **Note** Levels L5 and L6 store data in PostgreSQL. The simplest way to run them is `docker compose up --build`, which starts the API, the database and the interface together. Leave them until L0 to L4 feel comfortable.
