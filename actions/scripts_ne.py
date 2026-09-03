from __future__ import annotations

VOICE_TEMPLATE_NE = (
    "{settlement}का बासिन्दाहरू ध्यान दिनुहोस्। बाढीको जोखिम बढेको छ। "
    "अनुमानित समय {lead_time} मिनेट भित्र पानी आउन सक्छ। "
    "कृपया तुरुन्त सुरक्षित र अग्लो ठाउँमा सर्नुहोस्। यो एक स्वचालित सन्देश हो।"
)

SMS_TEMPLATE_NE = (
    "{settlement}: बाढी जोखिम {status}। {lead_time} मिनेटमा पानी आउन सक्छ। सुरक्षित ठाउँमा जानुहोस्।"
)

SMS_MAX_CHARS = 140


def voice_script(settlement: str, lead_time_minutes: float | None) -> str:
    lead = f"{lead_time_minutes:.0f}" if lead_time_minutes is not None else "अज्ञात"
    return VOICE_TEMPLATE_NE.format(settlement=settlement, lead_time=lead)


def sms_text(settlement: str, status_np: str, lead_time_minutes: float | None) -> str:
    lead = f"{lead_time_minutes:.0f}" if lead_time_minutes is not None else "अज्ञात"
    text = SMS_TEMPLATE_NE.format(settlement=settlement, status=status_np, lead_time=lead)
    return text[:SMS_MAX_CHARS]
