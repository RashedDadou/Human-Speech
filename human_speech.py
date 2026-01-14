# human_speech.py
"""
محاكاة النطق البشري وتواصل الحيوانات بالأصوات (بالإنجليزي فقط حاليًا، مع دعم محدود للغات أخرى)
- يأخذ نصًا بشريًا أو وصف صوت حيواني
- يستخرج phonemes باستخدام epitran للبشري
- يربطها بـ visemes للبشري
- يحاكي حركات اللسان، الأسنان، الفم، الشفاه، الوجه والجسم للبشري
- يحاكي آليات إنتاج الصوت للحيوانات بناءً على التقرير: طيور (سيرينكس)، ثدييات (حيتان، خفافيش، قرود)، حشرات، برمائيات، أسماك
- ينتج وصف نصي للحركات/الآليات (يمكن تطويره لاحقًا إلى animation data أو توليد صوتي)
- يتضمن تطبيقات AI بسيطة: نماذج فيزيائية/عصبية، استخراج ميزات، محاكاة، تعلم ذاتي
"""

import os
import json
from pathlib import Path
import logging
import argparse
import time

import nltk
nltk.data.path = [
    r"C:\Users\Rashed_Dadou\nltk_data",
    r"C:\nltk_data",
] + nltk.data.path

from speech_visualizer import visualize_from_json

try:
    import epitran
    os.environ['PANPHON_USE_CACHE'] = 'False'
except ImportError:
    print("epitran غير مثبت. قم بتثبيته:")
    print("pip install epitran panphon")
    exit(1)
else:
    print("epitran imported successfully!")

g2p = None

try:
    from g2p_en import G2p
    g2p = G2p()
except ImportError:
    print("g2p_en غير مثبتة → الدعم الإنجليزي سيكون محدودًا")
except Exception as e:
    print(f"خطأ أثناء تهيئة g2p_en: {e}")
    g2p = None
    
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# تهيئة epitran للغات متعددة
epi_eng = epitran.Epitran('eng-Latn')
epi_ara = epitran.Epitran('ara-Arab')  # للعربية

# ─── قاموس viseme → وصف حركات اللسان/الأسنان/الفم/الوجه/الجسم للبشري ────────────────
# مبسط جدًا - يمكن توسيعه
VISeme_ANIMATION_HUMAN = {
    'PP': {'lips': 'closed', 'teeth': 'visible slightly', 'tongue': 'neutral', 'jaw': 'closed', 'face': 'neutral', 'body': 'slight head nod'},
    'FF': {'lips': 'upper teeth on lower lip', 'teeth': 'upper teeth visible', 'tongue': 'neutral', 'jaw': 'slightly open', 'face': 'slight smile', 'body': 'hand gesture forward'},
    'TH': {  # لسان بين الأسنان (θ, ð)
        'lips': 'open',
        'teeth': 'tongue between teeth',
        'tongue': 'tip between teeth',
        'jaw': 'open medium',
        'face': 'focused',
        'body': 'leaning forward'
    },
    'SS': {  # هواء مع أسنان (s, z)
        'lips': 'open slightly',
        'teeth': 'visible',
        'tongue': 'tip near teeth',
        'jaw': 'open small',
        'face': 'tense',
        'body': 'still'
    },
    'SH': {  # شفاه مدورة + هواء (ʃ, ʒ)
        'lips': 'rounded forward',
        'teeth': 'hidden',
        'tongue': 'back raised',
        'jaw': 'open small',
        'face': 'relaxed',
        'body': 'shoulders raised'
    },
    'T': {  # لسان على الأسنان العلوية (t, d, n, l)
        'lips': 'open',
        'teeth': 'visible',
        'tongue': 'tip on alveolar ridge',
        'jaw': 'open medium',
        'face': 'neutral',
        'body': 'slight hand movement'
    },
    'IY': {  # شفاه مشدودة للأمام (i:)
        'lips': 'spread wide',
        'teeth': 'visible',
        'tongue': 'high front',
        'jaw': 'close',
        'face': 'smile',
        'body': 'head tilt up'
    },
    'AA': {  # فتح واسع (ɑ, æ)
        'lips': 'open wide',
        'teeth': 'visible',
        'tongue': 'low back',
        'jaw': 'open wide',
        'face': 'surprised/excited',
        'body': 'arms open'
    },
    'UW': {  # شفاه مدورة (u:)
        'lips': 'rounded tight',
        'teeth': 'hidden',
        'tongue': 'high back',
        'jaw': 'close',
        'face': 'kiss',
        'body': 'leaning back'
    },
    'SIL': {  # صمت / راحة
        'lips': 'relaxed',
        'teeth': 'hidden',
        'tongue': 'rest',
        'jaw': 'closed',
        'face': 'neutral',
        'body': 'relaxed'
    },
    'AINF': {  # أصوات أنفية (m, n, ng)
        'lips': 'closed or open slightly',
        'teeth': 'hidden',
        'tongue': 'neutral or raised',
        'jaw': 'closed',
        'face': 'relaxed',
        'body': 'steady'
    },
    'HLQ': {  # أصوات حلقية مثل ع/ح في العربية
        'lips': 'open',
        'teeth': 'visible',
        'tongue': 'back lowered',
        'jaw': 'open',
        'face': 'tense throat',
        'body': 'neck forward'
    },
    'TONE': {  # نغمات في الصينية
        'lips': 'vary with phoneme',
        'teeth': 'vary with phoneme',
        'tongue': 'vary with pitch',
        'jaw': 'vary with pitch',
        'face': 'expressive pitch',
        'body': 'head movement with tone'
    }
}

