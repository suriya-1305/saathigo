from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SaathiGo"
    secret_key: str = "dev-insecure-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = "sqlite:///./tagalong.db"
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    cors_origins: list[str] = ["http://localhost:5173"]
    upload_dir: str = "uploads"
    static_dir: str | None = None
    max_upload_mb: int = 8
    # Comma-separated emails that get admin rights (Saathi human-review queue) on next request.
    admin_emails: str = ""

    # Pricing is a share of the product value: the traveller who carries/brings it earns 20%,
    # SaathiGo keeps 2%.
    traveller_reward_pct: float = 0.20
    platform_fee_pct: float = 0.02

    shipping_provider: str = "rate_card"

    tesseract_cmd: str | None = None
    boarding_pass_min_score: int = 60
    # Boarding-pass scanning is off by default; any signed-in user can carry or bring orders.
    boarding_pass_enabled: bool = False

    payment_provider: str = "mock"
    pinelabs_env: str = "uat"
    pinelabs_base_url: str | None = None
    pinelabs_client_id: str = ""
    pinelabs_client_secret: str = ""
    pinelabs_merchant_id: str = ""
    pinelabs_webhook_secret: str = ""

    # Pine Labs AgenticOrg ("Saathi" agents). Provider "agenticorg" when a key is set, otherwise rule-based fallbacks.
    agent_provider: str | None = None
    agenticorg_api_key: str = ""
    agenticorg_base_url: str = "https://agenticorg.hackathon.pinelabs.com"
    agenticorg_timeout_s: float = 90.0
    agent_concierge_id: str = "4459bfd0-2217-4675-ae00-62f5b2d4e828"
    agent_intake_id: str = "43892aba-712a-4430-a30f-37ad3173d674"
    agent_dabba_curator_id: str = "1b9a33df-6bb0-4949-8d79-d487bae00bc0"
    agent_compliance_id: str = "3af13765-0a70-4095-b95f-5ca50af326ea"
    agent_matching_id: str = "9f7ec8b1-4f18-4c15-a259-9a107c160205"
    agent_negotiation_id: str = "88f00fe0-c6a5-4a2e-a842-e7e2f649b032"
    agent_tracking_support_id: str = "bbfbb8b9-652f-4eaa-8e88-e8a52aeaf6dd"

    @property
    def agents_enabled(self) -> bool:
        provider = self.agent_provider or ("agenticorg" if self.agenticorg_api_key else "mock")
        return provider == "agenticorg" and bool(self.agenticorg_api_key)

    @property
    def pinelabs_api_base(self) -> str:
        if self.pinelabs_base_url:
            return self.pinelabs_base_url.rstrip("/")
        return "https://api.pluralpay.in" if self.pinelabs_env == "prod" else "https://pluraluat.v2.pinepg.in"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
