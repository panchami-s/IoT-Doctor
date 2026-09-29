import os
import json
import re
from flask import Flask, request, jsonify, session, render_template_string
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "iot-doctor-secret-2024")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "llama3-8b-8192")

# ─────────────────────────────────────────────────────────────────────────────
# BUILT-IN IoT KNOWLEDGE BASE  (RAG source)
# ─────────────────────────────────────────────────────────────────────────────
IOT_KNOWLEDGE_BASE = [
    {
        "id": "esp32_wifi_1",
        "device": "ESP32",
        "category": "connectivity",
        "title": "ESP32 Wi-Fi Not Connecting – SSID/Password Issues",
        "content": (
            "ESP32 Wi-Fi connection failures are most often caused by incorrect SSID or password. "
            "Steps: (1) Double-check the SSID (case-sensitive) and password in your code. "
            "(2) Ensure the router broadcasts on 2.4 GHz – ESP32 does NOT support 5 GHz. "
            "(3) Move the ESP32 closer to the router to rule out range issues. "
            "(4) Call WiFi.disconnect(true) then WiFi.begin(ssid, password) to force a fresh connection. "
            "(5) Add a Serial.print of WiFi.status() in your loop to watch the status codes. "
            "(6) WL_NO_SSID_AVAIL means the network is not found; WL_CONNECT_FAILED means wrong password. "
            "(7) Restart both the ESP32 and router if the problem persists."
        ),
        "keywords": ["esp32", "wifi", "wi-fi", "connect", "ssid", "password", "wireless", "network"]
    },
    {
        "id": "esp32_wifi_2",
        "device": "ESP32",
        "category": "connectivity",
        "title": "ESP32 Wi-Fi Drops / Unstable Connection",
        "content": (
            "Unstable ESP32 Wi-Fi can be caused by power supply issues or interference. "
            "Steps: (1) Use a 5 V / 1 A or better power supply – USB from a computer may be insufficient. "
            "(2) Add a 100 µF capacitor across 3.3 V and GND to stabilise power. "
            "(3) Set a static IP with WiFi.config() to avoid DHCP delays. "
            "(4) Enable the watchdog timer to auto-recover from lockups. "
            "(5) Reduce distance or obstacles between the ESP32 and router. "
            "(6) Avoid placing the ESP32 near metal enclosures or other RF sources."
        ),
        "keywords": ["esp32", "wifi", "drops", "unstable", "disconnect", "reconnect", "power"]
    },
    {
        "id": "esp32_sensor_i2c",
        "device": "ESP32",
        "category": "sensor",
        "title": "ESP32 I2C Sensor Not Responding",
        "content": (
            "I2C sensor communication failures on ESP32 are usually wiring or address issues. "
            "Steps: (1) Verify SDA → GPIO 21 and SCL → GPIO 22 (default ESP32 I2C pins). "
            "(2) Run an I2C scanner sketch to confirm the sensor's address. "
            "(3) Add 4.7 kΩ pull-up resistors on SDA and SCL to 3.3 V. "
            "(4) Check that the sensor is powered from the correct voltage (3.3 V or 5 V as required). "
            "(5) Confirm that the sensor library uses the correct I2C address. "
            "(6) Try Wire.begin(SDA_PIN, SCL_PIN) with explicit pin numbers. "
            "(7) Slow the bus: Wire.setClock(100000) for 100 kHz if the sensor is slow."
        ),
        "keywords": ["esp32", "i2c", "sensor", "sda", "scl", "address", "wire", "communication"]
    },
    {
        "id": "esp32_sensor_spi",
        "device": "ESP32",
        "category": "sensor",
        "title": "ESP32 SPI Sensor/Module Not Working",
        "content": (
            "SPI issues on ESP32 are often pin-mapping or CS-line problems. "
            "Steps: (1) Default VSPI pins: MOSI=23, MISO=19, SCK=18, SS/CS=5. "
            "(2) Make sure the CS pin is driven LOW before and HIGH after each transaction. "
            "(3) Match SPI mode (0–3) to the sensor datasheet. "
            "(4) Ensure the sensor voltage level matches ESP32's 3.3 V logic (use a level shifter for 5 V devices). "
            "(5) Check SPI clock speed – start at 1 MHz and increase if stable."
        ),
        "keywords": ["esp32", "spi", "mosi", "miso", "sck", "cs", "sensor", "module"]
    },
    {
        "id": "esp32_upload",
        "device": "ESP32",
        "category": "firmware",
        "title": "ESP32 Firmware Upload / Flash Error",
        "content": (
            "Common ESP32 upload errors in Arduino IDE or PlatformIO. "
            "Steps: (1) Hold the BOOT button on the ESP32 while clicking Upload, release once upload starts. "
            "(2) Check that the correct COM port is selected in Tools → Port. "
            "(3) Select 'ESP32 Dev Module' (or your exact board) under Tools → Board. "
            "(4) Lower the upload speed: Tools → Upload Speed → 115200. "
            "(5) Install the correct CP2102 or CH340 driver for your USB-UART chip. "
            "(6) Try a different USB cable (many cables are charge-only with no data lines). "
            "(7) Add a 10 µF capacitor between EN and GND for auto-reset on some clone boards."
        ),
        "keywords": ["esp32", "upload", "flash", "firmware", "boot", "com port", "driver", "arduino ide", "error"]
    },
    {
        "id": "arduino_not_detected",
        "device": "Arduino",
        "category": "connectivity",
        "title": "Arduino Not Detected by Computer",
        "content": (
            "Arduino not showing a COM port is nearly always a driver or cable issue. "
            "Steps: (1) Try a different USB cable – many phone cables have no data lines. "
            "(2) Install/reinstall the CH340 driver (clones) or FTDI driver (genuine boards). "
            "(3) Open Device Manager (Windows) and look for 'Unknown Device' under Ports. "
            "(4) On macOS, check System Report → USB for the Arduino. "
            "(5) Restart the IDE after connecting the board. "
            "(6) Try a different USB port on the computer. "
            "(7) On Windows, manually update the driver in Device Manager. "
            "(8) Verify the board is powered (LED should be on)."
        ),
        "keywords": ["arduino", "not detected", "com port", "driver", "usb", "ch340", "ftdi", "device manager"]
    },
    {
        "id": "arduino_upload",
        "device": "Arduino",
        "category": "firmware",
        "title": "Arduino Code Upload Errors",
        "content": (
            "Upload errors on Arduino are typically port, board-selection, or bootloader issues. "
            "Steps: (1) Confirm the correct board is selected: Tools → Board. "
            "(2) Confirm the correct port is selected: Tools → Port. "
            "(3) Press the Reset button on the Arduino just before the IDE shows 'Uploading…'. "
            "(4) Close Serial Monitor – it locks the COM port. "
            "(5) Check that no other program is using the serial port. "
            "(6) If error says 'stk500_recv(): programmer is not responding', try a manual reset. "
            "(7) Reflash the bootloader using another Arduino as ISP if the bootloader is corrupted."
        ),
        "keywords": ["arduino", "upload", "error", "stk500", "programmer", "bootloader", "serial monitor"]
    },
    {
        "id": "ultrasonic_sensor",
        "device": "Ultrasonic Sensor",
        "category": "sensor",
        "title": "HC-SR04 Ultrasonic Sensor Not Giving Readings",
        "content": (
            "HC-SR04 returning 0, negative, or wildly incorrect values. "
            "Steps: (1) Power the HC-SR04 from 5 V (VCC pin), not 3.3 V. "
            "(2) Wire: VCC→5V, GND→GND, Trig→digital pin, Echo→digital pin (use voltage divider for 3.3 V boards). "
            "(3) Send a 10 µs HIGH pulse on Trig, then measure Echo pulse width in microseconds. "
            "(4) Distance (cm) = pulse duration / 58. "
            "(5) Add a 2 ms delay between measurements to allow the sensor to reset. "
            "(6) Minimum range is ~2 cm; objects closer than this cause incorrect readings. "
            "(7) Surfaces at steep angles may not reflect the ultrasonic pulse back."
        ),
        "keywords": ["ultrasonic", "hc-sr04", "sensor", "distance", "trig", "echo", "reading", "zero"]
    },
    {
        "id": "dht_sensor",
        "device": "DHT Sensor",
        "category": "sensor",
        "title": "DHT11/DHT22 Temperature/Humidity Sensor Issues",
        "content": (
            "DHT sensors returning NaN, -999, or wrong values. "
            "Steps: (1) Add a 10 kΩ pull-up resistor between Data and VCC. "
            "(2) DHT11 runs on 3.3–5 V; DHT22 runs on 3.3–5 V. "
            "(3) Wait at least 2 seconds between readings. "
            "(4) Check that you are reading from the correct pin in the library constructor. "
            "(5) Use the latest DHT library (Adafruit DHT Sensor Library). "
            "(6) Long data wires (>20 cm) can cause noise – keep wires short or use shielded cable."
        ),
        "keywords": ["dht", "dht11", "dht22", "temperature", "humidity", "nan", "sensor", "reading"]
    },
    {
        "id": "general_wiring",
        "device": "General",
        "category": "configuration",
        "title": "General Sensor Wiring and Configuration Checklist",
        "content": (
            "Universal checklist for any IoT sensor problem. "
            "(1) Verify VCC and GND connections first – reversed polarity can damage sensors. "
            "(2) Confirm the voltage levels match (3.3 V vs 5 V) – use level shifters where needed. "
            "(3) Check that all GND rails are connected together (common ground). "
            "(4) Use short wires and minimise breadboard connections to reduce resistance. "
            "(5) Read the sensor datasheet for exact pin functions. "
            "(6) Confirm the correct library is installed and the correct pins are set in the sketch. "
            "(7) Use Serial.println() to debug sensor values in real time."
        ),
        "keywords": ["wiring", "sensor", "vcc", "gnd", "voltage", "configuration", "breadboard", "general"]
    },
    {
        "id": "iot_communication",
        "device": "General",
        "category": "communication",
        "title": "IoT Device Communication Failures (MQTT / HTTP)",
        "content": (
            "IoT devices failing to send or receive data over MQTT or HTTP. "
            "Steps: (1) Confirm the device is connected to Wi-Fi first. "
            "(2) For MQTT: check broker IP/hostname, port (1883 default), and credentials. "
            "(3) Verify the topic name matches exactly (case-sensitive). "
            "(4) For HTTP: check the server URL and port; test with a browser or curl. "
            "(5) Ensure the server/broker is reachable from the device's network. "
            "(6) Check for firewall rules blocking the port. "
            "(7) Use a library like PubSubClient for MQTT or HTTPClient for HTTP on ESP32/Arduino."
        ),
        "keywords": ["mqtt", "http", "communication", "broker", "topic", "publish", "subscribe", "iot", "data"]
    },
    {
        "id": "power_issues",
        "device": "General",
        "category": "configuration",
        "title": "IoT Device Power Supply Problems",
        "content": (
            "Insufficient power is a silent killer of IoT projects. "
            "Symptoms: random resets, Wi-Fi not connecting, sensors giving wrong data. "
            "Steps: (1) Use a dedicated 5 V / 2 A adapter instead of a USB computer port. "
            "(2) Add decoupling capacitors (100 nF ceramic + 100 µF electrolytic) near the power pins. "
            "(3) Measure the actual voltage with a multimeter – should be 3.3 V ±0.1 V at the MCU. "
            "(4) If using batteries, check voltage under load. "
            "(5) Avoid powering many sensors from the board's 3.3 V regulator – it is limited to ~200 mA."
        ),
        "keywords": ["power", "supply", "reset", "voltage", "current", "adapter", "battery", "regulator"]
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# GROQ API HELPER
# ─────────────────────────────────────────────────────────────────────────────
def generate_response(messages: list, temperature: float = 0.3) -> str:
    """Call the Groq API and return the assistant's reply as a string."""
    if not GROQ_API_KEY:
        return "ERROR: GROQ_API_KEY is not set. Please add it to your .env file."
    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "invalid_api_key" in error_msg.lower():
            return "ERROR: Invalid or expired GROQ_API_KEY. Please check your .env file."
        if "model" in error_msg.lower():
            return f"ERROR: Model '{GROQ_MODEL}' not found. Check GROQ_MODEL in your .env file."
        return f"ERROR: Groq API call failed – {error_msg}"


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 1 – IoT Issue Understanding Agent
# ─────────────────────────────────────────────────────────────────────────────
def agent_understand_issue(user_message: str, conversation_history: list) -> dict:
    """
    Analyse the user's natural-language IoT problem and return a structured dict
    with device, category, symptoms, and a brief summary.
    """
    system_prompt = """You are an IoT Issue Understanding Agent.
Your job is to analyse the user's IoT problem and extract structured information.

You MUST respond with valid JSON only – no markdown fences, no extra text.

JSON format:
{
  "device": "<identified device, e.g. ESP32, Arduino Uno, HC-SR04, DHT22, or 'Unknown'>",
  "category": "<one of: connectivity, sensor, firmware, communication, configuration, compatibility, unknown>",
  "symptoms": ["<symptom 1>", "<symptom 2>"],
  "summary": "<one sentence summary of the problem>",
  "needs_more_info": <true if you need more info to diagnose, else false>,
  "clarification_question": "<question to ask if needs_more_info is true, else empty string>"
}"""

    recent_history = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
    messages = [{"role": "system", "content": system_prompt}]
    for msg in recent_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    raw = generate_response(messages, temperature=0.1)

    if raw.startswith("ERROR:"):
        return {"error": raw}

    try:
        # Strip markdown fences if the model adds them anyway
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "device": "Unknown",
            "category": "unknown",
            "symptoms": [user_message],
            "summary": user_message,
            "needs_more_info": False,
            "clarification_question": "",
            "parse_warning": "Agent 1 returned non-JSON; used fallback."
        }


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 2 – IoT Knowledge / RAG Agent
# ─────────────────────────────────────────────────────────────────────────────
def agent_retrieve_knowledge(issue_analysis: dict, user_message: str) -> dict:
    """
    Simple keyword-based RAG: score each knowledge-base entry against the
    identified device, category, and raw user message, then return the top matches.
    """
    device   = issue_analysis.get("device", "").lower()
    category = issue_analysis.get("category", "").lower()
    symptoms = " ".join(issue_analysis.get("symptoms", [])).lower()
    query    = f"{device} {category} {symptoms} {user_message.lower()}"

    scored = []
    for entry in IOT_KNOWLEDGE_BASE:
        score = 0
        for kw in entry["keywords"]:
            if kw.lower() in query:
                score += 1
        # Bonus for matching device or category exactly
        if entry["device"].lower() in query:
            score += 2
        if entry["category"].lower() in query:
            score += 1
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_entries = [e for _, e in scored[:3]]

    if not top_entries:
        return {
            "found": False,
            "knowledge_text": "",
            "sources": [],
            "message": "No specific knowledge found in the knowledge base for this issue."
        }

    knowledge_text = "\n\n".join(
        f"[{e['title']}]\n{e['content']}" for e in top_entries
    )
    sources = [e["title"] for e in top_entries]

    return {
        "found": True,
        "knowledge_text": knowledge_text,
        "sources": sources,
        "message": f"{len(top_entries)} relevant knowledge article(s) retrieved."
    }


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 3 – Troubleshooting Agent
# ─────────────────────────────────────────────────────────────────────────────
def agent_troubleshoot(user_message: str, issue_analysis: dict,
                        knowledge: dict, conversation_history: list) -> str:
    """
    Using the structured issue analysis and retrieved knowledge, generate a
    clear, step-by-step troubleshooting response for the user.
    """
    analysis_str = json.dumps(issue_analysis, indent=2)
    knowledge_str = knowledge["knowledge_text"] if knowledge["found"] else "No specific knowledge retrieved."

    system_prompt = f"""You are an expert IoT Troubleshooting Agent helping beginners fix IoT device problems.

You have received:
1. The user's original problem description.
2. A structured analysis from the Issue Understanding Agent.
3. Relevant knowledge retrieved from the IoT knowledge base.

IMPORTANT RULES:
- Use ONLY the provided knowledge and analysis. Do NOT invent technical facts.
- If you cannot diagnose reliably, ask ONE specific clarifying question.
- Never say you tested a physical device – you did not.
- Format your response using the exact structure below.

--- STRUCTURED ANALYSIS ---
{analysis_str}

--- RETRIEVED KNOWLEDGE ---
{knowledge_str}

--- RESPONSE FORMAT (use this exactly) ---
## 🔧 IoT Doctor Diagnosis

**Problem Identified:** <one sentence>
**Device:** <device name>
**Problem Category:** <category>

---

### 🔍 Possible Causes
- Cause 1
- Cause 2
- Cause 3

---

### 🛠️ Troubleshooting Steps
**Step 1:** <action>
**Step 2:** <action>
...

---

### ✅ Expected Result
<what the user should see when the problem is fixed>

---

### 📚 Knowledge / Sources Used
- <source 1>
- <source 2>

---
*Note: This guidance is based on common IoT troubleshooting practices. Always verify connections before powering your device.*
"""

    recent_history = conversation_history[-4:] if len(conversation_history) > 4 else conversation_history
    messages = [{"role": "system", "content": system_prompt}]
    for msg in recent_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    return generate_response(messages, temperature=0.4)


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
def orchestrate(user_message: str, conversation_history: list) -> dict:
    """
    Run: User → Agent 1 (Understand) → Agent 2 (RAG) → Agent 3 (Troubleshoot)
    Returns a dict with the final response and pipeline metadata.
    """
    # Agent 1
    issue_analysis = agent_understand_issue(user_message, conversation_history)
    if "error" in issue_analysis:
        return {"response": issue_analysis["error"], "pipeline": {}}

    # Agent 2
    knowledge = agent_retrieve_knowledge(issue_analysis, user_message)

    # Agent 3
    final_response = agent_troubleshoot(user_message, issue_analysis, knowledge, conversation_history)

    return {
        "response": final_response,
        "pipeline": {
            "agent1": {
                "device": issue_analysis.get("device", "Unknown"),
                "category": issue_analysis.get("category", "unknown"),
                "symptoms": issue_analysis.get("symptoms", []),
                "summary": issue_analysis.get("summary", ""),
            },
            "agent2": {
                "found": knowledge["found"],
                "sources": knowledge["sources"],
                "message": knowledge["message"],
            },
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IoT Doctor – Smart IoT Device Troubleshooting Assistant</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
<style>
  :root {
    --bg: #181a1f;
    --surface: #22252c;
    --surface2: #2a2d36;
    --border: #32363f;
    --text: #e4e6eb;
    --muted: #8b8fa8;
    --accent: #4f8ef7;
    --accent-dim: rgba(79,142,247,0.15);
    --success: #3ecf8e;
    --warning: #f5a623;
    --danger: #f25f5c;
    --radius: 14px;
    --radius-sm: 8px;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 15px;
    line-height: 1.65;
    min-height: 100vh;
  }

  /* ── Navbar ── */
  .navbar {
    background: rgba(24,26,31,0.92) !important;
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    padding: 0.75rem 0;
    position: sticky; top: 0; z-index: 999;
  }
  .navbar-brand {
    font-weight: 700; font-size: 1.2rem; color: var(--accent) !important;
    display: flex; align-items: center; gap: 8px;
  }
  .navbar-brand .logo-icon {
    width: 32px; height: 32px; background: var(--accent);
    border-radius: 8px; display: flex; align-items: center; justify-content: center;
    font-size: 16px; color: #fff;
  }
  .nav-link { color: var(--muted) !important; font-weight: 500; transition: color .2s; }
  .nav-link:hover, .nav-link.active { color: var(--text) !important; }
  .navbar-toggler { border-color: var(--border); }
  .navbar-toggler-icon { filter: invert(1) brightness(.6); }

  /* ── Pages ── */
  .page { display: none; }
  .page.active { display: block; }

  /* ── Hero ── */
  .hero {
    background: linear-gradient(135deg, #1a1d24 0%, #1e2230 100%);
    border-bottom: 1px solid var(--border);
    padding: 5rem 0 4rem;
    text-align: center;
  }
  .hero-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--accent-dim); border: 1px solid var(--accent);
    color: var(--accent); font-size: .78rem; font-weight: 600;
    padding: 4px 14px; border-radius: 50px; margin-bottom: 1.5rem;
    letter-spacing: .04em; text-transform: uppercase;
  }
  .hero h1 { font-size: clamp(2rem, 5vw, 3.2rem); font-weight: 800; line-height: 1.2; }
  .hero h1 span { color: var(--accent); }
  .hero p.lead { color: var(--muted); max-width: 560px; margin: 1rem auto 2rem; font-size: 1.05rem; }
  .btn-primary-custom {
    background: var(--accent); border: none; color: #fff;
    padding: .65rem 1.8rem; border-radius: var(--radius-sm);
    font-weight: 600; font-size: .95rem; cursor: pointer;
    transition: opacity .2s, transform .15s;
  }
  .btn-primary-custom:hover { opacity: .88; transform: translateY(-1px); }
  .btn-outline-custom {
    background: transparent; border: 1px solid var(--border); color: var(--text);
    padding: .65rem 1.8rem; border-radius: var(--radius-sm);
    font-weight: 500; cursor: pointer; transition: border-color .2s, color .2s;
  }
  .btn-outline-custom:hover { border-color: var(--accent); color: var(--accent); }

  /* ── Cards ── */
  .card-dark {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
  }
  .card-dark-sm {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 1.25rem;
  }

  /* ── Section titles ── */
  .section-title { font-size: 1.5rem; font-weight: 700; margin-bottom: .4rem; }
  .section-sub { color: var(--muted); margin-bottom: 2rem; }

  /* ── Workflow steps ── */
  .workflow-steps {
    display: flex; flex-wrap: wrap; gap: 0; justify-content: center; align-items: center;
  }
  .workflow-step {
    text-align: center; padding: 1rem .5rem; flex: 1; min-width: 130px; max-width: 160px;
  }
  .step-icon {
    width: 52px; height: 52px; border-radius: 50%;
    background: var(--accent-dim); border: 2px solid var(--accent);
    color: var(--accent); display: flex; align-items: center; justify-content: center;
    font-size: 1.3rem; margin: 0 auto .75rem;
  }
  .step-label { font-size: .78rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
  .step-title { font-size: .92rem; font-weight: 700; margin-top: .2rem; }
  .workflow-arrow { color: var(--border); font-size: 1.5rem; flex-shrink: 0; padding: 0 .25rem; margin-top: -28px; }

  /* ── Agent cards ── */
  .agent-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    height: 100%;
    transition: border-color .2s;
  }
  .agent-card:hover { border-color: var(--accent); }
  .agent-num {
    width: 32px; height: 32px; border-radius: 50%;
    background: var(--accent); color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: .9rem; margin-bottom: 1rem;
  }
  .agent-card h5 { font-size: 1rem; font-weight: 700; margin-bottom: .5rem; }
  .agent-card p { color: var(--muted); font-size: .88rem; line-height: 1.55; }

  /* ── Device tags ── */
  .tag {
    display: inline-block;
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--muted); font-size: .78rem; font-weight: 600;
    padding: 4px 12px; border-radius: 50px;
  }

  /* ── Chat page ── */
  .chat-layout { display: flex; gap: 1.25rem; align-items: flex-start; }
  .chat-sidebar {
    width: 280px; flex-shrink: 0;
    position: sticky; top: 80px;
  }
  .chat-main { flex: 1; min-width: 0; }

  /* Chat window */
  .chat-window {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    display: flex; flex-direction: column;
    height: calc(100vh - 180px);
    min-height: 480px;
  }
  .chat-header {
    padding: .9rem 1.25rem;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
  }
  .chat-header-left { display: flex; align-items: center; gap: 10px; }
  .online-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); }
  .chat-header h6 { margin: 0; font-weight: 700; font-size: .95rem; }
  .chat-header small { color: var(--muted); font-size: .78rem; }
  .btn-clear {
    background: transparent; border: 1px solid var(--border); color: var(--muted);
    padding: 4px 12px; border-radius: var(--radius-sm); font-size: .8rem;
    cursor: pointer; transition: border-color .2s, color .2s;
  }
  .btn-clear:hover { border-color: var(--danger); color: var(--danger); }

  /* Messages */
  .chat-messages {
    flex: 1; overflow-y: auto; padding: 1.25rem;
    display: flex; flex-direction: column; gap: 1rem;
    scroll-behavior: smooth;
  }
  .chat-messages::-webkit-scrollbar { width: 5px; }
  .chat-messages::-webkit-scrollbar-track { background: transparent; }
  .chat-messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .msg-row { display: flex; gap: 10px; max-width: 90%; }
  .msg-row.user { margin-left: auto; flex-direction: row-reverse; }
  .msg-avatar {
    width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: .9rem; font-weight: 700;
  }
  .msg-avatar.bot { background: var(--accent); color: #fff; }
  .msg-avatar.user { background: #3a3d48; color: var(--text); }

  .msg-bubble {
    padding: .75rem 1rem; border-radius: 14px;
    font-size: .9rem; line-height: 1.6; max-width: 100%;
  }
  .msg-bubble.bot {
    background: var(--surface2); border: 1px solid var(--border);
    border-bottom-left-radius: 4px;
  }
  .msg-bubble.user {
    background: var(--accent); color: #fff;
    border-bottom-right-radius: 4px;
  }
  .msg-bubble.error {
    background: rgba(242,95,92,.12); border: 1px solid var(--danger);
    color: var(--danger);
  }

  /* Markdown-like styling inside bot bubbles */
  .msg-bubble h2 { font-size: 1rem; font-weight: 700; margin: .75rem 0 .4rem; color: var(--accent); }
  .msg-bubble h3 { font-size: .92rem; font-weight: 700; margin: .6rem 0 .3rem; }
  .msg-bubble strong { color: var(--text); }
  .msg-bubble ul { padding-left: 1.2rem; margin: .3rem 0; }
  .msg-bubble li { margin-bottom: .2rem; }
  .msg-bubble hr { border-color: var(--border); margin: .75rem 0; }
  .msg-bubble p { margin-bottom: .3rem; }
  .msg-bubble em { color: var(--muted); font-size: .85rem; }

  /* Typing indicator */
  .typing-indicator {
    display: flex; align-items: center; gap: 5px;
    padding: .75rem 1rem;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 14px; border-bottom-left-radius: 4px;
    width: fit-content;
  }
  .typing-dot {
    width: 7px; height: 7px; border-radius: 50%; background: var(--muted);
    animation: bounce .9s infinite;
  }
  .typing-dot:nth-child(2) { animation-delay: .15s; }
  .typing-dot:nth-child(3) { animation-delay: .3s; }
  @keyframes bounce {
    0%, 80%, 100% { transform: translateY(0); }
    40% { transform: translateY(-6px); }
  }

  /* Input area */
  .chat-input-area {
    padding: 1rem 1.25rem;
    border-top: 1px solid var(--border);
    display: flex; gap: 10px; align-items: flex-end;
  }
  .chat-input {
    flex: 1; background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); border-radius: var(--radius-sm);
    padding: .65rem 1rem; font-size: .9rem;
    resize: none; outline: none; transition: border-color .2s;
    font-family: inherit; max-height: 120px;
  }
  .chat-input:focus { border-color: var(--accent); }
  .chat-input::placeholder { color: var(--muted); }
  .send-btn {
    background: var(--accent); border: none; color: #fff;
    width: 42px; height: 42px; border-radius: var(--radius-sm);
    cursor: pointer; display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; transition: opacity .2s; flex-shrink: 0;
  }
  .send-btn:hover { opacity: .85; }
  .send-btn:disabled { opacity: .4; cursor: not-allowed; }

  /* Quick buttons */
  .quick-btn {
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); padding: .45rem .9rem; border-radius: var(--radius-sm);
    font-size: .8rem; cursor: pointer; transition: border-color .2s, color .2s;
    text-align: left; width: 100%;
    display: flex; align-items: center; gap: 8px;
  }
  .quick-btn:hover { border-color: var(--accent); color: var(--accent); }

  /* Pipeline panel */
  .pipeline-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem;
    margin-top: 1.25rem;
    font-size: .82rem;
  }
  .pipeline-panel h6 { font-size: .82rem; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: .75rem; }
  .pipeline-step {
    display: flex; align-items: flex-start; gap: 8px; margin-bottom: .6rem;
  }
  .pipeline-step-icon {
    width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; margin-top: 1px;
    display: flex; align-items: center; justify-content: center; font-size: .7rem; font-weight: 700;
  }
  .ps-1 { background: rgba(79,142,247,.2); color: var(--accent); }
  .ps-2 { background: rgba(62,207,142,.2); color: var(--success); }
  .ps-3 { background: rgba(245,166,35,.2); color: var(--warning); }
  .pipeline-step-body { flex: 1; }
  .pipeline-step-title { font-weight: 700; color: var(--text); }
  .pipeline-step-detail { color: var(--muted); }

  /* KB page */
  .kb-entry {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem;
    margin-bottom: 1rem;
    cursor: pointer;
    transition: border-color .2s;
  }
  .kb-entry:hover { border-color: var(--accent); }
  .kb-entry h6 { font-weight: 700; margin-bottom: .3rem; }
  .kb-entry p { color: var(--muted); font-size: .85rem; margin: 0; }
  .kb-content { display: none; margin-top: .75rem; color: var(--text); font-size: .88rem; line-height: 1.65; }
  .kb-content.open { display: block; }
  .kb-badge {
    font-size: .72rem; font-weight: 600; padding: 2px 10px; border-radius: 50px;
    background: var(--accent-dim); border: 1px solid var(--accent); color: var(--accent);
    margin-right: 6px;
  }
  .kb-badge.sensor { background: rgba(62,207,142,.12); border-color: var(--success); color: var(--success); }
  .kb-badge.firmware { background: rgba(245,166,35,.12); border-color: var(--warning); color: var(--warning); }
  .kb-badge.config { background: rgba(124,84,204,.15); border-color: #7c54cc; color: #a07de0; }
  .kb-badge.communication { background: rgba(242,95,92,.12); border-color: var(--danger); color: var(--danger); }

  /* About */
  .about-section { margin-bottom: 2.5rem; }
  .about-section h5 { font-weight: 700; margin-bottom: .75rem; color: var(--accent); }
  .about-section p, .about-section li { color: var(--muted); font-size: .92rem; }
  .about-section ul { padding-left: 1.3rem; }
  .about-section ul li { margin-bottom: .3rem; }
  .limitation-box {
    background: rgba(242,95,92,.08); border: 1px solid rgba(242,95,92,.35);
    border-radius: var(--radius-sm); padding: 1rem 1.25rem;
    color: #f88; font-size: .88rem;
  }

  /* Footer */
  footer {
    border-top: 1px solid var(--border);
    padding: 1.5rem 0;
    text-align: center;
    color: var(--muted);
    font-size: .82rem;
    margin-top: 3rem;
  }

  /* Utilities */
  .text-accent { color: var(--accent); }
  .text-muted-c { color: var(--muted); }
  .text-success-c { color: var(--success); }
  .text-warning-c { color: var(--warning); }
  .page-section { padding: 3rem 0; }

  @media (max-width: 768px) {
    .chat-layout { flex-direction: column; }
    .chat-sidebar { width: 100%; position: static; }
    .chat-window { height: 60vh; min-height: 400px; }
    .workflow-arrow { display: none; }
  }
</style>
</head>
<body>

<!-- ── NAVBAR ── -->
<nav class="navbar navbar-expand-lg">
  <div class="container">
    <a class="navbar-brand" href="#" onclick="showPage('home')">
      <div class="logo-icon"><i class="bi bi-cpu"></i></div>
      IoT Doctor
    </a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navMenu">
      <ul class="navbar-nav ms-auto gap-1">
        <li class="nav-item"><a class="nav-link active" id="nav-home" href="#" onclick="showPage('home')">Home</a></li>
        <li class="nav-item"><a class="nav-link" id="nav-chat" href="#" onclick="showPage('chat')">Troubleshooting Chat</a></li>
        <li class="nav-item"><a class="nav-link" id="nav-kb" href="#" onclick="showPage('kb')">Knowledge Base</a></li>
        <li class="nav-item"><a class="nav-link" id="nav-about" href="#" onclick="showPage('about')">About</a></li>
      </ul>
    </div>
  </div>
</nav>

<!-- ═══════════════════════════════════════════════
     PAGE: HOME
═══════════════════════════════════════════════ -->
<div id="page-home" class="page active">
  <!-- Hero -->
  <section class="hero">
    <div class="container">
      <div class="hero-badge"><i class="bi bi-stars"></i> AI-Powered · 3-Agent System</div>
      <h1>IoT <span>Doctor</span></h1>
      <p class="lead">Smart IoT Device Troubleshooting Assistant — diagnose your ESP32, Arduino, and sensor issues through natural-language conversation.</p>
      <div class="d-flex gap-3 justify-content-center flex-wrap">
        <button class="btn-primary-custom" onclick="showPage('chat')"><i class="bi bi-chat-dots me-2"></i>Start Troubleshooting</button>
        <button class="btn-outline-custom" onclick="showPage('about')"><i class="bi bi-info-circle me-2"></i>How It Works</button>
      </div>
    </div>
  </section>

  <div class="container">
    <!-- Workflow -->
    <section class="page-section">
      <div class="text-center mb-4">
        <div class="section-title">How It Works</div>
        <div class="section-sub">Three specialised AI agents work together to diagnose your IoT problem</div>
      </div>
      <div class="card-dark">
        <div class="workflow-steps">
          <div class="workflow-step">
            <div class="step-icon"><i class="bi bi-chat-text"></i></div>
            <div class="step-label">Step 1</div>
            <div class="step-title">Describe Problem</div>
          </div>
          <div class="workflow-arrow"><i class="bi bi-arrow-right"></i></div>
          <div class="workflow-step">
            <div class="step-icon"><i class="bi bi-search"></i></div>
            <div class="step-label">Agent 1</div>
            <div class="step-title">Understand Issue</div>
          </div>
          <div class="workflow-arrow"><i class="bi bi-arrow-right"></i></div>
          <div class="workflow-step">
            <div class="step-icon"><i class="bi bi-database"></i></div>
            <div class="step-label">Agent 2</div>
            <div class="step-title">Retrieve Knowledge</div>
          </div>
          <div class="workflow-arrow"><i class="bi bi-arrow-right"></i></div>
          <div class="workflow-step">
            <div class="step-icon"><i class="bi bi-wrench"></i></div>
            <div class="step-label">Agent 3</div>
            <div class="step-title">Diagnose & Solve</div>
          </div>
          <div class="workflow-arrow"><i class="bi bi-arrow-right"></i></div>
          <div class="workflow-step">
            <div class="step-icon"><i class="bi bi-check-circle"></i></div>
            <div class="step-label">Result</div>
            <div class="step-title">Step-by-step Fix</div>
          </div>
        </div>
      </div>
    </section>

    <!-- 3 Agent Cards -->
    <section class="page-section pt-0">
      <div class="text-center mb-4">
        <div class="section-title">The 3-Agent Architecture</div>
        <div class="section-sub">Each agent has a specific role — together they deliver reliable troubleshooting</div>
      </div>
      <div class="row g-3">
        <div class="col-md-4">
          <div class="agent-card">
            <div class="agent-num">1</div>
            <h5><i class="bi bi-search me-2 text-accent"></i>Issue Understanding Agent</h5>
            <p>Parses your natural-language description to identify the device, problem category, and key symptoms. Returns a structured analysis for the next agent.</p>
          </div>
        </div>
        <div class="col-md-4">
          <div class="agent-card">
            <div class="agent-num">2</div>
            <h5><i class="bi bi-database me-2 text-accent"></i>Knowledge / RAG Agent</h5>
            <p>Searches the built-in IoT knowledge base using a Retrieval-Augmented Generation (RAG) approach to find the most relevant technical articles for your issue.</p>
          </div>
        </div>
        <div class="col-md-4">
          <div class="agent-card">
            <div class="agent-num">3</div>
            <h5><i class="bi bi-wrench me-2 text-accent"></i>Troubleshooting Agent</h5>
            <p>Combines the structured analysis and retrieved knowledge to generate clear, beginner-friendly, step-by-step troubleshooting instructions with expected outcomes.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Devices & Categories -->
    <section class="page-section pt-0">
      <div class="row g-4">
        <div class="col-md-6">
          <div class="card-dark h-100">
            <h5 class="mb-3"><i class="bi bi-cpu me-2 text-accent"></i>Supported Devices</h5>
            <div class="d-flex flex-wrap gap-2">
              <span class="tag">ESP32</span><span class="tag">Arduino Uno/Mega</span>
              <span class="tag">Arduino Nano</span><span class="tag">HC-SR04 Ultrasonic</span>
              <span class="tag">DHT11 / DHT22</span><span class="tag">I2C Sensors</span>
              <span class="tag">SPI Modules</span><span class="tag">Wi-Fi IoT Devices</span>
            </div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="card-dark h-100">
            <h5 class="mb-3"><i class="bi bi-list-check me-2 text-accent"></i>Troubleshooting Categories</h5>
            <div class="d-flex flex-wrap gap-2">
              <span class="tag">Wi-Fi Connectivity</span><span class="tag">Sensor Readings</span>
              <span class="tag">Firmware Upload</span><span class="tag">Device Detection</span>
              <span class="tag">I2C / SPI Comms</span><span class="tag">Wiring & Config</span>
              <span class="tag">MQTT / HTTP</span><span class="tag">Power Issues</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>

  <footer>
    <div class="container">
      IoT Doctor · Smart IoT Troubleshooting Assistant · Powered by Groq &amp; LLaMA 3
    </div>
  </footer>
</div>

<!-- ═══════════════════════════════════════════════
     PAGE: CHAT
═══════════════════════════════════════════════ -->
<div id="page-chat" class="page">
  <div class="container py-4">
    <div class="chat-layout">

      <!-- Sidebar -->
      <div class="chat-sidebar">
        <div class="card-dark mb-3">
          <h6 style="font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:.9rem;">⚡ Quick Problems</h6>
          <div class="d-flex flex-column gap-2">
            <button class="quick-btn" onclick="setQuickMessage('My ESP32 is not connecting to Wi-Fi. I have entered the correct SSID and password but it keeps failing to connect.')">
              <i class="bi bi-wifi-off text-accent"></i> ESP32 Wi-Fi Issue
            </button>
            <button class="quick-btn" onclick="setQuickMessage('My ultrasonic sensor HC-SR04 is not giving any distance readings. It just returns 0 or garbage values.')">
              <i class="bi bi-broadcast text-success-c"></i> Sensor Not Working
            </button>
            <button class="quick-btn" onclick="setQuickMessage('My Arduino Uno is not being detected by my computer. No COM port appears in the Arduino IDE.')">
              <i class="bi bi-usb-symbol text-warning-c"></i> Arduino Not Detected
            </button>
            <button class="quick-btn" onclick="setQuickMessage('I am getting an error while uploading code to my ESP32. The IDE shows a timeout or connection error during upload.')">
              <i class="bi bi-exclamation-triangle text-accent"></i> Firmware Upload Error
            </button>
          </div>
        </div>

        <!-- Pipeline panel -->
        <div class="pipeline-panel" id="pipeline-panel" style="display:none;">
          <h6>Agent Pipeline</h6>
          <div id="pipeline-content"></div>
        </div>
      </div>

      <!-- Main chat -->
      <div class="chat-main">
        <div class="chat-window">
          <div class="chat-header">
            <div class="chat-header-left">
              <div class="online-dot"></div>
              <div>
                <h6>IoT Doctor</h6>
                <small>Smart Troubleshooting Assistant</small>
              </div>
            </div>
            <button class="btn-clear" onclick="clearChat()"><i class="bi bi-trash me-1"></i>Clear</button>
          </div>

          <div class="chat-messages" id="chatMessages">
            <!-- Welcome message -->
            <div class="msg-row">
              <div class="msg-avatar bot"><i class="bi bi-cpu"></i></div>
              <div class="msg-bubble bot">
                <strong>Hello! I'm IoT Doctor 👋</strong><br><br>
                I use <strong>3 AI agents</strong> to diagnose your IoT device problems:<br>
                <ul style="margin-top:.5rem;">
                  <li><strong>Agent 1</strong> – Understands your issue</li>
                  <li><strong>Agent 2</strong> – Retrieves relevant knowledge (RAG)</li>
                  <li><strong>Agent 3</strong> – Generates step-by-step fixes</li>
                </ul>
                <br>
                Describe your IoT problem or use a <strong>Quick Problem</strong> button to get started.
              </div>
            </div>
          </div>

          <div class="chat-input-area">
            <textarea class="chat-input" id="chatInput" rows="1"
              placeholder="Describe your IoT problem… (e.g. My ESP32 won't connect to Wi-Fi)"
              onkeydown="handleKeyDown(event)"
              oninput="autoResize(this)"></textarea>
            <button class="send-btn" id="sendBtn" onclick="sendMessage()" title="Send">
              <i class="bi bi-send"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════
     PAGE: KNOWLEDGE BASE
═══════════════════════════════════════════════ -->
<div id="page-kb" class="page">
  <div class="container py-5">
    <div class="section-title mb-1">Knowledge Base</div>
    <div class="section-sub">Built-in IoT troubleshooting articles used by the RAG Agent</div>

    <div id="kb-list">
      <!-- Populated by JS -->
    </div>
  </div>
  <footer><div class="container">IoT Doctor · Smart IoT Troubleshooting Assistant · Powered by Groq &amp; LLaMA 3</div></footer>
</div>

<!-- ═══════════════════════════════════════════════
     PAGE: ABOUT
═══════════════════════════════════════════════ -->
<div id="page-about" class="page">
  <div class="container py-5" style="max-width:780px;">
    <div class="section-title mb-1">About IoT Doctor</div>
    <div class="section-sub mb-4">An AI-powered multi-agent IoT troubleshooting system</div>

    <div class="about-section">
      <h5><i class="bi bi-question-circle me-2"></i>What is IoT Doctor?</h5>
      <p>IoT Doctor is an AI-powered chatbot that helps students, hobbyists, and engineers diagnose and fix common IoT device problems. Instead of searching scattered forums and documentation, you describe your problem in plain English and IoT Doctor guides you through a systematic fix.</p>
    </div>

    <div class="about-section">
      <h5><i class="bi bi-exclamation-triangle me-2"></i>Why is IoT Troubleshooting Difficult?</h5>
      <ul>
        <li>IoT systems combine hardware, firmware, and network layers — a single fault can look like many different problems.</li>
        <li>Error messages are often cryptic or absent.</li>
        <li>Beginners lack structured mental models for systematic debugging.</li>
        <li>Documentation is spread across datasheets, forums, and vendor sites.</li>
        <li>Physical testing is needed but not always possible.</li>
      </ul>
    </div>

    <div class="about-section">
      <h5><i class="bi bi-diagram-3 me-2"></i>How the 3-Agent System Works</h5>
      <div class="row g-3 mt-1">
        <div class="col-12">
          <div class="card-dark-sm">
            <strong class="text-accent">Agent 1 – Issue Understanding Agent</strong>
            <p style="color:var(--muted);font-size:.88rem;margin-top:.4rem;">Receives the raw natural-language problem description and uses an LLM to extract the device type, problem category, and key symptoms into a structured JSON object.</p>
          </div>
        </div>
        <div class="col-12">
          <div class="card-dark-sm">
            <strong class="text-accent">Agent 2 – Knowledge / RAG Agent</strong>
            <p style="color:var(--muted);font-size:.88rem;margin-top:.4rem;">Implements a simple Retrieval-Augmented Generation approach: keywords from the structured analysis are scored against the built-in knowledge base and the top-matching articles are retrieved. This grounds the final response in factual technical content.</p>
          </div>
        </div>
        <div class="col-12">
          <div class="card-dark-sm">
            <strong class="text-accent">Agent 3 – Troubleshooting Agent</strong>
            <p style="color:var(--muted);font-size:.88rem;margin-top:.4rem;">Receives the original problem, the structured analysis from Agent 1, and the retrieved knowledge from Agent 2. The LLM synthesises these into a structured diagnosis with possible causes, step-by-step instructions, and expected outcome.</p>
          </div>
        </div>
      </div>
    </div>

    <div class="about-section">
      <h5><i class="bi bi-database me-2"></i>How RAG is Used</h5>
      <p>Retrieval-Augmented Generation (RAG) means the AI does not rely solely on its training data. Before generating a response, Agent 2 retrieves relevant articles from the built-in knowledge base and injects them into the prompt. This ensures the advice is grounded in specific, accurate technical content rather than hallucinated facts.</p>
    </div>

    <div class="about-section">
      <h5><i class="bi bi-lightning me-2"></i>How Groq is Used</h5>
      <p>All three agents use the <strong>Groq API</strong> with a free open-source LLM (LLaMA 3). Groq provides extremely fast inference, making the multi-agent pipeline respond quickly. The API key is stored in an environment variable and never hardcoded.</p>
    </div>

    <div class="about-section">
      <h5><i class="bi bi-shield-exclamation me-2"></i>Important Limitation</h5>
      <div class="limitation-box">
        <strong>⚠️ IoT Doctor provides guidance only.</strong> It does not physically test your hardware, measure voltages, or verify wiring. All troubleshooting steps are based on common patterns and the built-in knowledge base. Always verify your connections and consult your component's datasheet for authoritative specifications.
      </div>
    </div>
  </div>
  <footer><div class="container">IoT Doctor · Smart IoT Troubleshooting Assistant · Powered by Groq &amp; LLaMA 3</div></footer>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
<script>
// ── Page navigation ──────────────────────────────────────────
function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.getElementById('nav-' + name).classList.add('active');
  window.scrollTo(0, 0);
  if (name === 'kb') buildKB();
}

