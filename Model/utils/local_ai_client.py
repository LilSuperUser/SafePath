# Model/utils/local_ai_client.py
import os
import re

# Flag: Enable local LLM only when explicitly turned on
USE_LOCAL_AI = os.environ.get("USE_LOCAL_AI", "0").lower() in ("1", "true", "yes")

def analyze_crime_risk(segment_summary, model="phi3:3.8b"):
    if not USE_LOCAL_AI:
        return None

    import requests  # safe to import only when neede

    prompt = f"""
You are a crime-risk scoring AI.

Return ONLY:

RISK: <0-1 number>
EXPLANATION: <1 sentence>

Crime Summary:
{segment_summary}
"""

    try:
        url = "http://localhost:11434/v1/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an expert crime risk analyst. Be concise."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 100
        }

        r = requests.post(url, json=payload, timeout=8)
        r.raise_for_status()
        data = r.json()

        # Extract model response
        text = data["choices"][0]["message"]["content"]

        # Parse numeric risk
        m = re.search(r"RISK:\s*([0-9]*\.?[0-9]+)", text)
        risk = float(m.group(1)) if m else None

        # Explanation
        m2 = re.search(r"EXPLANATION:\s*(.*)", text)
        explanation = m2.group(1).strip() if m2 else ""

        if risk is None:
            raise Exception("LLM did not return a numeric risk.")

        return {
            "risk": max(0.0, min(1.0, risk)),
            "explanation": explanation
        }

    except Exception as e:
        raise RuntimeError(f"Local AI call failed: {e}")