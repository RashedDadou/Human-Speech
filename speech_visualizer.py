# speech_visualizer.py

import json
from pathlib import Path
import logging
import time

try:
    from gtts import gTTS
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    from matplotlib.patches import Rectangle, Circle, Wedge
    import numpy as np
    import pygame
except ImportError as e:
    print(f"مكتبات ناقصة: {e}")
    exit(1)

# ─── هنا مكانه المثالي ────────────────────────────────────────────────
# VISEME_MAP ── قيم عددية + وصفية لكل نوع فيزيم
# حاليًا غير مستخدم مباشرة، لكن مخطط استخدامه في update() لتحسين الدقة
VISEME_MAP = {
    'bilabial':         {'jaw_open': 0.15, 'mouth_open': 0.1,  'lip_round': 0.5, 'lip_spread': 0.0, 'tongue': 'rest',      'lips': 'closed_rounded'},
    'labiodental':      {'jaw_open': 0.1,  'mouth_open': 0.15, 'lip_round': 0.8, 'lip_spread': 0.0, 'tongue': 'rest',      'lips': 'rounded_tight'},
    'dental_stop':      {'jaw_open': 0.25, 'mouth_open': 0.3,  'lip_round': 0.0, 'lip_spread': 0.1, 'tongue': 'near_teeth','lips': 'neutral'},
    'interdental':      {'jaw_open': 0.25, 'mouth_open': 0.35, 'lip_round': 0.0, 'lip_spread': 0.15,'tongue': 'between_teeth','lips': 'neutral'},
    'emphatic':         {'jaw_open': 0.5,  'mouth_open': 0.5,  'lip_round': 0.1, 'lip_spread': 0.1, 'tongue': 'low_back',  'lips': 'neutral'},
    'velar':            {'jaw_open': 0.35, 'mouth_open': 0.4,  'lip_round': 0.2, 'lip_spread': 0.0, 'tongue': 'high_back', 'lips': 'neutral'},
    'rounded_vowel':    {'jaw_open': 0.3,  'mouth_open': 0.5,  'lip_round': 0.9, 'lip_spread': 0.0, 'tongue': 'mid',       'lips': 'rounded_forward'},
    'front_vowel':      {'jaw_open': 0.25, 'mouth_open': 0.4,  'lip_round': 0.0, 'lip_spread': 0.5, 'tongue': 'high_front','lips': 'spread'},
    'open_vowel':       {'jaw_open': 0.8,  'mouth_open': 0.9,  'lip_round': 0.0, 'lip_spread': 0.2, 'tongue': 'low',       'lips': 'open_wide'},
    'rest':             {'jaw_open': 0.0,  'mouth_open': 0.0,  'lip_round': 0.0, 'lip_spread': 0.0, 'tongue': 'rest',      'lips': 'relaxed_neutral'},
    # أضف المزيد لاحقًا (مثل: 'pharyngeal', 'fricative_alveolar', ...)
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_audio(text: str, lang: str = 'ar', output_mp3: str = "temp_speech.mp3") -> float:
    """
    توليد ملف صوت فقط + إرجاع طوله بالثواني
    لا تشغيل هنا → للسماح بالتزامن مع الـ animation
    """
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(output_mp3)
        logger.info(f"تم حفظ الصوت في: {output_mp3}")

        # احسب الطول بدون تشغيل كامل
        pygame.mixer.init()
        sound = pygame.mixer.Sound(output_mp3)
        duration = sound.get_length()
        logger.info(f"طول الصوت: {duration:.2f} ثانية")

        return duration

    except Exception as e:
        logger.error(f"خطأ في توليد الصوت: {e}")
        print(f"فشل توليد الصوت: {e}")
        return 0.0  # أو قيمة fallback
    
def interpolate(from_mov: dict, to_mov: dict, t: float = 0.6) -> dict:
    """
    Linear interpolation بين حركتين
    t في [0.0, 1.0]
    """
    t = max(0.0, min(1.0, t))  # clamp لتجنب قيم غريبة

    result = {}
    numeric_keys = ['mouth_open', 'jaw_open', 'lip_round', 'lip_spread',
                    'jaw_height', 'tongue_y']   # أضف كل ما تحتاجه

    for key in numeric_keys:
        v1 = from_mov.get(key, 0.0)
        v2 = to_mov.get(key, 0.0)
        result[key] = v1 + (v2 - v1) * t

    # للـ string keys (مثل lips, tongue, jaw desc) → نأخذ الأقرب أو نستخدم to_mov
    string_keys = ['lips', 'tongue', 'jaw', 'face_expression']
    for key in string_keys:
        # إما نأخذ to_mov إذا t ≥ 0.5، أو نعمل شيء أكثر ذكاءً لاحقًا
        result[key] = to_mov.get(key, from_mov.get(key, 'neutral'))

    return result
    
# ─── Visualization بسيطة للفم والوجه ────────────────────────
def visualize_speech_movements(movements: list[dict], duration_per_step=0.12):
    """
    رسم متحرك بسيط لمحاكاة حركات النطق
    - repeat=False → يشتغل مرة وحدة ويتوقف (أفضل للتزامن مع الصوت)
    - blit=True → تحديث أسرع للعناصر المتغيرة فقط
    """

    if not movements:
        print("لا توجد حركات لعرضها")
        return

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title("محاكاة حركات النطق (بسيطة)")

    # ─── العناصر الرسومية ────────────────────────────────────────────────
    jaw = Rectangle((2, 1), 6, 2, fc='lightgray', ec='black', lw=1.5)
    upper_lip = Wedge((5, 6), 3, 180, 360, fc='pink', ec='black', lw=1.5)
    lower_lip = Wedge((5, 4), 3, 0, 180, fc='pink', ec='black', lw=1.5)
    tongue_tip = Circle((5, 4.5), 0.6, fc='red', ec='darkred', lw=1)

    ax.add_patch(jaw)
    ax.add_patch(upper_lip)
    ax.add_patch(lower_lip)
    ax.add_patch(tongue_tip)

    # نعمل نسخة من أول حركة عشان ما نعدلش القائمة الأصلية
    prev_mov = movements[0].copy()

    # خريطة مواقع اللسان (أكثر مرونة)
    tongue_y_map = {
        'high': 6.5, 'high front': 6.8, 'high back': 6.2,
        'mid': 5.0,
        'low': 2.5, 'low back': 2.8,
        'between_teeth': 3.8, 'near_teeth': 4.0,
        'retroflex': 5.2, 'bunched': 5.0,
        'rest': 4.5
    }

    def update(frame):
        nonlocal prev_mov

        # الحركة الحالية (مع loop إذا خلّصت الحركات)
        current = movements[frame % len(movements)]

        # blending factor (يمكنك تجربة قيم مختلفة: 0.6 → 0.75)
        t = 0.68

        blended = {}
        for key in ['mouth_open', 'jaw_open', 'lip_round', 'lip_spread']:
            v1 = prev_mov.get(key, 0.0)
            v2 = current.get(key, 0.0)
            blended[key] = v1 + (v2 - v1) * t

        blended['lips']   = current.get('lips',   prev_mov.get('lips',   'relaxed_neutral'))
        blended['tongue'] = current.get('tongue', prev_mov.get('tongue', 'rest'))
        blended['jaw']    = current.get('jaw',    prev_mov.get('jaw',    'closed'))
        blended['face_expression'] = current.get('face_expression', prev_mov.get('face_expression', 'neutral'))

        # ─── الفك ───────────────────────────────────────────────────────────
        jaw_height = 2.0
        jaw_desc = blended['jaw'].lower()
        if any(x in jaw_desc for x in ['wide', 'open wide']):
            jaw_height = 5.0
        elif any(x in jaw_desc for x in ['medium', 'medium open']):
            jaw_height = 3.5
        elif 'slightly open' in jaw_desc:
            jaw_height = 2.8

        jaw.set_height(jaw_height)
        jaw.set_y(3 - jaw_height / 2)   # مركزي أكثر

        # ─── الشفاه ────────────────────────────────────────────────────────
        lips_desc = blended['lips'].lower()
        lip_radius = 2.8

        if 'closed' in lips_desc:
            lip_radius = 2.5
        elif any(x in lips_desc for x in ['rounded', 'forward', 'pursed', 'protruded']):
            lip_radius = 1.8 + blended.get('lip_round', 0.0) * 0.6
        elif 'spread' in lips_desc or 'wide' in lips_desc:
            lip_radius = 3.2 + blended.get('lip_spread', 0.0) * 0.4

        lower_lip.set_radius(lip_radius)
        upper_lip.set_radius(lip_radius)

        # ─── اللسان ────────────────────────────────────────────────────────
        tongue_y = 4.5
        tongue_desc = blended['tongue'].lower()
        for key, pos in tongue_y_map.items():
            if key in tongue_desc:
                tongue_y = pos
                break

        tongue_tip.center = (5, tongue_y)

        # ─── لون الوجه (تعبير بسيط) ───────────────────────────────────────
        face_expr = blended['face_expression'].lower()
        face_color = 'lightgray'
        if any(x in face_expr for x in ['smile', 'happy']):
            face_color = 'lightblue'
        elif any(x in face_expr for x in ['angry', 'tense']):
            face_color = 'lightcoral'
        elif any(x in face_expr for x in ['surprised', 'excited']):
            face_color = 'yellow'

        jaw.set_facecolor(face_color)

        prev_mov = current.copy()

        return jaw, upper_lip, lower_lip, tongue_tip

    # ─── إعداد الـ Animation ───────────────────────────────────────────────
    interval_ms = max(50, int(duration_per_step * 1000))   # ~8–20 إطار/ثانية تقريبًا

    anim = FuncAnimation(
        fig=fig,
        func=update,
        frames=len(movements) * 2,       # مثال: تكرار مرتين – يمكن تعديله حسب طول الصوت
        interval=interval_ms,
        blit=True,                       # تحديث أسرع (مهم جدًا)
        repeat=False                     # يشتغل مرة ويتوقف (مناسب للتزامن مع الصوت)
    )

    plt.show()

    # لو حابب ترجع الـ animation object عشان تتحكم فيه لاحقًا
    return anim

# ─── دمج مع النتيجة السابقة ────────────────────────────────
def visualize_from_json(json_path: str):
    import pygame  # لو مش موجود فوق

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    text = data.get("original_text", "مرحبا بالعالم")
    lang = data.get("language", "ar")
    movements = data.get("animation_sequence", [])

    if not movements:
        print("لا توجد بيانات حركات")
        return

    output_mp3 = "temp_output.mp3"

    # 1. توليد الصوت فقط (بدون تشغيل)
    duration = generate_audio(text, lang=lang, output_mp3=output_mp3)  # ← استخدم النسخة اللي ما تشغلش

    if duration <= 0:
        print("فشل في الحصول على طول صوت → استخدام fallback")
        duration = len(movements) * 0.12

    print(f"طول الصوت المحسوب: {duration:.2f} ثانية")

    # 2. إعدادات الـ animation
    interval_ms = 80
    interval_sec = interval_ms / 1000.0
    num_frames = max(10, int(duration / interval_sec) + 5)

    print(f"عدد الفريمات المستهدف: {num_frames}")

    # تكرار الحركات إذا كانت قليلة
    if len(movements) < num_frames // 3:
        print("عدد الحركات قليل → تكرار الـ sequence")
        repeat_count = (num_frames // len(movements)) + 1
        extended_movements = movements * repeat_count
        movements = extended_movements[:num_frames]

    # 3. إعداد الشكل والـ animation
    fig, ax = plt.subplots(figsize=(6, 6))
    # ... هنا تضع كود الـ patches (jaw, upper_lip, lower_lip, tongue_tip)
    # ... وتعريف دالة update (كما في النسخة السابقة)

    anim = FuncAnimation(
        fig,
        update,
        frames=num_frames,
        interval=interval_ms,
        blit=True,
        repeat=False
    )

    # 4. تشغيل الصوت قبل أو مع بداية العرض
    try:
        pygame.mixer.music.load(output_mp3)
        pygame.mixer.music.play()
        print("بدأ تشغيل الصوت")
    except Exception as e:
        print(f"فشل تشغيل الصوت: {e}")

    plt.show()

    # بعد الإغلاق يمكن حذف الملف المؤقت إذا أردت
    # try: os.remove(output_mp3)
    # except: pass
        
# ─── مثال التشغيل ────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        json_path = "Simulation/Emotion_Generation_1.json"  # ← الجديد
    
    if Path(json_path).exists():
        visualize_from_json(json_path)
    else:
        print(f"الملف غير موجود: {json_path}")
        print("شغّل human_speech.py أولاً لإنشاء الملفات في مجلد Simulation")