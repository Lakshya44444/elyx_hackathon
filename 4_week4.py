# Week 4 WhatsApp-style communications generator (STRICT JSON) using Ollama
# - Uses Ollama to create short chat lines
# - Wraps into strict JSON schema with timestamps + event tags
# - Incorporates member profile, Elyx team roles, and Week 4–8 rules in the prompt

import re
import json
import random
from datetime import datetime, timedelta
import ollama

# ------------ Member Profile ------------
MEMBER_PROFILE = """
Member’s Profile
1) Snapshot
- Preferred name: Rohan Patel
- DOB / Age / Gender: 12 March 1979, 46, Male
- Residence & travel hubs: Singapore; frequent travel to UK, US, South Korea, Jakarta
- Occupation: Regional Head of Sales, FinTech; frequent international travel; high stress
- Personal assistant: Sarah Tan

2) Core Outcomes & Timelines
- Reduce risk of heart disease by maintaining healthy cholesterol/BP by Dec 2026
- Enhance cognitive function & focus for sustained performance by Jun 2026
- Implement annual full-body screenings starting Nov 2025

- Why now: Family history of heart disease; wants long-term career performance; be present for young children
- Success metrics: Blood markers (cholesterol, BP, inflammatory markers), cognitive scores, sleep quality (Garmin), stress resilience (subjective + Garmin HRV)

3) Behavioural & Psychosocial
- Personality/values: Analytical, driven, efficiency + evidence-based
- Stage of change: Highly motivated, time-constrained; needs concise, data-driven plans
- Social support: Supportive wife; 2 kids; has a cook at home
- Mental health: No formal history; manages work stress via exercise

4) Tech Stack & Data
- Wearables: Garmin (runs); considering Oura
- Apps: Trainerize, MyFitnessPal, Whoop
- Data sharing: Full sharing approved
- Reporting cadence: Monthly consolidated trend report; quarterly deep dives

5) Preferences
- Channels: Important updates + scheduling via PA (Sarah)
- Response times: 24–48h non-urgent; urgent → PA then wife
- Detail depth: Prefers exec summaries; wants optional granular evidence
- Language/culture: English; Indian cultural background

6) Scheduling & Logistics
- Weekly availability: Morning 20-min routine; occasional runs
- Travel: At least 1 week every 4 on business trips (UK/US/KR/Jakarta time zones)
- Appointments: Virtual preferred; on-site ok for major assessments
"""

# ------------ Elyx Team (Cast of Experts) ------------
TEAM_ROLES = """
Elyx Concierge Team – Roles & Voices
- Ruby (Concierge / Orchestrator): Logistics, scheduling, reminders, follow-ups.
  Voice: Empathetic, organized, proactive; removes friction.
- Dr. Warren (Medical Strategist / Physician): Interprets labs, approves diagnostics, sets medical direction.
  Voice: Authoritative, precise, scientific, clear.
- Advik (Performance Scientist): Wearables/HRV/sleep/recovery/stress data; experiments & hypotheses.
  Voice: Analytical, curious, pattern-oriented.
- Carla (Nutritionist): Nutrition plans, food logs, CGM, supplements; coordinates with cook.
  Voice: Practical, educational, explains the "why".
- Rachel (Physiotherapist): Strength, mobility, rehab, exercise programming.
  Voice: Direct, encouraging, form & function.
- Neel (Relationship Manager / Lead): Strategic reviews, de-escalation, links to long-term goals.
  Voice: Strategic, calm, reassuring.
- Sarah Tan (Personal Assistant): Scheduling & coordination for Rohan; concise & precise.
- Rohan Patel (Member): Busy, analytical, professional but casual.
"""

# ------------ Global Restrictions / Program Rules ------------
PROGRAM_RULES = """
Program Constraints & Rhythm
- One full diagnostic test panel every 3 months.
- Member starts up to 5 curiosity questions per week on average.
- Member commits ~5 hours/week to the plan.
- Exercises updated every 2 weeks based on progress.
- Member travels 1 week out of every 4.
- Adherence ~50%: ~half of proposed plans need adjustment.
- Member generally well; may manage 1 chronic condition (e.g., high BP or high sugar).

Weeks 4–8 Specifics
- Test results are shared intermittently and categorized:
  * "major issues" <act>
  * "need followup" <soft follow up>
  * "all okay" <note>
- Different Elyx experts speak with the member about results and actions.
- Confirm and capture member commitments for interventions (lifestyle changes).
"""

