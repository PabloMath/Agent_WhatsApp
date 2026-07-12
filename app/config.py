from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    groq_api_key: str
    whatsapp_token: str
    whatsapp_phone_id: str
    whatsapp_verify_token: str
    mp_access_token: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str
    base_url: str = "http://localhost:8000"
    
    # 1. Agregamos la variable que faltaba para solucionar el error de Pydantic
    postgres_db: str = "salesbot" 

    class Config:
        env_file = ".env"
        # 2. Con esto, si tienes más variables extras en tu .env, Pydantic las ignorará en vez de romper el código
        extra = "ignore" 

settings = Settings()