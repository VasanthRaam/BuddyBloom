class SMSService:
    @staticmethod
    def send_otp(phone: str, otp: str):
        """
        Sends an OTP via SMS.
        Currently defaults to Console Mocking for free developer testing.
        Can be upgraded to use Twilio or other providers in the future.
        """
        # MOCK IMPLEMENTATION
        print("="*50)
        print("MOCK SMS SERVICE")
        print(f"To: {phone}")
        print(f"Message: Your BuddyBloom verification code is {otp}. It will expire in 5 minutes.")
        print("="*50)
        return True
