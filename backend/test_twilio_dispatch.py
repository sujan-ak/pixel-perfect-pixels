import os
from dotenv import load_dotenv

load_dotenv()

def test_twilio():
    twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    dispatch_to = os.getenv("TWILIO_DISPATCH_TO") or "+910000000000"
    whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    sms_body = "TEST VERIFIED INCIDENT Zone 04 — severity 0.92 — AuraShield automated test"

    print("Testing Twilio WhatsApp dispatch...")
    print(f"From: {whatsapp_from}")
    print(f"To: whatsapp:{dispatch_to}")

    try:
        from twilio.rest import Client
        client = Client(twilio_account_sid, twilio_auth_token)
        msg = client.messages.create(
            to=f"whatsapp:{dispatch_to}",
            from_=whatsapp_from,
            body=sms_body,
        )
        print(f"SUCCESS: WhatsApp message sent! SID: {msg.sid}, status: {msg.status}")
        return True, msg.sid
    except Exception as e:
        print(f"FAILED: {e}")
        return False, str(e)

if __name__ == "__main__":
    test_twilio()