ALLOWED_SENDERS = ["Rohan", "Sarah", "Ruby",
                   "Dr. Warren", "Advik", "Carla", "Rachel", "Neel"]
ALLOWED_EVENTS = ["update", "question", "test", "plan_change", "travel",
                  "logistics", "followup", "education", "escalation", "resolution", "attachment"]

# ------------ Event classifier (keyword-based) ------------


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
    # Random times between 08:00 and 18:00 local
    base = datetime.strptime(iso_date + " 08:00", "%Y-%m-%d %H:%M")
    times = [base + timedelta(minutes=random.randint(0, 600))
             for _ in range(n)]
    times.sort()
    return [t.strftime("%Y-%m-%d %H:%M") for t in times]

# ------------ Ollama Prompt Builders ------------


def build_system_prompt():
    return f"""
You are the Elyx Concierge Team. Generate WhatsApp-style messages between the member (Rohan Patel), his PA (Sarah), and Elyx experts.
Rules:
- Keep each message 1–2 short lines, WhatsApp tone.
- Use only these speakers: {", ".join(ALLOWED_SENDERS)}.
- No markdown, no numbering, no explanations—only chat content when requested.
Context:
{TEAM_ROLES}

Member Context:
{MEMBER_PROFILE}

Program Context:
{PROGRAM_RULES}
"""


def build_user_prompt(day_idx: int, date_str: str, n_turns: int, is_travel_week: bool):
    travel_note = "Rohan is traveling on business with timezone shifts this week; include travel logistics and jet lag considerations." if is_travel_week else "Rohan is in Singapore; keep scheduling in SGT."
    # Encourage distribution of member-initiated questions up to 5/week. Week 4 = first week of this month segment.
    return f"""
Week 4, Day {day_idx} ({date_str}).
Goal: Generate exactly {n_turns} chat lines in raw text, each line 'Speaker: message'.
Include:
- Intermittent sharing of test results categorized as: "major issues" <act>, "need followup" <soft follow up>, or "all okay" <note>.
- Experts (Dr. Warren, Advik, Carla, Rachel, Neel, Ruby) discuss results, interventions, and commitments.
- Up to 5 member-initiated curiosity questions across the week; sprinkle naturally.
- Exercises may update this week (biweekly cadence).
- Adherence ~50% → some plan changes due to preferences/logistics.
- {travel_note}
Constraints:
- Very short, WhatsApp-style messages.
- Use only allowed speakers.
- Do NOT include timestamps; only 'Speaker: text' lines.
- Do NOT include JSON; plain chat lines only.
"""

# ------------ Core Generator ------------


def generate_week4(start_date="2025-01-22", daily_min=12, daily_max=18, seed=42):
    random.seed(seed)
    week_json = []
    system_prompt = build_system_prompt()

    # Assume Week 4 is a TRAVEL week (per "1 week out of every 4"): set True
    travel_week = True

    for d in range(7):
        date_obj = datetime.strptime(
            start_date, "%Y-%m-%d") + timedelta(days=d)
        date_str = date_obj.strftime("%Y-%m-%d")
        n_turns = random.randint(daily_min, daily_max)
        timestamps = day_timestamps(date_str, n_turns)

        user_prompt = build_user_prompt(d+1, date_str, n_turns, travel_week)

        # --- Call Ollama ---
        resp = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ]
        )

        raw = resp.get("message", {}).get("content", "")
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

        # Normalize + filter lines to allowed speakers and extract message
        parsed = []
        for ln in lines:
            # Standardize speakers
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

        # Enforce exact n_turns if Ollama produced extra/less
        if len(parsed) > n_turns:
            parsed = parsed[:n_turns]
        elif len(parsed) < n_turns:
            # If fewer than needed, repeat last valid short nudge (keeps schema intact)
            while len(parsed) < n_turns and parsed:
                last = parsed[-1]
                filler = (last[0], "Noted.") if len(
                    last[1]) > 6 else (last[0], "Okay.")
                parsed.append(filler)

        # Build JSON items with timestamps + event tags
        for i, (sender, message) in enumerate(parsed):
            item = {
                "timestamp": timestamps[min(i, len(timestamps)-1)],
                "sender": sender,
                "message": message,
                "event": classify_event(message)
            }
            # Guard: enforce allowed event vocabulary only
            if item["event"] not in ALLOWED_EVENTS:
                item["event"] = "update"
            week_json.append(item)

    return week_json


# ------------ Script Entry ------------
if __name__ == "__main__":
    data = generate_week4(start_date="2025-01-22")
    with open("elyx_week4_communications.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("✅ Generated: elyx_week4_communications.json")