// ── Knowledge Base ────────────────────────────────────────────
const KB_DATA = {{ kb_data | tojson }};

function catClass(cat) {
  const m = { connectivity:'', sensor:'sensor', firmware:'firmware', communication:'communication', configuration:'config' };
  return m[cat] || '';
}
function catLabel(cat) {
  return cat.charAt(0).toUpperCase() + cat.slice(1);
}

function buildKB() {
  const list = document.getElementById('kb-list');
  if (list.dataset.built) return;
  list.dataset.built = '1';
  list.innerHTML = KB_DATA.map((entry, i) => `
    <div class="kb-entry" onclick="toggleKB(${i})">
      <div class="d-flex align-items-start justify-content-between gap-2">
        <div>
          <span class="kb-badge ${catClass(entry.category)}">${catLabel(entry.category)}</span>
          <span class="kb-badge" style="background:var(--surface2);border-color:var(--border);color:var(--muted);">${entry.device}</span>
          <h6 class="mt-2 mb-1">${entry.title}</h6>
          <p>${entry.content.slice(0, 90)}…</p>
        </div>
        <i class="bi bi-chevron-down text-muted-c" id="kb-chevron-${i}" style="flex-shrink:0;margin-top:4px;"></i>
      </div>
      <div class="kb-content" id="kb-content-${i}">${entry.content}</div>
    </div>
  `).join('');
}

