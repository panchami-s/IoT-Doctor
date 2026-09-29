# IoT Doctor – Smart IoT Device Troubleshooting Chatbot

## Overview

IoT Doctor is an AI-powered chatbot that helps users identify and troubleshoot common IoT device problems through natural-language interaction.

## Features

- Natural-language IoT issue understanding
- 3-agent AI architecture
- RAG-based knowledge retrieval
- Step-by-step troubleshooting solutions
- Conversational web interface
- IoT-focused troubleshooting knowledge base

## AI Agents

### 1. Issue Understanding Agent
Identifies the IoT device, symptoms, and type of problem from the user's description.

### 2. IoT Knowledge / RAG Agent
Retrieves relevant information from the IoT troubleshooting knowledge base.

### 3. Troubleshooting Agent
Uses the identified issue and retrieved knowledge to generate clear, step-by-step troubleshooting instructions.

## System Flow

User Problem → Issue Understanding → Knowledge Retrieval → Troubleshooting Analysis → Final Solution

## Technology Used

- Python
- Flask
- Groq API
- RAG
- HTML
- CSS
- JavaScript
- Bootstrap 5
- Python-dotenv
- IBM Bob

## Example Problems

- ESP32 not connecting to Wi-Fi
- Ultrasonic sensor not giving readings
- Arduino not detected by the computer
- ESP32 code upload errors
- Sensor configuration and communication issues

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
