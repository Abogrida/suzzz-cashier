# Hybrid Access Guide: Offline Local & Online Cloud

This guide explains how to configure your system to work **Offline (Local Network)** and **Online (Cloud)** simultaneously.

## 1. How It Works (The "Hybrid" Strategy)
Your system runs on your Main Computer.
- **Offline (Local Network) [Port 3000 & 3001]**:
    - **Works without Internet.**
    - Devices (Tablets/Phones) connected to the **Same WiFi** access the system directly.
    - If the internet cuts out ("If net finishes"), THIS CONTINUES TO WORK PERFECTLY.
- **Online (Cloud) [Cloudflare Tunnel]**:
    - **Requires Internet.**
    - Allows you to access the system from **Anywhere in the world**.
    - If the internet cuts out, this stops working until the internet returns.

---

## 2. Using Ports 3000 & 3001
The system now runs two parallel interfaces:
- **Port 3000**: **Full Admin & Cashier System** (Login required)
- **Port 3001**: **Tablet/Waiter Interface** (Direct access)

### Local Access URLs
From the Main Computer:
- Admin: `http://localhost:3000`
- Tablet: `http://localhost:3001`

From Other Devices (Phone/Tablet on same WiFi):
1. Find your Local IP (shown when you start the app, e.g., `192.168.1.5`).
2. Use: `http://192.168.1.5:3000` (Admin) or `http://192.168.1.5:3001` (Tablet).

---

## 3. Setting Up Cloud Access (Cloudflare Tunnel)
To access the system from outside (like a "Cloud Server"), use Cloudflare Tunnel. It is free, secure, and doesn't require opening router ports.

### Step 1: Install Cloudflared
1.  Download `cloudflared` for Windows from [Cloudflare Downloads](https://github.com/cloudflare/cloudflared/releases).
2.  Rename the downloaded file to `cloudflared.exe`.
3.  Place it in a folder (e.g., `C:\cloudflared`).

### Step 2: Start the Tunnel
Open Command Prompt (cmd) and run:
```cmd
cloudflared tunnel --url http://localhost:3000
```

### Step 3: Get Your Cloud Link
You will see a link in the output like:
`https://random-name-here.trycloudflare.com`

- **Share this link** with anyone who needs remote access.
- Any changes made via this Cloud link are instantly saved to your local database.

---

## FAQ

**Q: "If net finishes what happens?" (What if internet cuts off?)**
- **Cloud Link**: Stops working immediately. You cannot access it from *outside* the restaurant.
- **Local Network (3000/3001)**: **Keeps working 100%.** Your tablets and cashier inside the restaurant are NOT affected. They talk directly to the Main Computer via the WiFi router, not the internet.

**Q: Can I use a Custom Domain?**
- Yes, if you buy a domain (e.g., `myrestaurant.com`), you can configure Cloudflare Tunnel to use `admin.myrestaurant.com` for Port 3000 and `tablet.myrestaurant.com` for Port 3001.
