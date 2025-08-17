import re
import json
import random
from datetime import datetime, timedelta
import ollama

# ------------ Member Profile ------------
MEMBER_PROFILE = """
Rohan Patel, 42, Singapore-based founder (tech sector).
Chronic condition: high blood pressure.
Baseline habits: inconsistent exercise, high travel load.
PA: Sarah Tan (coordinates all logistics).
Personality: curious, pragmatic, prefers WhatsApp-style quick chats.
Goals: longevity, metabolic fitness, heart health.
Context: Elyx 12-month precision health concierge program.
"""

# ------------ Elyx Team (Cast of Experts) ------------
TEAM_ROLES = """
Ruby (Ops): scheduling, test logistics, reminders.
Dr. Warren (Medical lead): medical oversight, strategy, treatment plans.
Advik (Data science/tech): wearables, biometrics, data collection.
Carla (Nutritionist): diet, meals, nutrition planning.
Rachel (Exercise physiologist): exercise, recovery, programming.
Neel (Longevity advisor): big-picture reassurance, program anchoring.
Sarah (PA): manages coordination, practical support.
"""

# ------------ Global Restrictions / Program Rules ------------
PROGRAM_RULES = """
- Week 2: settling into rhythm, no major travel this week.
- Focus: habit building, adherence, early Q&A.
- First biweekly updates to exercise and nutrition can appear.
- No diagnostic test panel yet (tests come at week 4).
- Rohan should ask 3–5 curiosity questions across the week.
- Singapore timezone (SGT) for scheduling.
- Chats must be short, WhatsApp style, 1–2 lines.
- Speakers allowed: Rohan, Sarah, Ruby, Dr. Warren, Advik, Carla, Rachel, Neel.
- No markdown, no numbering, no JSON in chat text.
"""

# ------------ Allowed Senders & Event Types ------------
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
        ("test", ["test", "panel", "results", "lab", "report",
         "ogtt", "ldl", "apo", "lp(a)", "cimt", "mri", "fit"]),
        ("plan_change", ["adjust", "modify",
         "change", "swap", "replace", "update plan"]),
        ("travel", ["flight", "airport", "travel",
         "timezone", "jet lag", "hotel", "boarding"]),
        ("logistics", ["schedule", "book", "arrange",
         "slot", "availability", "calendar", "appointment"]),
        ("followup", ["follow up", "checking in",
         "check-in", "remind", "touch base"]),
        ("education", ["tip", "tips", "why", "because",
         "recommend", "suggest", "guidance"]),
        ("question", ["?", "can we", "should we", "how do", "what if"]),
        ("update", ["update", "status", "progress", "note"])
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

# ------------ Ollama Prompt Builders ------------


def build_system_prompt():
    return f"""
You are the Elyx Concierge Team. Generate WhatsApp-style messages between Rohan (the member), Sarah (his PA), and Elyx experts.
Rules:
- Each message 1–2 short lines, WhatsApp tone.
- Use only these speakers: {', '.join(ALLOWED_SENDERS)}.
- No markdown, no numbering, no explanations.

Member Context:
{MEMBER_PROFILE}

Elyx Team:
{TEAM_ROLES}

Program Rules:
{PROGRAM_RULES}
"""


def build_user_prompt(day_idx: int, date_str: str, n_turns: int):
    return f"""
Week 2, Day {day_idx} ({date_str}).
Generate exactly {n_turns} raw chat lines in the format 'Speaker: message'.
Include:
- Habit setting and adherence reminders.
- Biweekly first updates to exercise/nutrition.
- Some curiosity questions from Rohan (total 3–5 this week).
- Singapore timezone context.
Constraints:
- Only allowed speakers.
- Very short, WhatsApp-style messages.
- No timestamps, no JSON.
"""

# ------------ Core Generator ------------


def generate_week2(start_date="2025-01-22", daily_min=12, daily_max=18, seed=202):
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


# ------------ Script Entry ------------
if __name__ == "__main__":
    data = generate_week2(start_date="2025-01-22")
    with open("elyx_week2_communications.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("✅ Generated: elyx_week2_communications.json")