# ─── قواميس لآليات إنتاج الصوت عند الحيوانات من التقرير ────────────────
# مبسط - يمكن توسيعه لمحاكاة فيزيائية أو عصبية
ANIMAL_SOUND_MECHANISMS = {
    'birds': {  # الطيور
        'organ': 'syrinx',
        'mechanism': 'vibration of membranes in syrinx at tracheal-bronchial junction',
        'features': 'independent control of each side, allowing two different notes simultaneously',
        'examples': 'songbirds produce complex songs for mating or territory',
        'ai_application': 'physical model simulation of syrinx for generating bird-like sounds'
    },
    'whales_baleen': {  # حيتان ذات الفانات
        'organ': 'larynx-like structure',
        'mechanism': 'low-frequency sounds propagated through ventral grooves to water',
        'features': 'complex songs for communication during breeding',
        'examples': 'humpback whales produce songs',
        'ai_application': 'neural models to generate whale songs using frequency modulation'
    },
    'whales_toothed': {  # حيتان ذات الأسنان
        'organ': 'phonic lips in nasal passage',
        'mechanism': 'sound modified by melon (fatty forehead)',
        'features': 'echolocation clicks for navigation',
        'examples': 'dolphins use clicks and whistles',
        'ai_application': 'feature extraction for echo patterns in AI sonar simulation'
    },
    'bats': {  # خفافيش
        'organ': 'larynx',
        'mechanism': 'ultrasound for echolocation',
        'features': 'high-frequency calls to locate prey',
        'examples': 'bats emit pulses and listen to echoes',
        'ai_application': 'self-learning models to optimize echo-based navigation'
    },
    'primates': {  # قرود
        'organ': 'vocal apparatus similar to humans',
        'mechanism': 'variety of sounds for social communication',
        'features': 'calls for alarm or bonding',
        'examples': 'chimpanzees use grunts and screams',
        'ai_application': 'reinforcement learning for social sound generation'
    },
    'insects_stridulation': {  # حشرات (احتكاك)
        'organ': 'wings or body parts',
        'mechanism': 'rubbing body parts together',
        'features': 'chirping sounds',
        'examples': 'crickets rub wings',
        'ai_application': 'simulation data for insect sound synthesis'
    },
    'insects_tymbals': {  # حشرات (أغشية طبلية)
        'organ': 'tymbals in abdomen',
        'mechanism': 'vibration of membranes',
        'features': 'high-pitched buzzing',
        'examples': 'cicadas produce loud calls',
        'ai_application': 'physics-based models for membrane vibration'
    },
    'insects_drumming': {  # حشرات (طرق)
        'organ': 'head or body',
        'mechanism': 'tapping on surfaces',
        'features': 'clicks or drums',
        'examples': 'termites tap heads',
        'ai_application': 'feature extraction for rhythm patterns'
    },
    'amphibians': {  # برمائيات
        'organ': 'vocal cords with vocal sacs',
        'mechanism': 'amplification of sounds for mating',
        'features': 'croaks amplified by sacs',
        'examples': 'frogs croak to attract mates',
        'ai_application': 'neural networks for call variation'
    },
    'fish': {  # أسماك
        'organ': 'swim bladder or teeth',
        'mechanism': 'vibration or grinding',
        'features': 'grunts or hums',
        'examples': 'some fish grind teeth',
        'ai_application': 'underwater sound simulation for AI'
    }
}

