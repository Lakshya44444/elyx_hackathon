import re
import json
import random
from datetime import datetime, timedelta
import ollama

# ------------ Config ------------
ALLOWED_SENDERS = ["Rohan", "Sarah", "Ruby",
                   "Dr. Warren", "Advik", "Carla", "Rachel", "Neel"]
ALLOWED_EVENTS = ["update", "question", "test", "plan_change", "travel",
                  "logistics", "followup", "education", "escalation", "resolution", "attachment"]

# ------------ Event classifier ------------


def classify_event(message: str) -> str:
    m = message.lower()
    rules = [
        ("escalation", ["urgent", "immediately", "red flag", "alarming"]),
        ("resolution", ["resolved", "fixed", "cleared", "completed", "done"]),
        ("test", ["test", "results", "lab", "report", "ogtt", "lipid",
         "apo", "cimt", "mri", "dexa", "cortisol", "thyroid", "urinalysis"]),
        ("plan_change", ["adjust", "modify",
         "change", "swap", "replace", "update plan"]),
        ("travel", ["flight", "airport", "travel", "timezone",
         "jet lag", "hotel", "boarding", "business trip"]),
        ("logistics", ["schedule", "book", "arrange",
         "slot", "availability", "calendar", "appointment"]),
        ("followup", ["follow up", "checking in",
         "check-in", "remind", "touch base"]),
        ("education", ["tip", "tips", "why", "because",
         "recommend", "suggest", "guidance", "rationale"]),
        ("question", ["?", "can we", "should we",
         "how do", "what if", "which test", "is it safe"]),
        ("update", ["update", "status", "progress",
         "note", "exercise", "workout", "training"])
    ]
    for ev, kws in rules:
        if any(k in m for k in kws):
            return ev
    return "update"

# ------------ Timestamps ------------


def day_timestamps(iso_date: str, n: int):
    base = datetime.strptime(iso_date + " 08:00", "%Y-%m-%d %H:%M")
    times = [base + timedelta(minutes=random.randint(0, 600))
             for _ in range(n)]
    times.sort()
    return [t.strftime("%Y-%m-%d %H:%M") for t in times]

# ------------ Prompts ------------


def build_system_prompt():
    return f"""
You are the Elyx Concierge Team. Generate WhatsApp-style messages between the member (Rohan Patel), his PA (Sarah), and Elyx experts.
Rules:
- Each message 1–2 short lines, WhatsApp tone.
- Speakers allowed: {', '.join(ALLOWED_SENDERS)}.
- Sarah may speak on behalf of Rohan for scheduling/logistics.
- Keep exchanges concise and natural.
"""


def build_user_prompt(day_idx: int, date_str: str, n_turns: int):
    return f"""
Week 26, Day {day_idx} ({date_str}).
Generate exactly {n_turns} WhatsApp-style chat lines.
Include:
- Rohan is on a business trip (assume Hong Kong), with some travel constraints.
- New exercise plan introduced this week (bi-weekly update cycle).
- Ruby/Advik check in for blockers, logistics, and nudges on adherence.
- 4–5 curiosity questions from Rohan about fasting, inflammation, genetics, supplements.
- Member follows ~50% of plan → team adapts.
Constraints:
- Short, WhatsApp-style messages only.
"""

# ------------ Generator ------------


def generate_week26(start_date="2025-07-17", daily_min=12, daily_max=16, seed=2626):
    random.seed(seed)
    week_json = []
    system_prompt = build_system_prompt()

    for d in range(7):
        date_obj = datetime.strptime(
            start_date, "%Y-%m-%d") + timedelta(days=d)
        date_str = date_obj.strftime("%Y-%m-%d")
        n_turns = random.randint(daily_min, daily_max)
        timestamps = day_timestamps(date_str, n_turns)

        user_prompt = build_user_prompt(d+1, date_str, n_turns)

        resp = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ]
        )

        raw = resp.get("message", {}).get("content", "")
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

        parsed = []
        for ln in lines:
            ln = re.sub(r'^(Rohan Patel|Rohan)\s*:\s*', 'Rohan: ', ln)
            ln = re.sub(r'^(Sarah Tan|Sarah)\s*:\s*', 'Sarah: ', ln)
            ln = re.sub(r'^(Ruby).*?:\s*', 'Ruby: ', ln)
            ln = re.sub(r'^(Dr\.?\s*Warren).*?:\s*', 'Dr. Warren: ', ln)
            ln = re.sub(r'^(Advik).*?:\s*', 'Advik: ', ln)
            ln = re.sub(r'^(Carla).*?:\s*', 'Carla: ', ln)
            ln = re.sub(r'^(Rachel).*?:\s*', 'Rachel: ', ln)
            ln = re.sub(r'^(Neel).*?:\s*', 'Neel: ', ln)

            m = re.match(
                r'^(Rohan|Sarah|Ruby|Dr\. Warren|Advik|Carla|Rachel|Neel):\s*(.+)$', ln)
            if not m:
                continue
            sender = m.group(1)
            message = m.group(2).strip()
            if not message:
                continue
            parsed.append((sender, message))

        if len(parsed) > n_turns:
            parsed = parsed[:n_turns]
        elif len(parsed) < n_turns and parsed:
            while len(parsed) < n_turns:
                last = parsed[-1]
                filler = (last[0], "Noted.")
                parsed.append(filler)

        for i, (sender, message) in enumerate(parsed):
            item = {
                "timestamp": timestamps[min(i, len(timestamps)-1)],
                "sender": sender,
                "message": message,
                "event": classify_event(message)
            }
            if item["event"] not in ALLOWED_EVENTS:
                item["event"] = "update"
            week_json.append(item)

    return week_json


if __name__ == "__main__":
    data = generate_week26(start_date="2025-07-17")
    with open("elyx_week26_communications.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("✅ Generated: elyx_week26_communications.json")
