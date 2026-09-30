# AI Caption & Voiceover App

An AI-powered web application built with Flask, OpenAI GPT-4o-mini Vision, and OpenAI Text-to-Speech (TTS). Upload an image, get an AI-generated descriptive caption, and listen to realistic voiceover narrations in various TTS voices.

## 🛡️ Admin Dashboard & Access

A dedicated Administrator Dashboard is included with user management and system analytics:

- **Admin Login URL:** `http://127.0.0.1:5000/admin/login` (or access via the Admin Panel button in the navbar)
- **Username:** `admin`
- **Password:** `123`

### Admin Features:
- **Comprehensive User Management:** View all user profiles, registration dates, last active timestamps, creation counts, and storage usage.
- **Deep Dive User Details:** View each user's history of image uploads, full captions, and listen to their generated audio voiceovers.
- **User Actions:** Create new users, edit usernames, reset passwords, promote/demote administrator privileges, and permanently delete accounts with automatic file cleanup.
- **All Generations Feed:** Browse, search, listen to, or delete any image caption and voiceover across the system.
- **Voice & Storage Analytics:** Breakdown of TTS voice model usage (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`) and disk storage consumption.
- **System Diagnostics:** Inspect database size, upload directory file counts, and OpenAI API connectivity.

## 🚀 Quick Start

1. **Activate Virtual Environment:**
   ```bash
   .venv\Scripts\activate
   ```

2. **Run App:**
   ```bash
   python app.py
   ```
   Or double-click `ai-voice.bat`.

3. **Open in Browser:**
   - App: [http://127.0.0.1:5000](http://127.0.0.1:5000)
   - Admin Portal: [http://127.0.0.1:5000/admin/login](http://127.0.0.1:5000/admin/login)
