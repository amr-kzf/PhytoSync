import os
import logging
import re
from flask import Blueprint, request, jsonify, session
from openai import APIError, OpenAI
from localization import current_language

chatbot_bp = Blueprint("chatbot", __name__, template_folder="templates", static_folder="static")
logger = logging.getLogger(__name__)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

OFFLINE_KNOWLEDGE = {
    "wheat": "Wheat thrives in well-drained loamy soil with temperatures between 15°C to 25°C. Critical irrigation stages: Crown Root Initiation (21 DAS) and Flowering.",
    "rice": "Rice requires heavy clay or alluvial soil with high water holding capacity and standing water during vegetative phases. Maintain optimal NPK of 90:50:50.",
    "fertilizer": "Apply nitrogen fertilizers (Urea) in split doses: 50% basal, 25% at tillering, and 25% at panicle/flowering initiation. Phosphatic fertilizers should be applied entirely at sowing.",
    "pest": "For initial pest infestations, apply 5% Neem Oil extract spray. For severe fungal attacks, consider Mancozeb (2g/L) or Copper Oxychloride based on local extension guidelines.",
    "yellow leaves": "Yellowing of older leaves typically indicates Nitrogen (N) deficiency. Interveinal yellowing on younger leaves suggests Iron or Magnesium deficiency.",
    "moisture": "Maintain soil moisture at field capacity (50-70%). Avoid overwatering during ripening/harvest stages to prevent fungal rot."
}

OFFLINE_NPK_ANSWERS = {
    "n": "N in N-P-K fertilizer stands for nitrogen. Plants use it to make chlorophyll and proteins, supporting leafy, green growth. Older leaves turning yellow can indicate nitrogen deficiency; too much nitrogen can produce excessive leaves instead of flowers or fruit. Use a soil test and local crop recommendations to guide application.",
    "p": "P in N-P-K fertilizer stands for phosphorus. It supports root development, energy transfer, and flowering or seed formation. Use a soil test to check whether your soil needs phosphorus, since excess can run off and harm waterways.",
    "k": "K in N-P-K fertilizer stands for potassium (also called potash). It helps regulate water use and supports strong stems and general stress tolerance. Soil testing is the best way to determine the right amount for your crop.",
    "npk": "N-P-K shows the percentages by weight of nitrogen (N), phosphate (P₂O₅), and potash (K₂O) in a fertilizer. For example, 10-10-10 contains 10% of each. Choose a blend based on a soil test and your crop's needs."
}

AR_OFFLINE_KNOWLEDGE = {
    "wheat": "ينمو القمح جيدًا في التربة الطميية جيدة التصريف ودرجات حرارة بين 15 و25°م. من مراحل الري المهمة: تكوين الجذور التاجية عند نحو 21 يومًا والإزهار.",
    "rice": "يحتاج الأرز إلى تربة طينية أو غرينية تحتفظ بالماء، مع توفر الماء خلال مراحل النمو الخضري. احتياجه الإرشادي من NPK هو 90:50:50.",
    "fertilizer": "قسّم إضافة السماد النيتروجيني مثل اليوريا إلى جرعات وفق توصيات المحصول المحلية. يُضاف السماد الفوسفاتي عادةً عند الزراعة، مع الاستناد إلى تحليل التربة.",
    "pest": "راقب الإصابة واعزل الأجزاء المتضررة عند الإمكان. استخدم أي مبيد وفق ملصق المنتج وتوصيات الإرشاد الزراعي المحلي.",
    "yellow leaves": "قد يشير اصفرار الأوراق القديمة إلى نقص النيتروجين، بينما قد يرتبط الاصفرار بين العروق في الأوراق الحديثة بنقص عناصر أخرى. افحص النبات والتربة قبل التسميد.",
    "moisture": "حافظ على رطوبة مناسبة للتربة وتجنب الإفراط في الري، خصوصًا قرب النضج والحصاد، للحد من أعفان الجذور والأوراق.",
}


