import pandas as pd
import numpy as np
import random
import os

random.seed(42)
np.random.seed(42)

# ── Language pools ────────────────────────────────────────────────────────────

HC_TEXTS = {
    "en": [
        "Had a wonderful time at the beach with family today. The sunset was absolutely breathtaking and the kids loved playing in the waves.",
        "Finished reading a fascinating book on ancient history last night. I would highly recommend it to anyone who enjoys learning about the past.",
        "Cooking a new recipe tonight — spicy prawn curry with coconut milk. The whole house smells amazing already and everyone is excited.",
        "Went for a long walk this morning along the river path and felt incredibly refreshed afterwards. The weather was perfect.",
        "Caught up with old friends over coffee this afternoon. It is always so good to reconnect and hear what everyone has been up to.",
        "Started learning a new language this week using an app on my phone. It is challenging but very rewarding to make progress each day.",
        "The garden is looking beautiful after all the rain we had last weekend. The roses are blooming and the vegetables are growing well.",
        "Attended a really interesting public lecture on climate change and sustainable living this evening. Lots of practical ideas to think about.",
        "Tried a new yoga class today and absolutely loved the instructor's teaching style. Will definitely be going back next week.",
        "Spent the afternoon volunteering at the local community centre helping with the after-school programme. It felt very fulfilling.",
        "Made a big pot of soup from scratch today using vegetables from the garden. It turned out really well and we have enough for the week.",
        "Visited the art exhibition at the city gallery with my sister. There were some remarkable pieces and we spent a good two hours there.",
    ],
    "si": [
        "අද දවස ගොඩාක් සතුටින් ගෙවුණා. පවුලේ සියල්ලෝ එකතු වෙලා හොඳ ආහාරයක් කෑවා. ළමයින්ත් ගොඩාක් සතුටු වුණා.",
        "අද රෑ නව චිත්‍රපටයක් බැලුවා. කතාව ගොඩාක් හොඳයි, නළු නිළියන්ගේ රංගනය ඇත්තෙන්ම දිනාගත්තා. කවුරුත් බලන්න ඕනෙ.",
        "ගෙදර පොතක් කියෙව්වා. ගොඩාක් ඉගෙනගන්න දේවල් තිබුණා. නොදන්නා දේවල් ඕනෑ තරම් ඉගෙනගත්තා.",
        "සතියේ දවස් කීපයක් ව්‍යායාම කළා. ශරීරය හොඳ හැඟීමක් ගත්තා. ඒ නිසා ඉදිරියටත් කරන්න හිතාගෙන ඉන්නවා.",
        "මිතුරන් සමඟ ගමනක් ගිහින් ගොඩාක් ආස හිතුණා. රාත්‍රී ආහාරය ගෙන කතාබහ කළා. ඇත්තෙන්ම ආනන්දමත් දවසක් ගෙවුණා.",
    ],
    "ta": [
        "இன்று குடும்பத்துடன் நேரம் செலவிட்டோம். மிகவும் மகிழ்ச்சியாக இருந்தது. குழந்தைகள் விளையாடி மகிழ்ந்தனர்.",
        "புதிய புத்தகம் படிக்க ஆரம்பித்தேன். மிகவும் சுவாரஸ்யமாக இருக்கிறது. ஒவ்வொரு அத்தியாயமும் புதிய தகவல்களை தருகிறது.",
        "நண்பர்களுடன் சாப்பிட சென்றோம். நல்ல நேரம் கழித்தோம். நிறைய விஷயங்கள் பேசினோம்.",
        "காலையில் உடற்பயிற்சி செய்தேன். உடல் புத்துணர்ச்சியாக உணர்கிறது. தினமும் செய்வதை தொடர்வேன்.",
        "இன்று வேலை நன்றாக முடிந்தது. மிகவும் திருப்தியாக இருக்கிறேன். நாளை இன்னும் சிறப்பாக செய்வேன்.",
    ],
    "romanized_sinhala": [
        "ada family eka ekka beach giya. hari sathutu dawasak. lamainuth hodata sellam kalaa.",
        "ada rathriyy film ekak baluwa. kathawa hari hondai, actorsla ge acting eka hariyatama liked karaa.",
        "gedara idan pothak kiyewwa. godak dewal igena ganna thibba, ada mama godak dewal danagatta.",
        "sathiyata eka dawasak wiyayama kala, agata hri shakthiyan danenawa, wayayama karana eka agata hodai",
        "yaluwo ekka trip ekak giya godak asa unaa. rathri kama kaala katha karaa. harima santhosa dawasak.",
        "gedara vibhagaya potha ekka kalaa. dhan therenne godak. anith dawase wenath deyak karannnam.",
        "wathura para langa aluth walking ekak giya. godak refresh unaa. weather eka hondhata thibuna.",
        "office eken issellai naya recipe ekak try kalaa. gedara mutta thamai issarahata.",
    ],
}

