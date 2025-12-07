import json
import logging
from openai import OpenAI
from src.config import settings

log = logging.getLogger(__name__)

class AIAgent:
	def __init__(self):
		self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
		
	async def analyze_message(self, text: str) -> dict:
		if not self.client: return {"is_spam": False, "is_membership": False}
		if len(text) < 5: return {"is_spam": True, "spam_reason": "Too short", "is_membership": False}

		system_prompt = (
			"You are the Atrioly Intelligent Filter. \n"
			"1. SECURITY: Detect SPAM (phishing, crypto, ads, NSFW, noise).\n"
			"2. INTELLIGENCE: Detect Streaming Membership Sharing offers (Netflix, Disney+, YouTube, etc).\n"
			"Output PURE JSON: {is_spam(bool), spam_reason(str), is_membership(bool), platform(str), summary(str)}"
		)

		try:
			response = self.client.chat.completions.create(
				model=settings.DEFAULT_MODEL,
				messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": text}],
				response_format={"type": "json_object"},
				temperature=0.3
			)
			return json.loads(response.choices[0].message.content)
		except Exception as e:
			log.error(f"AI Error: {e}")
			return {"is_spam": False, "is_membership": False}

agent = AIAgent()