def offline_reply(question, language="en"):
    normalized_question = question.lower().strip()
    normalized_question = re.sub(r"[^\w\s]", "", normalized_question)
    words = set(normalized_question.split())

    if language == "ar":
        if re.search(r"(مرحبا|مرحباً|أهلا|اهلا|السلام عليكم|هاي)", normalized_question):
            return "مرحبًا! أستطيع مساعدتك في العناية بالمحاصيل وأعراض النباتات والتربة والأسمدة والري والآفات. ما المحصول أو المشكلة التي تريد السؤال عنها؟"
        if "npk" in words:
            return "توضح N-P-K نسب النيتروجين (N) والفوسفات (P₂O₅) والبوتاس (K₂O) في السماد. اختر التركيبة وفق تحليل التربة واحتياجات المحصول."

        arabic_topics = {
            "wheat": ("قمح", "القمح"),
            "rice": ("أرز", "الرز"),
            "fertilizer": ("سماد", "تسميد", "أسمدة"),
            "pest": ("آفة", "آفات", "حشرة", "حشرات"),
            "yellow leaves": ("اصفرار", "أوراق صفراء", "اصفرار الأوراق"),
            "moisture": ("رطوبة", "ري", "الماء"),
        }
        replies = [
            AR_OFFLINE_KNOWLEDGE[key]
            for key, terms in arabic_topics.items()
            if any(term in normalized_question for term in terms)
        ]
        if replies:
            return "🌾 " + " ".join(replies)
        return "دليلي الزراعي دون اتصال لا يملك إجابة مؤكدة لهذا السؤال بعد. اسأل عن القمح أو الأرز أو التسميد أو الري أو الآفات أو اصفرار الأوراق، أو أضف GROQ_API_KEY للحصول على إجابات أوسع."

    if re.fullmatch(r"(hi|hello|hey|hiya|greetings)( there)?", normalized_question):
        return "Hi! I can help with crop care, plant symptoms, soil, fertilizer, pests, and irrigation. What are you growing or trying to solve?"

    if "npk" in words:
        return OFFLINE_NPK_ANSWERS["npk"]

    element_aliases = {
        "n": {"n", "nitrogen"},
        "p": {"p", "phosphorus"},
        "k": {"k", "potassium", "potash"},
    }
    asks_about_element = words.intersection({"what", "which", "meaning", "mean", "stands", "stand"})
    for symbol, aliases in element_aliases.items():
        if words.intersection(aliases) and (
            asks_about_element or words.issubset(aliases)
        ):
            return OFFLINE_NPK_ANSWERS[symbol]

    matched_replies = [value for key, value in OFFLINE_KNOWLEDGE.items() if key in normalized_question]
    if matched_replies:
        return "🌾 " + " ".join(matched_replies)

    return (
        "I can help with common farming questions, but my offline guide doesn't have that answer yet. "
        "Ask about a crop, fertilizer, irrigation, pests, or leaf symptoms. For a broader answer, configure "
        "a valid GROQ_API_KEY in your .env file and restart PhytoSync."
    )


@chatbot_bp.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json() or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    user_question = data.get("question", "")
    if not isinstance(user_question, str):
        return jsonify({"error": "Question must be text."}), 400
    user_question = user_question.strip()
    
    if not user_question:
        return jsonify({"error": "Question cannot be empty!"}), 400
    
    api_key = os.getenv("GROQ_API_KEY")
    
    if api_key:
        client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
        model = os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL
        language = current_language(session.get("language"))
        language_instruction = (
            "Respond in Arabic. Use clear, practical Modern Standard Arabic suitable for farmers."
            if language == "ar"
            else "Respond in English."
        )
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are PhytoSync AI, an expert agricultural consultant. Provide concise, clear, and practical advice for farmers on crops, fertilizers, irrigation, weather adaptation, and pest management. "
                        + language_instruction
                    },
                    {"role": "user", "content": user_question}
                ],
                max_tokens=450,
                temperature=0.3
            )
        except APIError as error:
            status_code = getattr(error, "status_code", None)
            logger.warning(
                "Groq chatbot request failed (status=%s, error_type=%s)",
                status_code,
                type(error).__name__,
            )
            if status_code in (401, 403):
                message = "Groq rejected the API key or its permissions. Create a new GROQ_API_KEY in Groq Console, update .env, and restart PhytoSync."
            elif status_code == 404:
                message = f"Groq could not find model '{model}'. Set GROQ_MODEL to an active Groq model in .env and restart PhytoSync."
            elif status_code == 429:
                message = "Groq rate limit or usage quota reached. Check your Groq Console limits and try again later."
            else:
                message = "Groq is temporarily unavailable. Check the server logs and try again."
            if language == "ar":
                if status_code in (401, 403):
                    message = "رفض Groq مفتاح API أو صلاحياته. أنشئ مفتاح GROQ_API_KEY جديدًا، حدّث ملف .env، ثم أعد تشغيل PhytoSync."
                elif status_code == 404:
                    message = f"لم يعثر Groq على النموذج '{model}'. حدّث GROQ_MODEL إلى نموذج متاح ثم أعد تشغيل PhytoSync."
                elif status_code == 429:
                    message = "تم بلوغ حد الاستخدام أو الحصة في Groq. تحقق من حدود حسابك وحاول لاحقًا."
                else:
                    message = "خدمة Groq غير متاحة مؤقتًا. تحقق من سجل الخادم ثم حاول مجددًا."
            return jsonify({
                "error": message
            }), 502

        if completion.choices and completion.choices[0].message.content:
            return jsonify({"response": completion.choices[0].message.content, "mode": "groq"})

        logger.error("Groq chatbot returned an empty completion")
        message = "تلقى مساعد PhytoSync ردًا فارغًا من Groq. حاول مرة أخرى." if language == "ar" else "PhytoSync AI received an empty response from Groq. Please try again."
        return jsonify({"error": message}), 502

    language = current_language(session.get("language"))
    return jsonify({"response": offline_reply(user_question, language), "mode": "offline"})
