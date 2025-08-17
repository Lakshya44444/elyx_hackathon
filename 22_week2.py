import re
import random
from datetime import datetime, timedelta
import ollama

# ---- Roles & Panels Blocks ----
ROLES_BLOCK = """
Elyx Concierge Team – Roles & Communication Styles:

1. Ruby (Concierge / Orchestrator) - Warm, empathetic, organized.
2. Dr. Warren (Medical Strategist / Physician) - Clear, precise, science-driven.
3. Advik (Performance Scientist / Data Analyst) - Analytical, detailed.
4. Carla (Nutritionist / Dietary Strategist) - Practical, educational.
5. Rachel (Physiotherapist / Movement Specialist) - Direct, encouraging.
6. Neel (Relationship Manager / Strategic Lead) - Strategic, calm.
7. Sarah Tan (Personal Assistant to Rohan Patel) - Polite, efficient, precise.
8. Rohan Patel (Member / Client) - Busy, casual but professional.
"""

TEST_PANEL_BLOCK = """
Week 2–4 Focus: Biological sample collection + full physical exam + diagnostic scan suite.
Tests include blood panels, cardiovascular screening, fitness & functional testing, body composition, and brain health checks.
"""

RESTRICTIONS_BLOCK = """
- One diagnostic test panel every 3 months.
- Rohan initiates up to 5 curiosity questions per week.
- Member commits ~5 hrs/week to plan.
- Exercises updated every 2 weeks.
- Rohan travels 1 week every 4 weeks.
- Residence: Singapore.
- Adherence ~50% (plans need adjusting half the time).
- Health: generally well, but managing 1 chronic condition (e.g., high BP or high sugar).
"""

# ---- System Prompt ----
system_prompt = f"""You are the Elyx Concierge Team.
Simulate WhatsApp-style chats with Rohan Patel and Sarah Tan.
Keep chats very short (1–2 lines per speaker).
Always prefix with speaker name.
Avoid long paragraphs.

{ROLES_BLOCK}

{TEST_PANEL_BLOCK}

{RESTRICTIONS_BLOCK}
"""

# ---- Generate random timestamps per day ----


def generate_timestamps(date_str, n_msgs):
    base_time = datetime.strptime(date_str + " 08:00", "%Y-%m-%d %H:%M")
    times = [base_time + timedelta(minutes=random.randint(0, 600))
             for _ in range(n_msgs)]
    return [t.strftime("[%m/%d/%y, %I:%M %p]") for t in sorted(times)]

# ---- Generate Week 2 Chats ----


def generate_week2_chats(start_date="2025-01-08"):
    all_chats = []
    date = datetime.strptime(start_date, "%Y-%m-%d")

    for day in range(7):
        # 🔹 Increase messages per day (a little bigger)
        n_msgs = random.randint(14, 20)
        timestamps = generate_timestamps(
            (date + timedelta(days=day)).strftime("%Y-%m-%d"), n_msgs)

        user_prompt = f"Week 2 Day {day+1}: Collect biological samples + physical exam + scan suite. " \
            f"Keep chats short and WhatsApp style, but slightly longer conversations (14–20 turns)."

        # Call Ollama
        response = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        raw_text = response["message"]["content"]
        raw_lines = raw_text.splitlines()

        day_chats, ts_idx = [], 0
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue

            # Remove markdown symbols
            line = re.sub(r'[*_`]+', '', line)

            # Normalize speaker names
            line = re.sub(r'^(Rohan Patel|Rohan)\s*:', 'Rohan:', line)
            line = re.sub(r'^(Sarah Tan|Sarah)\s*:', 'Sarah:', line)
            line = re.sub(r'^(Ruby).*:', 'Ruby:', line)
            line = re.sub(r'^(Dr\.?\s*Warren).*:', 'Dr. Warren:', line)
            line = re.sub(r'^(Carla).*:', 'Carla:', line)
            line = re.sub(r'^(Advik).*:', 'Advik:', line)
            line = re.sub(r'^(Rachel).*:', 'Rachel:', line)
            line = re.sub(r'^(Neel).*:', 'Neel:', line)

            # Only keep valid lines
            if not re.match(r'^(Rohan|Ruby|Sarah|Dr\. Warren|Carla|Advik|Rachel|Neel):', line):
                continue

            # Attach timestamp
            ts = timestamps[min(ts_idx, len(timestamps) - 1)]
            formatted = f"{ts} {line}"
            day_chats.append(formatted)

            if ts_idx < len(timestamps) - 1:
                ts_idx += 1

        all_chats.append("\n".join(day_chats))

    return "\n\n".join(all_chats)


# ---- Main Execution ----
if __name__ == "__main__":
    chats = generate_week2_chats("2025-01-08")

    with open("elyx_week2_chats.txt", "w", encoding="utf-8") as f:
        f.write(chats)

    print("✅ Week 2 chat history generated: elyx_week2_chats.txt")
