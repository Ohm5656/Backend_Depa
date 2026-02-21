# 🦐 **ShrimpSense AI — Smart Aquaculture Intelligence Platform**

### *AI-Powered Backend for Real-Time Shrimp Farm Monitoring*

<p align="center">
AI + IoT + Computer Vision to transform traditional shrimp farming into a data-driven intelligent ecosystem.
</p>

---

## 🌊 **What is ShrimpSense AI?**

**ShrimpSense AI** is an AI-driven backend platform designed to help shrimp farmers monitor pond conditions automatically using computer vision and smart analytics.

This system receives images and videos directly from Raspberry Pi devices in real environments, analyzes shrimp size, behavior, and abnormal patterns using AI models, and delivers actionable insights through a scalable API.

Built for innovation projects, real farms, and next-generation aquaculture startups.

---

## ⚡ **Core Capabilities**

✨ Real-time shrimp size estimation
🧠 AI detection of floating or abnormal shrimp
🎥 Behavioral analysis from video streams
📡 IoT integration (Raspberry Pi / Edge devices)
💾 Metadata-based local storage system
🔗 Public file access via API endpoints
🚀 Cloud-ready architecture (Railway / Docker)

---

## 🧩 **How It Works**

```
Raspberry Pi Cameras
        ↓
   FastAPI Backend
        ↓
   AI Processing Modules
        ↓
   Output + Metadata Storage
        ↓
   Public File API & App Integration
```

ShrimpSense converts raw pond visuals into structured data that farmers and apps can actually use.

---

## 🏗️ **Project Structure**

```
Backend_Depa/
│
├── Model/              # AI model files
├── process/            # AI analysis modules
├── utils/              # helper utilities
│
├── input_raspi1/       # shrimp size images
├── input_raspi2/       # floating shrimp detection
├── input_video/        # behavior videos
│
├── output/             # processed AI results
├── local_storage/      # metadata & file manager
│
├── main.py             # FastAPI server
├── local_storage.py    # file storage system
├── Dockerfile          # container deployment
```

---

## 📡 **API Overview**

### Analyze Shrimp Size

`POST /analyze/size`

### Detect Floating Shrimp

`POST /analyze/shrimp`

### Analyze Movement Video

`POST /analyze/video`

### Access Generated Files

`GET /files/{file_id}`

---

## 🚀 **Quick Start**

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Development Server

```bash
uvicorn main:app --reload
```

Open browser:

```
http://localhost:8000/docs
```


---

## ☁️ **Cloud Deployment**

ShrimpSense AI backend is optimized for:

* Railway Deployment


---

## 🧠 Tech Stack

<p align="center">

<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
<img src="https://img.shields.io/badge/Python_AI-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/YOLO_Computer_Vision-111111?style=for-the-badge&logo=opencv&logoColor=white"/>
<img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white"/>
<img src="https://img.shields.io/badge/IoT_Integration-FF6F00?style=for-the-badge&logo=raspberrypi&logoColor=white"/>
<img src="https://img.shields.io/badge/Metadata_Storage-0A66C2?style=for-the-badge&logo=databricks&logoColor=white"/>

</p>

---

## 🌱 **Startup Vision**

ShrimpSense AI aims to bring intelligent monitoring to aquaculture by combining:

* Edge AI
* Real-time computer vision
* Cloud APIs
* Smart farming automation

Our goal is to reduce farming risk, improve shrimp survival rates, and help farmers make data-driven decisions.

---


<p align="center">
🚀 Turning shrimp farms into intelligent ecosystems with AI
</p>