# ─── دالة لتحويل نص بشري إلى فونيمات حسب اللغة ────────────────
def text_to_phonemes(text: str, language: str = 'eng') -> str:
    """
    تحويل نص إنجليزي بسيط إلى تمثيل فونيمي تقريبي
    - تستخدم قاموسًا يدويًا صغيرًا للكلمات الشائعة
    - الباقي يرجع سلسلة من 'SIL' كبديل مؤقت
    """
    text = text.strip()
    if not text:
        return "sil"

    # القاموس اليدوي (هنا المكان اللي كنت أقصده)
    simple_fallback = {
        'hello':    'HH AH0 L OW1',
        'world':    'W ER1 L D',
        'this':     'DH IH0 S',
        'is':       'IH0 Z',
        'a':        'AH0',
        'test':     'T EH1 S T',
        'the':      'DH AH0',
        'quick':    'K W IH1 K',
        'brown':    'B R AW1 N',
        'fox':      'F AA1 K S',
        'jumps':    'JH AH1 M P S',
        'over':     'OW1 V ER0',
        'lazy':     'L EY1 Z IY0',
        'dog':      'D AO1 G',
        'good':     'G UH1 D',
        'morning':  'M AO1 R N IH0 NG',
        'everyone': 'EH1 V R IY0 W AH2 N',
        # أضف أي كلمات أخرى تريدها هنا
    }

    # تقسيم النص إلى كلمات
    words = text.lower().split()

    result = []
    for word in words:
        # إزالة أي علامات ترقيم بسيطة (اختياري)
        clean_word = word.strip(",.!?").lower()
        if clean_word in simple_fallback:
            result.append(simple_fallback[clean_word])
        else:
            # fallback بسيط جدًا
            result.append("SIL " * (len(clean_word) // 2 + 2))

    # جمع النتيجة
    return " ".join(result).strip()

# ─── قاموس ربط: IPA symbol → فئة viseme (أو صوت مشابه) ────────────────
PHONEME_TO_VISEME = {
    # مشترك
    'p': 'bilabial', 'b': 'bilabial', 'm': 'bilabial',
    'f': 'labiodental', 'v': 'labiodental',
    'θ': 'interdental', 'ð': 'interdental',
    's': 'alveolar_fricative', 'z': 'alveolar_fricative',
    'ʃ': 'postalveolar_fricative', 'ʒ': 'postalveolar_fricative',
    't': 'alveolar_stop', 'd': 'alveolar_stop', 'n': 'alveolar_nasal', 'l': 'alveolar_lateral',
    'ɾ': 'flap', 'r': 'rhotic',
    'k': 'velar_stop', 'g': 'velar_stop',
    'i': 'close_front', 'iː': 'close_front', 'ɪ': 'near_close_near_front',
    'u': 'close_back_rounded', 'uː': 'close_back_rounded',
    'ɑ': 'open_back', 'a': 'open_central', 'aː': 'open_central',

    # عربي محدد
    'ħ': 'pharyngeal_fricative', 'ʕ': 'pharyngeal_fricative',
    'q': 'uvular_stop', 'χ': 'uvular_fricative', 'ʁ': 'uvular_fricative',
    'sˤ': 'emphatic_fricative', 'dˤ': 'emphatic_stop',
    'tˤ': 'emphatic_stop', 'ðˤ': 'emphatic_fricative',
    'ʔ': 'glottal_stop',
    'j': 'palatal_approximant', 'w': 'labiovelar_approximant',

    # fallback
    ' ': 'sil', '': 'sil'
}

# ─── قاموس الفيزيمات: فئة → قيم عددية + وصف نصي ────────────────
VISEME_DETAILS = {
    'bilabial': {
        'mouth_open': 0.10, 'jaw_open': 0.15, 'lip_round': 0.50, 'lip_spread': 0.00,
        'lips': 'closed_rounded', 'jaw': 'closed', 'tongue': 'rest', 'face': 'neutral'
    },
    'labiodental': {
        'mouth_open': 0.15, 'jaw_open': 0.10, 'lip_round': 0.80, 'lip_spread': 0.00,
        'lips': 'rounded_tight', 'jaw': 'slightly_open', 'tongue': 'rest', 'face': 'slight_smile'
    },
    'interdental': {
        'mouth_open': 0.35, 'jaw_open': 0.25, 'lip_round': 0.00, 'lip_spread': 0.10,
        'lips': 'open', 'jaw': 'open_medium', 'tongue': 'tip_between_teeth', 'face': 'focused'
    },
    'pharyngeal_fricative': {
        'mouth_open': 0.50, 'jaw_open': 0.45, 'lip_round': 0.00, 'lip_spread': 0.00,
        'lips': 'open_neutral', 'jaw': 'open_medium', 'tongue': 'root_retracted', 'face': 'tense_throat'
    },
    'emphatic_fricative': {
        'mouth_open': 0.45, 'jaw_open': 0.50, 'lip_round': 0.10, 'lip_spread': 0.05,
        'lips': 'neutral_tight', 'jaw': 'open_medium', 'tongue': 'low_back', 'face': 'tense'
    },
    'sil': {
        'mouth_open': 0.00, 'jaw_open': 0.00, 'lip_round': 0.00, 'lip_spread': 0.00,
        'lips': 'relaxed', 'jaw': 'closed', 'tongue': 'rest', 'face': 'neutral'
    },
    # أضف المزيد تدريجيًا (alveolar_fricative, velar_stop, إلخ)
}


# ─── دالة لربط الفونيمات بالفيزيمات ────────────────
def phonemes_to_visemes(phonemes: str, emotion: str = 'neutral') -> list[dict]:
    """
    تحويل سلسلة IPA → قائمة من dicts تحتوي على:
    - phoneme
    - viseme_category
    - params (عددية + وصفية)
    """
    EMOTION_MULTIPLIERS = {
        'neutral':  {'mouth_open': 1.0, 'jaw_open': 1.0, 'lip_round': 1.0, 'lip_spread': 1.0},
        'happy':    {'mouth_open': 0.9,  'jaw_open': 0.8,  'lip_round': 0.7,  'lip_spread': 1.4},
        'angry':    {'mouth_open': 1.3,  'jaw_open': 1.4,  'lip_round': 0.9,  'lip_spread': 0.6},
        'surprised':{'mouth_open': 1.6,  'jaw_open': 1.5,  'lip_round': 0.2,  'lip_spread': 0.3},
        'sad':      {'mouth_open': 0.7,  'jaw_open': 0.6,  'lip_round': 1.1,  'lip_spread': -0.4},
    }
    mult = EMOTION_MULTIPLIERS.get(emotion.lower(), EMOTION_MULTIPLIERS['neutral'])

    result = []
    i = 0
    while i < len(phonemes):
        char = phonemes[i]
        # محاولة أخذ رمزين (مثل sˤ أو aː)
        two_chars = phonemes[i:i+2]
        if two_chars in PHONEME_TO_VISEME:
            category = PHONEME_TO_VISEME[two_chars]
            ph = two_chars
            i += 2
        else:
            category = PHONEME_TO_VISEME.get(char, 'sil')
            ph = char
            i += 1

        base = VISEME_DETAILS.get(category, VISEME_DETAILS['sil'])
        params = {k: base.get(k, 0.0) * mult.get(k, 1.0) for k in ['mouth_open', 'jaw_open', 'lip_round', 'lip_spread']}
        params.update({
            'lips': base['lips'],
            'jaw': base['jaw'],
            'tongue': base['tongue'],
            'face': base['face'],
            'viseme_category': category
        })

        result.append({'phoneme': ph, 'params': params})

    return result

# ─── دالة مساعدة لاستخراج القيم العددية فقط (للـ animation) ────────────────
def get_viseme_numeric_params(viseme_category: str, emotion='neutral'):
    base = VISEME_DETAILS.get(viseme_category, VISEME_DETAILS['sil'])
    mult = EMOTION_MULTIPLIERS.get(emotion.lower(), EMOTION_MULTIPLIERS['neutral'])
    return {k: base.get(k, 0.0) * mult.get(k, 1.0) for k in ['mouth_open', 'jaw_open', 'lip_round', 'lip_spread']}

# ─── دالة لمحاكاة الحركات البشرية ────────────────
def simulate_human_speech_movements(viseme_list: list[dict]) -> list[dict]:
    movements = []
    for idx, item in enumerate(viseme_list):
        params = item['params']
        movements.append({
            "time_step": idx,
            "phoneme": item['phoneme'],
            "viseme_category": params['viseme_category'],
            "mouth_open": params['mouth_open'],
            "jaw_open": params['jaw_open'],
            "lip_round": params['lip_round'],
            "lip_spread": params['lip_spread'],
            "lips": params['lips'],
            "jaw": params['jaw'],
            "tongue": params['tongue'],
            "face_expression": params['face'],
        })
    return movements

# ─── دالة محاكاة آليات إنتاج الصوت للحيوانات ────────────────
def simulate_animal_sound(animal_type: str, sound_description: str) -> dict:
    """
    محاكاة آليات إنتاج الصوت للحيوانات بناءً على النوع
    """
    if animal_type not in ANIMAL_SOUND_MECHANISMS:
        logger.warning(f"نوع الحيوان غير معروف: {animal_type} → استخدام 'birds' كافتراضي")
        animal_type = 'birds'  # أو يمكن ترمي exception لو تبي صرامة أكثر

    mechanism = ANIMAL_SOUND_MECHANISMS[animal_type]

    return {
        "animal_type": animal_type,
        "sound_description": sound_description,
        "organ": mechanism.get('organ', 'غير محدد'),
        "mechanism": mechanism.get('mechanism', 'غير محدد'),
        "features": mechanism.get('features', 'غير محدد'),
        "examples": mechanism.get('examples', 'غير محدد'),
        "ai_application": mechanism.get('ai_application', 'غير محدد')
    }

# ─── دالة تطبيق ميزات AI (أكثر ذكاءً ومرونة) ────────────────
def apply_ai_features(data: list | dict, ai_type: str = 'physical') -> dict:
    """
    تطبيق وصف ميزات AI بناءً على نوع البيانات المدخلة
    """
    data_type = "human_speech" if isinstance(data, list) else "animal_mechanism"

    descriptions = {
        'physical': f"محاكاة فيزيائية لـ {data_type} (vocal tract / syrinx / phonic lips)",
        'neural': f"تعلم عميق (WaveNet/Tacotron/Wav2Vec) من بيانات {data_type}",
        'feature_extraction': f"استخراج ميزات (pitch, formants, spectrogram) من {data_type}",
        'training_data': f"إنشاء/استخدام مجموعة بيانات من تسجيلات {data_type}",
        'simulation': f"توليد بيانات اصطناعية بمحاكاة بيولوجية لـ {data_type}",
        'self_learning': f"تعلم ذاتي/تعزيزي مشابه لـ {data_type} (مثل تعلم الطيور للأغاني)",
    }

    desc = descriptions.get(ai_type, "تطبيق AI مدمج/غير محدد")

    return {
        "ai_type": ai_type,
        "description": desc,
        "data_type": data_type,
        "input_summary": f"{len(data)} عنصر" if isinstance(data, list) else "وصف آلية واحدة"
    }

# ─── دالة رئيسية لمعالجة نص بشري (معدلة لتدعم القيم العددية) ────────────────
def process_human_text(
    text: str,
    language: str = 'eng',
    output_file: str = None,
    ai_type: str = 'physical',
    emotion: str = 'neutral'   # ← إضافة مهمة جدًا
) -> dict:
    """
    معالجة نص بشري كامل → phonemes → visemes → حركات عددية + وصفية
    """
    phonemes = text_to_phonemes(text, language)

    # استخدام النسخة المحسنة اللي اقترحناها قبل
    viseme_items = phonemes_to_visemes(phonemes, emotion=emotion)

    # تحويل إلى animation_sequence متوافق مع الـ visualizer
    movements = []
    for idx, item in enumerate(viseme_items):
        params = item['params']
        movements.append({
            "time_step": idx,
            "phoneme": item['phoneme'],
            "viseme_category": params.get('viseme_category', 'unknown'),
            # القيم العددية الرئيسية ← هذي اللي يحتاجها الـ visualizer
            "mouth_open": params.get('mouth_open', 0.0),
            "jaw_open": params.get('jaw_open', 0.0),
            "lip_round": params.get('lip_round', 0.0),
            "lip_spread": params.get('lip_spread', 0.0),
            # الوصف النصي (اختياري للـ debug أو توسع لاحق)
            "lips": params.get('lips', 'relaxed'),
            "jaw": params.get('jaw', 'closed'),
            "tongue": params.get('tongue', 'rest'),
            "face_expression": params.get('face', 'neutral'),
        })

    ai_features = apply_ai_features(movements, ai_type)

    result = {
        "original_text": text,
        "language": language,
        "emotion": emotion,
        "phonemes": phonemes,
        "viseme_sequence": [item['phoneme'] for item in viseme_items],  # أو احتفظ بالتفاصيل كاملة
        "animation_sequence": movements,
        "ai_features": ai_features,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"تم حفظ النتيجة في: {output_file}")

    return result

# ─── دالة رئيسية لمعالجة صوت حيواني ────────────────
def process_animal_sound(animal_type: str, sound_description: str, output_file: str = None, ai_type: str = 'physical'):
    """معالجة وصف صوت حيواني"""
    mechanism = simulate_animal_sound(animal_type, sound_description)
    ai_features = apply_ai_features(mechanism, ai_type)

    result = {
        "animal_type": animal_type,
        "sound_description": sound_description,
        "mechanism": mechanism,
        "ai_features": ai_features
    }

    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"تم حفظ النتيجة في: {output_file}")

    return result

# ─── الدالة الرئيسية للتشغيل ────────────────
def main():
    # أمثلة بشرية
    human_examples = [
        {"text": "السلام عليكم ورحمة الله وبركاته هذا اختبار", "language": "ara", "emotion": "neutral"},
        {"text": "مرحبا بالعالم نحن نجرب محاكاة النطق العربي", "language": "ara", "emotion": "happy"},
        {"text": "يا راشد كيف حالك اليوم", "language": "ara", "emotion": "surprised"},
    ]
    # أمثلة حيوانية من التقرير
    animal_examples = [
        {"type": "birds", "desc": "complex song for mating"},
        {"type": "whales_baleen", "desc": "low-frequency song"},
        {"type": "whales_toothed", "desc": "echolocation clicks"},
        {"type": "bats", "desc": "ultrasound pulses"},
        {"type": "primates", "desc": "social grunts"},
        {"type": "insects_stridulation", "desc": "wing rubbing chirp"},
        {"type": "insects_tymbals", "desc": "membrane vibration buzz"},
        {"type": "insects_drumming", "desc": "head tapping clicks"},
        {"type": "amphibians", "desc": "vocal sac amplified croak"},
        {"type": "fish", "desc": "swim bladder vibration grunt"}
    ]

    # مجلد Simulation ينشأ تلقائيًا
    output_dir = Path("Simulation")
    output_dir.mkdir(parents=True, exist_ok=True)

    # ─── معالجة بشرية ────────────────────────────────────────────────
    for i, ex in enumerate(human_examples, 1):
        output_path = output_dir / f"Emotion_Generation_Human_{i}.json"
        
        result = process_human_text(
            ex["text"], 
            ex["language"], 
            output_file=str(output_path),
            ai_type='physical'
        )

        print(f"\n=== بشري {i}: {ex['text']} ({ex['language']}) ===")
        print(f"تم الحفظ في: {output_path.resolve()}")
        print(f"الفونيمات: {result['phonemes'][:100]}...")
        print(f"عدد الفيزيمات: {len(result['viseme_sequence'])}")
        print("أول 3 حركات: ", result['animation_sequence'][:3])
        print("تطبيق AI: ", result['ai_features'])

    # ─── معالجة حيوانية ──────────────────────────────────────────────
    for i, ex in enumerate(animal_examples, 1):
        output_path = output_dir / f"Emotion_Generation_Animal_{i}.json"
        
        result = process_animal_sound(
            ex["type"], 
            ex["desc"], 
            output_file=str(output_path),
            ai_type='physical'
        )

        print(f"\n=== حيواني {i}: {ex['type']} - {ex['desc']} ===")
        print(f"تم الحفظ في: {output_path.resolve()}")
        print("الآلية: ", result['mechanism'])
        print("تطبيق AI: ", result['ai_features'])

    logger.info("تم الانتهاء من المحاكاة وحفظ جميع الملفات في مجلد Simulation!")

    # ─── عرض visualization تلقائي (demo) ────────────────────────────────
    demo_path = output_dir / "Emotion_Generation_Human_1.json"
    
    if demo_path.exists():
        print("\n" + "="*70)
        print(" جاري عرض الـ visualization التجريبي لأول مثال بشري ")
        print(" النص: Hello world, this is a test. ")
        print("="*70 + "\n")
        
        try:
            visualize_from_json(str(demo_path))
        except Exception as e:
            print(f"خطأ في عرض الـ visualization: {e}")
            print("يمكنك تشغيلها يدويًا لاحقًا")
    else:
        print("\nتحذير: ملف الـ demo غير موجود")
        print(f"المتوقع: {demo_path}")
        print("تأكد من وجود أمثلة بشرية وتشغيلها بنجاح")
        
if __name__ == "__main__":
    examples = [
        "Hello world, this is a test.",
        "The quick brown fox jumps over the lazy dog.",
        "Good morning everyone.",
    ]

    for ex in examples:
        print(f"Text : {ex}")
        print(f"Phones: {text_to_phonemes(ex)}\n")