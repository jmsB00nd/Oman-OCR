# **System Architecture & Infrastructure**

### **1\. High-Level Design**

The system consists of multiple containers, orchestrated via Docker Compose. To handle the new requirement of "Batch Processing," we introduce an asynchronous task queue (SQLite-backed for MVP simplicity) that decouples the User Interface from the Inference Engines. This ensures the UI remains responsive under heavy load.

### **2\. The Container Stack**

We will deploy three primary services communicating over a private Docker network.

| Service Name | Technology | Role | Resource Allocation |
| ----- | ----- | ----- | ----- |
| **inference-vision** | vLLM  | **The Eyes:** Extracts raw text from images. | GPU: \~40% VRAM (Device 0\) |
| **inference-text** | vLLM  | **The Brain:** Corrects OCR mistakes. | GPU: \~30% VRAM (Device 0\) |
| **app-core** | Python (FastAPI \+ Streamlit) | **The Controller:** UI, Upload. | CPU Only |

### **3\. GPU Resource Strategy (The RTX 5090 Split)**

Since we are uncertain about specific models, it is best to let the architecture uses **agnostic VRAM partitioning**.

* **Vision Container:** Configured with gpu\_memory\_utilization=0.4.  
* **Text Container:** Configured with gpu\_memory\_utilization=0.3.  
* **Overhead:** 20% reserved for CUDA context switching and burst usage.  
* **Quantization:** Forced AWQ or GPTQ (4-bit) is mandatory for any model \>7B parameters to fit this split.

---

# **Page 2: Backend Logic & Batch Processing Flow**

### **1\. The Asynchronous Queue Mechanism**

Instead of processing images immediately upon upload (which freezes the UI), we use a "Status Polling" pattern.

**Phase A: Ingestion (The Batch Upload)**

1. User drags several images into Streamlit.  
2. **App Core** iterates through the list:  
   * Saves file to disk.  
   * Inserts row into SQLite jobs table:  
   ```json
     {id: UUID, status: "PENDING", original\_filename: "doc1.jpg", created\_at: TIMESTAMP, text:”الاسناد العربیه”}.  
     ```
3. UI immediately confirms: *"\#number files queued."*

**Phase B: The Worker Loop (Background Thread)**

Inside app-core, a dedicated background thread runs continuously:

1. **Fetch:** SELECT \* FROM jobs WHERE status='PENDING' ORDER BY created\_at ASC LIMIT 1.  
2. **Lock:** Update status to "PROCESSING".  
3. **Step 1 (Vision):** Send image to http://inference-vision:8000/v1/chat/completions.  
4. **Step 2 (Text):** Send raw OCR output to http://inference-text:8001/v1/chat/completions for correction.  
5. **Finalize:** Update status to "COMPLETED", save text to DB.  
6. **Loop:** Repeat.

### **2\. API Interface (Internal)**

The app-core does not need a complex REST API for itself; it acts as the client calling the Model APIs.

**Model API Contract (OpenAI Compatible):**

* **Endpoint:** /v1/chat/completions  
* **Vision Payload:**  
* **JSON** 

```json
  {  
  "model": "generic-vision-model",  
  "messages": [  
  {"role": "user", "content": [{"type": "text", "text": "Transcribe Arabic"}, {"type": "image_url", "image_url": {"url": "base64..."}}]}  
   ]  
  }
```

---

# **Page 3: User Interface (Streamlit) & Delivery**

### **1\. UI Layout**

The UI is divided into two distinct tabs to separate "Action" from "Review."

**Tab 1: Batch Ingestion**

* **Widget:** ```st.file\_uploader(accept\_multiple\_files=True)```
* **Feedback:** A dynamic progress bar st.progress() that updates by querying the DB ```(SELECT count(\*) FROM jobs WHERE status='COMPLETED')```.

**Tab 2: Results & History**

* **Layout:** A paginated table or grid.  
* **Display Logic:**  
  * **Left Column:** Thumbnail of the original image.  
  * **Right Column:** The final corrected text (editable st.text\_area).  
* **Ordering:** ORDER BY created\_at DESC (Newest batches first).

### **2\. Docker Compose Configuration Template (The "Run" Script)**

This is the single source of truth for the deployment.

```yaml
services:  
 --- Vision Model Service ---  
  vision-engine:  
    image: vllm/vllm-openai:latest  
    command: --model /models/vision --gpu-memory-utilization 0.5 --port 8000 --quantization awq  
    volumes:  
      - ./models/vision:/models/vision  
    deploy:  
      resources:  
        reservations:  
          devices:  
            \- driver: nvidia  
              count: 1  
              capabilities: \[gpu\]  
    ports:  
      - "8000:8000"

  --- Text Model Service ---  
  text-engine:  
    image: vllm/vllm-openai:latest  
    command: --model /models/text --gpu-memory-utilization 0.3 --port 8001 --quantization awq  
    volumes:  
      - ./models/text:/models/text  
    deploy:  
      resources:  
        reservations:  
          devices:  
            - driver: nvidia  
              count: 1  
              capabilities: \[gpu\]  
    ports:  
      - "8001:8001"

  --- Application Core ---  
  app:  
    build: ./app  
    environment:  
      - VISION\_URL=http://vision-engine:8000/v1  
      - TEXT\_URL=http://text-engine:8001/v1  
      - DB\_PATH=/data/queue.db  
    volumes:  
      - ./data:/data  
    ports:  
      - "8501:8501"  
    depends\_on:  
      - vision-engine  
      - text-engine  
```