function toggleKB(i) {
  const el = document.getElementById('kb-content-' + i);
  const ch = document.getElementById('kb-chevron-' + i);
  el.classList.toggle('open');
  ch.className = el.classList.contains('open')
    ? 'bi bi-chevron-up text-accent'
    : 'bi bi-chevron-down text-muted-c';
}

// ── Chat ──────────────────────────────────────────────────────
let isLoading = false;

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

function setQuickMessage(msg) {
  const input = document.getElementById('chatInput');
  input.value = msg;
  autoResize(input);
  input.focus();
}

function scrollToBottom() {
  const el = document.getElementById('chatMessages');
  el.scrollTop = el.scrollHeight;
}

function appendMessage(role, html, extraClass) {
  const container = document.getElementById('chatMessages');
  const row = document.createElement('div');
  row.className = 'msg-row' + (role === 'user' ? ' user' : '');

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar ' + (role === 'user' ? 'user' : 'bot');
  avatar.innerHTML = role === 'user' ? '<i class="bi bi-person"></i>' : '<i class="bi bi-cpu"></i>';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble ' + (role === 'user' ? 'user' : (extraClass || 'bot'));
  bubble.innerHTML = html;

  row.appendChild(avatar);
  row.appendChild(bubble);
  container.appendChild(row);
  scrollToBottom();
  return bubble;
}

