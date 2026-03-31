# 📄 README — HTML Docs Page for GitHub Workflow Sync & Data Download

This project provides a simple HTML documentation page that allows you to:

* 🔄 Trigger GitHub Actions workflows on demand
* 📥 Download training data files directly from your repository

---

## 🚀 Setup Guide

Follow the official setup instructions:

👉 https://github.com/CrankAddict/section-11/blob/main/examples/json-auto-sync/SETUP.md

### ⚠️ Important Adjustment

In the workflow file below:

👉 https://github.com/CrankAddict/section-11/blob/main/examples/json-auto-sync/auto-sync.yml

**Remove the `schedule` section** to disable automatic execution.
This ensures workflows are only triggered manually via the HTML page.

---

## 🌐 Enable GitHub Pages (Serve `index.html`)

To make your HTML page accessible:

1. Add your `index.html` file to a `/docs` folder in the repository
2. Go to: **Repo → Settings → Pages**
3. Under **Source**, select:

   * **Deploy from a branch**
   * Choose your branch (e.g. `main`)
   * Select the `/docs` folder
4. Click **Save**

Your page will be available at:

```
https://{username}.github.io/{reponame}/
```

---

## 🔐 GitHub Token Configuration

You will need **fine-grained personal access token(s)**.

### 📍 Where to create tokens

```id="3a91cf"
GitHub → User Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens
```

---

### 🔑 Token Options

You can either:

* ✅ Use **one token for both download and workflow triggering**, or
* ✅ Use **separate tokens** with minimal required permissions

---

### 1️⃣ Token — Download Content

**Permissions:**

* Code → Read
* Metadata → Read

---

### 2️⃣ Token — Trigger Workflow

**Permissions:**

* Metadata → Read
* Actions → Read & Write

---

## 🔒 Security Notes

* Tokens are stored **only in your browser (local storage)**
* They are **never transmitted to any server other than GitHub APIs**
* Keep your tokens private and avoid exposing them publicly

---

## 🧩 How It Works

* The HTML page provides UI controls (buttons/options)
* When triggered:

  * Calls GitHub APIs using your token(s)
  * Executes workflows via `workflow_dispatch`
  * Fetches and downloads repository files

---

## ✅ Summary

* Manual workflow triggering (no cron jobs)
* Flexible token usage (single or minimal-permission tokens)
* Lightweight HTML interface for automation

---
