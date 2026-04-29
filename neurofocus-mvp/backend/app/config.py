"""
Configuration de l'application et gestion des variables d'environnement.
Utilise pydantic-settings pour une validation stricte des configs.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Configuration globale de l'application NeuroFocus."""
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./neurofocus_dev.db"
    
    # Application
    app_name: str = "NeuroFocus MVP"
    debug: bool = True
    
    # CORS
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