MCI_TEXTS = {
    "en": [
        "Went to the shop today to get some things. I got a few items but I cannot quite remember what else I was supposed to get. Had to check my bag twice.",
        "Called my friend this afternoon. We talked for a while but I have already forgotten most of what we said. I think it was something about the weekend.",
        "Made food today at home. It was okay I think. I believe I have made this dish before but I am not entirely sure when that was.",
        "Went outside for a walk in the morning. Came back after a while feeling a little tired. I am not sure how long I was out for.",
        "Tried to read my book this evening but found it difficult to focus for very long. I had to reread the same paragraph a few times.",
        "Saw someone I know at the market today. I recognised their face but could not remember their name until they introduced themselves.",
        "Did some work around the house today. I am not sure if I finished everything I meant to do. I will have to check again tomorrow.",
        "Watched something on television after dinner. I cannot remember now what the programme was called or what it was about.",
        "Had my morning tea and sat for a while thinking. The day passed quite slowly. I did not manage to do as much as I had planned.",
        "Wrote a message to my sister today. I had to rewrite it a couple of times because I kept losing my train of thought halfway through.",
    ],
    "si": [
        "අද ගෙදර ඉඳගෙන ටිකක් කාලය ගෙවුණා. හිතට ටිකක් අමාරුයි. මොකද කරන්නේ කියලා හිතාගන්නම අමාරුයි.",
        "යන්න හිතුණා, ගියා, ආවා. හරියටම මොකද ගොස් කළේ කියලා දැන් හොඳට මතක නෑ. ටිකක් අමාරුයි.",
        "කෑම හැදුවා. කෑවා. හොඳද නැද්ද හරියට මතක නෑ. ඊළඟ පාර මොකද හදන්නේ කියලත් සිහි නෑ.",
        "ගෙදරින් එළියට ගිහින් ටිකක් ඉඳලා ආවා. ඇයි ගිහින් ආවේ හරිහැටි දන්නෑ. ගිය කාරණාව අමතකයි.",
        "රූපවාහිනී බැලුවා. මොකක්ද කියලා දැන් හරිහැටි මතක නෑ. ටික වෙලාවක් බලලා නැවතුණා.",
    ],
    "ta": [
        "இன்று வீட்டில் இருந்தேன். என்ன செய்தேன் என்று சரியாக நினைவில்லை. நேரம் மெதுவாக கடந்தது.",
        "யாரோ வந்தார்கள். பேசினோம். என்ன பேசினோம் என்று இப்போது மறந்துவிட்டேன். முக்கியமான விஷயமா என்று தெரியவில்லை.",
        "சாப்பிட்டேன். சரியாக இருந்ததா என்று தெரியவில்லை. என்ன சமைத்தோம் என்றும் மறந்துவிட்டது.",
        "வெளியே சென்றேன். திரும்பி வந்தேன். ஏன் சென்றேன் என்ற காரணம் மறந்துவிட்டது.",
        "தொலைக்காட்சி பார்த்தேன். என்ன நிகழ்ச்சி என்று நினைவில்லை. சிறிது நேரம் பார்த்துவிட்டு நிறுத்தினேன்.",
    ],
    "romanized_sinhala": [
        "ada kade giya monawa hari genna. monada gaththe kiyala therenne naa. bag eka dedena patta check kalaa.",
        "yaluwata call kalaa. monava katha kalada dhan mathaka naa. weekend ekaka wagayi kiyala hithanawa.",
        "kamak hadhdha gedara. hondada kiyala therenne naa. mona wageda karanna one kiyalath mathaka naa.",
        "eliyata giya walk ekakata. tikak mahansiyen aawa. kohomada innne kiyala therenne naa.",
        "potha kiyawanna try kalaa magema hithe hitiye naa. paragraph eka nawatha nawatha kiyawanna una.",
        "kadey ekkenek dhaka giya. muna therunaa namuth nama mathaka una naa. eyaa kiwwama therunaa.",
        "geval wada kalaa ada. okkoma karala ivara kalada kiyala mathaka naa. heta ithurath check karanna one.",
        "TV ekak baluwa kama passe. kiyana eka mathaka naa dhan monavada kiyala.",
    ],
}

