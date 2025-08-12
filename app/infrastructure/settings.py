from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str
    secret_key: str
    openai_api_key: str | None
    openai_model: str 
    max_preview_rows: int = 5
    allow_dangerous_code: bool = True   
    database_url: str
    
    class Config:
        env_file = ".env"
        
settings = Settings()
