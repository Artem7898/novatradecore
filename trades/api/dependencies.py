from trades.services.risk_engine import RiskEngineService

# В реальном django-nova это делает контейнер, здесь используем простую фабрику
def get_risk_service() -> RiskEngineService:
    return RiskEngineService()