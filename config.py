"""
Koko Configuration Manager - Secure Settings Loader
Loads configuration from .env file with fallback to defaults.
NEVER commit .env to version control!
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class KokoConfig:
    """Central configuration manager for all Koko services."""
    
    # Base directories
    BASE_KOKO_DIR = r"C:\Users\gooze\Downloads"
    COMFY_OUTPUT_DIR = r"C:\Users\gooze\Documents\ComfyUI\output"
    
    # Google Gemini API
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
    GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    ALLOWED_CHAT_IDS = ["8712716947"]
    
    # Local LLM Settings
    LOCAL_LLM_BASE = os.getenv('LOCAL_LLM_BASE', 'http://localhost:8080/v1')
    LOCAL_LLM_API_KEY = os.getenv('LOCAL_LLM_API_KEY', 'local')
    LOCAL_LLM_MODEL = os.getenv('LOCAL_LLM_MODEL', 'qwen-35b-local')
    
    # Coder LLM Settings  
    CODER_LLM_BASE = os.getenv('CODER_LLM_BASE', 'http://localhost:8081/v1')
    CODER_LLM_API_KEY = os.getenv('CODER_LLM_API_KEY', 'local')
    CODER_LLM_MODEL = os.getenv('CODER_LLM_MODEL', 'glm-4-flash')
    
    # Validation - ensure critical config exists
    def validate(self):
        """Check if all required configuration is present."""
        missing = []
        
        if not self.GEMINI_API_KEY or self.GEMINI_API_KEY == 'YOUR_GEMINI_API_KEY_HERE':
            missing.append('GEMINI_API_KEY - Get yours from Google Cloud Console')
            
        if not self.TELEGRAM_BOT_TOKEN or self.TELEGRAM_BOT_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN_HERE':
            missing.append('TELEGRAM_BOT_TOKEN - Create a bot via @BotFather on Telegram')
            
        if missing:
            raise ValueError("Missing required configuration:\n" + "\n".join(missing))
        
        return True
    
    def get_config_dict(self):
        """Export current config as dictionary (for backward compatibility)."""
        return {
            "gemini": {
                "api_key": self.GEMINI_API_KEY,
                "api_base": self.GEMINI_API_BASE,
                "model": self.GEMINI_MODEL
            },
            "telegram": {
                "bot_token": self.TELEGRAM_BOT_TOKEN,
                "allowed_chat_ids": self.ALLOWED_CHAT_IDS
            },
            "local_llm": {
                "api_base": self.LOCAL_LLM_BASE,
                "api_key": self.LOCAL_LLM_API_KEY,
                "model": self.LOCAL_LLM_MODEL
            },
            "coder_llm": {
                "api_base": self.CODER_LLM_BASE,
                "api_key": self.CODER_LLM_API_KEY,
                "model": self.CODER_LLM_MODEL
            }
        }

# Usage Example:
if __name__ == "__main__":
    config = KokoConfig()
    
    # Validate configuration before using
    try:
        config.validate()
        print("✅ Configuration validated successfully!")
        
        # Show current settings (without exposing secrets)
        config_dict = config.get_config_dict()
        for section, settings in config_dict.items():
            print(f"\n📁 {section}:")
            for key, value in settings.items():
                # Mask sensitive values
                if any(s in str(value).lower() for s in ['key', 'token']):
                    display = value[:10] + '...' if len(str(value)) > 10 else '***'
                    print(f"   {key}: {display}")
                else:
                    print(f"   {key}: {value}")
                    
    except ValueError as e:
        print(f"\n❌ Configuration Error:\n{e}")
        print("\n📝 Instructions:")
        print("1. Copy .env.example to .env")
        print("2. Fill in your actual API keys and tokens")
        print("3. NEVER commit .env to version control!")
