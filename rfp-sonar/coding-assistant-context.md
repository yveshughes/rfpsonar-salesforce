# coding-assistant-context.md

## 🧠 Project Overview

**Project Name:** RFP Sonar — Government Procurement Directory  
**Platform:** Salesforce (Deployed via Salesforce CLI + VS Code)  
**Goal:**  
Create a robust metadata foundation inside Salesforce that models **Government Agencies** as **Account** records with a custom **record type** and **page layout**.  

This directory will eventually power an automation pipeline that:
- Scrapes public procurement portals.
- Auto-creates Opportunities from RFPs.
- Uses AI to draft proposal responses.

---

## ⚙️ Key Architecture

- **Object:** `Account`
- **Record Type:** `Government Agency`
- **Layout:** `Government Agency Layout`
- **Custom Fields:** Authentication, Procurement Portal, RFP Feed, Scraper Status, etc.
- **Security:** Use **Named Credentials / External Credentials** for authentication — never store raw passwords.
- **Automation Readiness:** Fields for RFP Feed URL, Last Scrape Date, Scraper Status.
- **Access Control:** Managed via a **Permission Set** (`RFP_Sonar_Access`).
- **Deployment Target:** Authenticated org alias → `ndmm`.

---

## 📁 Expected Folder Structure

(force-app structure etc... trimmed for brevity)