function showTyping() {
  const container = document.getElementById('chatMessages');
  const row = document.createElement('div');
  row.className = 'msg-row';
  row.id = 'typing-row';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar bot';
  avatar.innerHTML = '<i class="bi bi-cpu"></i>';

  const indicator = document.createElement('div');
  indicator.className = 'typing-indicator';
  indicator.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';

  row.appendChild(avatar);
  row.appendChild(indicator);
  container.appendChild(row);
  scrollToBottom();
}

function removeTyping() {
  const el = document.getElementById('typing-row');
  if (el) el.remove();
}

function markdownToHTML(text) {
  // Very lightweight markdown → HTML converter for bot bubbles
  return text
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/[*][*](.+?)[*][*]/g, '<strong>$1</strong>')
    .replace(/[*](.+?)[*]/g, '<em>$1</em>')
    .replace(/^---$/gm, '<hr>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<[/]li>\n?)+/g, m => '<ul>' + m + '<\/ul>')
    .replace(/\n{2,}/g, '<\/p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^(?!<)(.+)$/gm, '<p>$1<\/p>')
    .replace(/<p><\/p>/g, '');
}

function updatePipeline(pipeline) {
  const panel = document.getElementById('pipeline-panel');
  const content = document.getElementById('pipeline-content');
  if (!pipeline || !pipeline.agent1) { panel.style.display = 'none'; return; }

  const a1 = pipeline.agent1;
  const a2 = pipeline.agent2;

  const symptomsHTML = a1.symptoms && a1.symptoms.length
    ? a1.symptoms.map(s => `<span class="tag" style="font-size:.72rem;">${s}</span>`).join(' ')
    : '<span style="color:var(--muted)">None extracted</span>';

  const sourcesHTML = a2.sources && a2.sources.length
    ? a2.sources.map(s => `<div style="color:var(--muted)">${s}</div>`).join('')
    : '<div style="color:var(--muted)">None found</div>';

  content.innerHTML = `
    <div class="pipeline-step">
      <div class="pipeline-step-icon ps-1">1</div>
      <div class="pipeline-step-body">
        <div class="pipeline-step-title">Issue Understanding</div>
        <div class="pipeline-step-detail">Device: <strong>${a1.device}</strong></div>
        <div class="pipeline-step-detail">Category: <strong>${a1.category}</strong></div>
        <div class="pipeline-step-detail mt-1">${symptomsHTML}</div>
      </div>
    </div>
    <div class="pipeline-step">
      <div class="pipeline-step-icon ps-2">2</div>
      <div class="pipeline-step-body">
        <div class="pipeline-step-title">RAG Knowledge</div>
        <div class="pipeline-step-detail">${a2.message}</div>
        <div class="pipeline-step-detail mt-1">${sourcesHTML}</div>
      </div>
    </div>
    <div class="pipeline-step">
      <div class="pipeline-step-icon ps-3">3</div>
      <div class="pipeline-step-body">
        <div class="pipeline-step-title">Troubleshooting Agent</div>
        <div class="pipeline-step-detail" style="color:var(--success);">✔ Response generated</div>
      </div>
    </div>
  `;
  panel.style.display = 'block';
}

async function sendMessage() {
  if (isLoading) return;
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return;

  input.value = '';
  input.style.height = 'auto';
  document.getElementById('sendBtn').disabled = true;
  isLoading = true;

  appendMessage('user', escapeHTML(msg));
  showTyping();

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    removeTyping();

    if (data.error) {
      appendMessage('bot', '<i class="bi bi-exclamation-triangle me-2"></i>' + escapeHTML(data.error), 'error');
    } else {
      const html = markdownToHTML(data.response || 'No response received.');
      appendMessage('bot', html);
      updatePipeline(data.pipeline);
    }
  } catch (err) {
    removeTyping();
    appendMessage('bot', '<i class="bi bi-exclamation-triangle me-2"></i>Network error. Please try again.', 'error');
  }

  document.getElementById('sendBtn').disabled = false;
  isLoading = false;
}

