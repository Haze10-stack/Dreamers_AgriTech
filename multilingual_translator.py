import os
from langdetect import detect
from groq import Groq
from dotenv import load_dotenv


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise Exception("❌ GROQ_API_KEY not found in .env file")

client = Groq(api_key=GROQ_API_KEY)


# ===============================
# GROQ TRANSLATION
# ===============================

def translate_with_model(text, src, tgt, model):

    prompt = f"""
Translate from {src} to {tgt}.
Only give translated text.

Text:
{text}
"""

    try:

        res = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a translator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        return res.choices[0].message.content.strip()

    except Exception as e:

        print(f"⚠️ {model} failed:", e)
        return text


def groq_translate_dual(text, source, target):

    t1 = translate_with_model(
        text, source, target,
        "openai/gpt-oss-20b"
    )

    t2 = translate_with_model(
        text, source, target,
        "moonshotai/kimi-k2-instruct-0905"
    )

    sim = simple_similarity(t1, t2)

    print("Translation Similarity:", sim)

    if sim >= 0.6:
        return t1

    return min([t1, t2], key=len)


# ===============================
# BACK TRANSLATION CHECK
# ===============================

def back_translation_check(original, translated, source_lang):

    back = groq_translate_dual(translated, "en", source_lang)

    similarity = simple_similarity(original, back)

    print("Back Translation Similarity:", similarity)

    return similarity >= 0.45


def simple_similarity(a, b):

    a = set(a.lower().split())
    b = set(b.lower().split())

    if not a or not b:
        return 0

    return len(a & b) / len(a | b)


# ===============================
# CORE AGENT
# ===============================

def run_core_agent(english_input, context):

    system_prompt = """
You are an expert agricultural advisor.

Rules:
- Think only in English
- No hallucination
- Give practical advice
- Follow safety rules
- Be realistic

Format:

Stage:
Weather Impact:
Action:
Warning:
Next Step:
"""

    user_prompt = f"""
Farmer Context:
{context}

Question:
{english_input}
"""

    try:

        res = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )

        return res.choices[0].message.content.strip()

    except Exception as e:

        print("⚠️ Core Agent Error:", e)

        return "Unable to generate advice at this time."


# ===============================
# VALIDATOR AGENT
# ===============================

def validate_response(response, context):

    prompt = f"""
Check this agricultural advice.

Context:
{context}

Advice:
{response}

Rules:
- Must be safe
- Must be realistic
- No false info
- Must match stage

Reply ONLY: VALID or FIX
"""

    try:

        res = client.chat.completions.create(
            model="moonshotai/kimi-k2-instruct-0905",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        verdict = res.choices[0].message.content.strip()

        return "VALID" in verdict.upper()


    except Exception as e:

        print("⚠️ Validator Error:", e)

        return False


# ===============================
# CLARIFICATION
# ===============================

def ask_clarification(lang):

    msg = "Please confirm your question. We detected some ambiguity."

    return groq_translate_dual(msg, "en", lang)


# ===============================
# MAIN PIPELINE
# ===============================

def process_user_message(user_text, farmer_context):

    # 1. Detect Language
    try:
        lang = detect(user_text)
    except:
        lang = "en"

    print("Detected Language:", lang)


    # 2. Translate → English
    if lang == "en":

        english_input = user_text

    else:

        english_input = groq_translate_dual(
            user_text,
            lang,
            "en"
        )

        print("English Input:", english_input)


        # 3. Back Translation
        ok = back_translation_check(
            user_text,
            english_input,
            lang
        )

        if not ok:
            return ask_clarification(lang)


    # 4. Core Reasoning
    ai_response_en = run_core_agent(
        english_input,
        farmer_context
    )

    print("AI English Output:\n", ai_response_en)

    # 5. Validation
    safe = validate_response(
        ai_response_en,
        farmer_context
    )

    if not safe:
        revised = run_core_agent(
            english_input + "\nPlease make it safer and remove chemicals.",
            farmer_context
        )
        ai_response_en = revised


    # 6. Translate Back
    if lang != "en":

        final_response = groq_translate_dual(
            ai_response_en,
            "en",
            lang
        )

    else:

        final_response = ai_response_en


    return final_response


# ===============================
# DEMO
# ===============================

if __name__ == "__main__":

    context = """
Crop: Rice
Location: Nashik
Soil: Red
Stage: Vegetative
Last Action: Fertilizer Applied
Weather: Low Rainfall
"""

    user_input = input("Enter your question: ")

    # user_input = "माझ्या शेतात पाणी नाही आणि पाने पिवळी आहेत. मला काय करायला हवे?"
    #user_input = "कल बारिश होगी क्या? कपास अब फूलने की अवस्था में है?"

    response = process_user_message(
        user_input,
        context
    )

    print("\n========== FINAL RESPONSE ==========\n")
    print(response)