AD_TEXTS = {
    "en": [
        "Went to the place. The place I went. I went to the place again. The place the place. Cannot find the place now. Went and came. Went and came from the place.",
        "I went I went I went. Home. I went home. Home home. Need to go home. Home is the place. I am going home now. Home home home.",
        "The thing. I need the thing. The thing is somewhere. Cannot find the thing. The thing the thing. Where is the thing I need the thing.",
        "Cannot. I cannot do this. Cannot find it. Cannot remember. Cannot cannot. I cannot do the thing I cannot find it I cannot.",
        "People came today. People people came. I do not know the people. The people came to the house. Who are the people. People came people came.",
        "Went out. Out out. I went out today. Out I went. Then came back. Back home. Went out came back. Out and back. Out out.",
        "Eat. Need to eat. I eat today. Eat eat. The food. Eat the food. Food food food. Need to eat the food now.",
        "I forget again. Forgot again. Forget forget. I forget everything I forget. Again I forgot. Forget I forget again today.",
        "What day today. The day. Today what day. Day day. I do not know what day it is today. Day today what day.",
        "My name. What is my name. I know my name. The name. My name my name. What is the name. I know I know my name.",
        "The door. I locked the door. Did I lock the door. The door the door. Need to check the door. Locked or not the door.",
        "Morning came. Morning morning. Is it morning now. Morning or evening. The time. What is the time now. Morning time.",
    ],
    "si": [
        "ගියා. ආවා. ගෙදර. ගෙදර ගෙදර. ගෙදරට ගියා. ගෙදරට ගෙදරට. ගෙදර කොහෙද. ගෙදර ගෙදර ගෙදර.",
        "ඒ දේ. දේ ඕනෙ. දේ කොහෙද. ඒ දේ ඒ දේ. දේ හොයනවා. දේ දේ. ඒ දේ නෑ. ඒ දේ හොයන්න ඕනෙ.",
        "මතක නෑ. නෑ. මතක නෑ නෑ. නෑ නෑ. මතකනෑ අද. ආයෙත් මතක නෑ. මතක නෑ නෑ.",
        "කෑවා. කෑම. කෑවාද. කෑම කෑම. කෑවාද නැද්ද. කෑම කෑම කෑම. කෑවා අද.",
        "ගෙදර. ගෙදර ගෙදර. ගෙදරට ගෙදරට. ගෙදර කොහෙද. ගෙදරට යන්නෙ. ගෙදර ගෙදර.",
    ],
    "ta": [
        "போனேன். வந்தேன். போனேன் வந்தேன். போகணும். போனேன் போனேன். எங்கே போனேன். போனேன் திரும்பி வந்தேன்.",
        "பொருள். அந்த பொருள். பொருள் வேணும். பொருள் பொருள். எங்கே பொருள். அந்த பொருள் வேணும் எனக்கு.",
        "மறந்தேன். மறந்தேன் மறந்தேன். மறக்கிறேன். மீண்டும் மறந்தேன். மறந்துவிட்டேன் மறந்துவிட்டேன்.",
        "சாப்பிட்டேனா. சாப்பாடு. சாப்பிட்டேனா இல்லையா. சாப்பாடு சாப்பாடு. சாப்பிட வேணும்.",
        "வீடு. வீடு வீடு. வீட்டிற்கு போகணும். வீடு எங்கே. வீடு வீடு. வீட்டிற்கு திரும்பணும்.",
    ],
    "romanized_sinhala": [
         "giya. gedara giya. gedara gedara. gedara kohomada. giya aawa gedara. gedara gedara giya.",
         "eka deyak. deyak one. deyak kohomada. eka deyak eka deyak. deyak hoyanawaa. deyak deyak naa.",
         "mathaka naa. naa. mathaka naa naa. naa naa. mathaka naa ada. ayeth mathaka naa.",
         "kaeva. kama. kaevada. kama kama. kaevada naddha. kama kama kama. kaeva ada.",
         "gedara. gedara gedara. gedara giya. gedara kohomada. gedaratama yanna. gedara gedara.",
    ],
}

INTERACTION_TYPES_ACTIVE  = ["comment", "message", "caption"]
INTERACTION_TYPES_PASSIVE = ["like", "view", "react"]
LANGUAGES = ["en", "si", "ta", "romanized_sinhala"]

