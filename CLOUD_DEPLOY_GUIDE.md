# 🚀 Suzz Cloud Deployment Guide

This guide explains how to deploy the Cloud Backend to **Render.com** (Free Hosting) so your offline system can sync data.

## Step 1: Push Code to GitHub
1. Create a `New Repository` on GitHub.
2. Upload the `cloud_backend` folder contents to it.
   - Or simply push your entire project if it's already a repo.
   - **Crucial:** The `cloud_backend/requirements.txt` and `cloud_backend/main.py` must be in the repo.

## Step 2: Create Service on Render
1. Go to [Render.com](https://render.com) and Sign Up.
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository.
4. **Settings:**
   - **Name:** `suzz-cloud` (or any name)
   - **Region:** `Frankfurt` (Best for Egypt)
   - **Branch:** `main`
   - **Root Directory:** `cloud_backend` (Important!)
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port 10000`
   - **Instance Type:** `Free`

5. **Detailed Settings (Environment Variables):**
   - Click "Advanced" or "Environment Variables".
   - Add Key: `SYNC_SECRET`
   - Add Value: `my_secure_password_123` (Change this to something hard!)
   - Add Key: `PYTHON_VERSION`
   - Add Value: `3.9.0` (Optional but recommended)

6. Click **Create Web Service**.

## Step 3: Get Your URL
1. Wait for the deployment to finish (it takes a few minutes).
2. Once live, copying the URL at the top like: `https://suzz-cloud.onrender.com`.

## Step 4: Configure Local System
1. Open your Local Cashier PC.
2. Open `backend/sync_agent.py`.
3. Update line 15:
   ```python
   CLOUD_API_URL = "https://suzz-cloud.onrender.com" 
   ```
4. Update line 89 (Secret Key) to match what you put in Render:
   ```python
   "X-Sync-Secret": "my_secure_password_123"
   ```
5. Restart the Cashier System.

🎉 **Done!** Your system is now Hybrid (Offline-First + Cloud Sync).
