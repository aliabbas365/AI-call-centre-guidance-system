from apps.calls.models import TranscriptChunk
from apps.analysis.models import CallAnalysis
from apps.knowledge_base.models import GuidanceRule


class CallAnalysisService:
    INTENT_KEYWORDS = {
        "technical_issue": [
            "internet", "router", "disconnect", "signal", "network",
            "not working", "technical", "device", "connection",
        ],
        "billing": [
            "bill", "billing", "payment", "invoice", "refund",
            "charge", "charged", "monthly payment", "cost",
        ],
        "complaint": [
            "complaint", "bad service", "angry", "frustrated",
            "upset", "terrible", "poor service",
        ],
        "insurance_inquiry": [
            "insurance", "medicare", "plan", "coverage", "benefit",
            "kaiser", "united healthcare", "monthly premium",
            "enrollment", "vision", "dental", "hearing",
        ],
        "general_inquiry": [
            "help", "information", "question", "inquiry", "assist",
        ],
    }

    POSITIVE_WORDS = ["thank you", "great", "good", "helpful", "nice"]
    NEGATIVE_WORDS = [
        "problem", "issue", "not working", "bad", "terrible",
        "frustrated", "angry", "upset",
    ]
    CONFUSION_WORDS = ["confused", "don't know", "not sure", "can't remember"]

    @staticmethod
    def normalize_text(text: str) -> str:
        return " ".join((text or "").split()).strip()

    @classmethod
    def detect_intent(cls, transcript_text: str) -> str:
        text = cls.normalize_text(transcript_text).lower()

        if not text:
            return "general_inquiry"

        insurance_priority_words = [
            "medicare", "insurance", "plan", "coverage",
            "kaiser", "benefits", "enrollment",
        ]
        if any(word in text for word in insurance_priority_words):
            return "insurance_inquiry"

        scores = {}
        for intent, keywords in cls.INTENT_KEYWORDS.items():
            scores[intent] = sum(1 for keyword in keywords if keyword in text)

        best_intent = max(scores, key=scores.get)
        if scores[best_intent] == 0:
            return "general_inquiry"
        return best_intent

    @classmethod
    def detect_sentiment(cls, transcript_text: str) -> str:
        text = cls.normalize_text(transcript_text).lower()

        if not text:
            return "neutral"
        if any(word in text for word in cls.CONFUSION_WORDS):
            return "neutral"
        if any(word in text for word in cls.NEGATIVE_WORDS):
            return "negative"
        if any(word in text for word in cls.POSITIVE_WORDS):
            return "positive"
        return "neutral"

    @classmethod
    def compute_confidence(cls, transcript_text: str, intent: str) -> float:
        text = cls.normalize_text(transcript_text).lower()
        if not text:
            return 0.35

        intent_hits = sum(1 for keyword in cls.INTENT_KEYWORDS.get(intent, []) if keyword in text)
        sentiment_hits = sum(1 for word in cls.POSITIVE_WORDS + cls.NEGATIVE_WORDS if word in text)
        word_count = len(text.split())

        base = 0.40 if intent == "general_inquiry" else 0.58
        score = base + (intent_hits * 0.08) + (sentiment_hits * 0.03) + min(word_count / 100.0, 0.18)

        return round(min(score, 0.97), 2)

    @staticmethod
    def get_guidance(transcript_text: str, intent: str, sentiment: str) -> str:
        text = " ".join((transcript_text or "").split()).lower()

        rules = GuidanceRule.objects.filter(is_active=True).select_related("category").order_by("priority")

        best_rule = None
        best_score = 0

        for rule in rules:
            keywords = [k.strip().lower() for k in rule.condition_keywords.split(",") if k.strip()]
            score = sum(1 for keyword in keywords if keyword in text)

            if score > best_score:
                best_score = score
                best_rule = rule

        if best_rule and best_score > 0:
            return best_rule.guidance_text

        if intent == "insurance_inquiry":
            return (
                "Confirm the caller's plan name, member details, and the exact benefit they are asking about. "
                "Do not promise coverage until the plan details are verified."
            )
        if intent == "billing":
            return (
                "Confirm the billing period, disputed amount, and whether the caller is asking for explanation or refund. "
                "Avoid promising reversal before verification."
            )
        if intent == "technical_issue":
            return (
                "Ask clarifying troubleshooting questions, confirm the affected device or service, "
                "and guide the caller through the next diagnostic step."
            )
        if sentiment == "negative":
            return "Acknowledge the caller's frustration, stay calm, and ask one focused clarifying question before offering next steps."

        return "Ask clarifying questions and guide the caller to the next best action."

    @staticmethod
    def generate_summary(transcript_text: str, intent: str, sentiment: str) -> str:
        clean_text = " ".join((transcript_text or "").split())
        if not clean_text:
            return "No meaningful transcript available yet."

        short_text = clean_text[:500]
        return f"Call intent detected as '{intent}' with sentiment '{sentiment}'. Summary: {short_text}"

    @classmethod
    def analyze_call(cls, call):
        chunks = TranscriptChunk.objects.filter(call=call, is_partial=False).order_by("sequence_number", "created_at")

        transcript_text = " ".join(
            cls.normalize_text(chunk.text)
            for chunk in chunks
            if cls.normalize_text(chunk.text)
        ).strip()

        intent = cls.detect_intent(transcript_text)
        sentiment = cls.detect_sentiment(transcript_text)
        confidence = cls.compute_confidence(transcript_text, intent)
        guidance = cls.get_guidance(transcript_text, intent, sentiment)
        summary = cls.generate_summary(transcript_text, intent, sentiment)

        analysis, _ = CallAnalysis.objects.update_or_create(
            call=call,
            defaults={
                "intent": intent,
                "sentiment": sentiment,
                "confidence_score": confidence,
                "guidance_text": guidance,
                "summary": summary,
                "model_name": "hybrid_rule_based_v4",
                "processing_time_seconds": 0.1,
            },
        )

        return analysis