# Key fix: AD_Risk now gets 8-12 active samples (not 1-3)
# and score ranges are spread further apart
CLASSES = {
    "HC":      {"n_subjects": 34, "active_range": (12, 18), "passive_range": (2, 4),  "score_range": (0.05, 0.32)},
    "MCI":     {"n_subjects": 33, "active_range": (7,  12), "passive_range": (3, 6),  "score_range": (0.43, 0.67)},
    "AD_Risk": {"n_subjects": 33, "active_range": (8,  12), "passive_range": (1, 3),  "score_range": (0.73, 0.96)},
}

TEXT_POOLS = {"HC": HC_TEXTS, "MCI": MCI_TEXTS, "AD_Risk": AD_TEXTS}

LANCET_FACTORS = [
    "education_less_than_secondary",
    "hearing_loss",
    "hypertension",
    "smoking",
    "obesity",
    "depression",
    "physical_inactivity",
    "diabetes",
    "low_social_contact",
    "excessive_alcohol",
    "traumatic_brain_injury",
    "air_pollution",
    "vision_loss",
    "high_ldl_cholesterol"
]

posts_rows = []
gt_rows    = []
env_rows   = []
subject_counter = 1

for cls, cfg in CLASSES.items():
    pool = TEXT_POOLS[cls]
    for _ in range(cfg["n_subjects"]):
        sid  = f"S{subject_counter:03d}"
        lang = random.choice(LANGUAGES)
        n_active  = random.randint(*cfg["active_range"])
        n_passive = random.randint(*cfg["passive_range"])
        risk_score = round(random.uniform(*cfg["score_range"]), 4)
        base_date  = pd.Timestamp("2024-01-01")

        for _ in range(n_active):
            text = random.choice(pool[lang])
            date = base_date + pd.Timedelta(days=random.randint(0, 365))
            posts_rows.append({
                "subject_id":       sid,
                "text":             text,
                "interaction_type": random.choice(INTERACTION_TYPES_ACTIVE),
                "date":             date.strftime("%Y-%m-%d"),
                "language":         lang,
            })
        for _ in range(n_passive):
            date = base_date + pd.Timedelta(days=random.randint(0, 365))
            posts_rows.append({
                "subject_id":       sid,
                "text":             "",
                "interaction_type": random.choice(INTERACTION_TYPES_PASSIVE),
                "date":             date.strftime("%Y-%m-%d"),
                "language":         lang,
            })

        gt_rows.append({
            "subject_id":              sid,
            "ground_truth_risk_class": cls,
            "ground_truth_risk_score": risk_score,
            "language":                lang,
        })

        # Generate Lancet factors & symptom_severity based on class with strict bounds
        if cls == "HC":
            n_factors = random.choices([0, 1, 2], weights=[0.45, 0.45, 0.10])[0]
            sym_sev = round(random.uniform(0.00, 0.20), 4)
        elif cls == "MCI":
            n_factors = random.choices([3, 4, 5, 6], weights=[0.35, 0.35, 0.20, 0.10])[0]
            sym_sev = round(random.uniform(0.30, 0.60), 4)
        else: # AD_Risk
            n_factors = random.choices([5, 6, 7, 8, 9], weights=[0.30, 0.35, 0.20, 0.10, 0.05])[0]
            sym_sev = round(random.uniform(0.50, 0.90), 4)

        chosen_factors = set(random.sample(LANCET_FACTORS, n_factors))
        env_entry = {"subject_id": sid}
        for f in LANCET_FACTORS:
            env_entry[f] = (f in chosen_factors)
        env_entry["symptom_severity"] = sym_sev
        env_rows.append(env_entry)

        subject_counter += 1

os.makedirs("data", exist_ok=True)
pd.DataFrame(posts_rows).to_csv("data/posts.csv",                index=False)
pd.DataFrame(gt_rows).to_csv(   "data/ground_truth.csv",         index=False)
pd.DataFrame(env_rows).to_csv(  "data/environmental_intake.csv", index=False)

gt_df = pd.DataFrame(gt_rows)
env_df = pd.DataFrame(env_rows)
print(f"posts.csv                : {len(posts_rows)} rows")
print(f"ground_truth.csv         : {len(gt_rows)} subjects")
print(f"environmental_intake.csv : {len(env_rows)} subjects")
print(gt_df["ground_truth_risk_class"].value_counts().to_string())
print(gt_df["language"].value_counts().to_string())