function clearChat() {
  const container = document.getElementById('chatMessages');
  container.innerHTML = `
    <div class="msg-row">
      <div class="msg-avatar bot"><i class="bi bi-cpu"></i></div>
      <div class="msg-bubble bot">
        Chat cleared. How can I help you with your IoT device today?
      </div>
    </div>`;
  document.getElementById('pipeline-panel').style.display = 'none';
  fetch('/clear', { method: 'POST' });
}

function escapeHTML(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    kb_data = [
        {
            "id": e["id"],
            "device": e["device"],
            "category": e["category"],
            "title": e["title"],
            "content": e["content"],
        }
        for e in IOT_KNOWLEDGE_BASE
    ]
    return render_template_string(HTML_TEMPLATE, kb_data=kb_data)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not data or not data.get("message", "").strip():
        return jsonify({"error": "Please enter a message."}), 400

    user_message = data["message"].strip()

    if not GROQ_API_KEY:
        return jsonify({"error": "GROQ_API_KEY is not configured. Add it to your .env file."}), 500

    if "history" not in session:
        session["history"] = []

    history = session["history"]

    result = orchestrate(user_message, history)

    # Persist to session (keep last 10 turns to stay within context limits)
    history.append({"role": "user", "content": user_message})
    if not result["response"].startswith("ERROR:"):
        history.append({"role": "assistant", "content": result["response"]})
    session["history"] = history[-10:]

    if result["response"].startswith("ERROR:"):
        return jsonify({"error": result["response"]}), 500

    return jsonify({
        "response": result["response"],
        "pipeline": result.get("pipeline", {}),
    })


@app.route("/clear", methods=["POST"])
def clear_session():
    session.pop("history", None)
    return jsonify({"status": "cleared"})


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not GROQ_API_KEY:
        print("⚠️  WARNING: GROQ_API_KEY is not set. Add it to a .env file before chatting.")
    print("🩺 IoT Doctor starting at http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
