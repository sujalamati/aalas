from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:password@localhost:5432/postgres"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    linkedin_provider: str = "linkedin_jobs_api"
    job_search_limit: int = 25
    scheduler_enabled: bool = True
    timezone: str = "Asia/Kolkata"
    latex_engine: str = "pdflatex"  # tectonic or pdflatex
    generated_dir: str = "generated"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
