# 📞 AI Call Center Guidance System

A full-stack AI-powered call center assistant built with **Django + DRF + Whisper**, capable of:

- 📂 Call management (create, store, delete calls)
- 🎤 Audio upload and transcription
- ⚡ Real-time (live) PCM audio streaming transcription
- 💬 Chat-style transcript UI (Caller vs Agent)
- 🧠 AI-based call analysis (intent, sentiment, summary)
- 📊 Live dashboard with guidance for agents

---

## 🚀 Features

### ✅ Core Features
- Upload recorded calls and transcribe using Whisper
- Live audio streaming with PCM processing
- Real-time transcript updates
- Chat-style UI (like WhatsApp)
- AI-generated:
  - Intent detection
  - Sentiment analysis
  - Call summary
  - Agent guidance

---

### ⚡ Live Streaming (Advanced)
- Audio captured via `AudioWorklet`
- Downsampled to **16kHz PCM**
- Sent in chunks to backend
- Buffered and converted to WAV
- Transcribed using Whisper

---

## 🏗️ Tech Stack

### Backend
- Django
- Django REST Framework
- Whisper (OpenAI)
- FFmpeg (for audio processing)

### Frontend
- HTML / CSS / JavaScript
- AudioWorklet API
- Fetch API

---

## 📁 Project Structure
