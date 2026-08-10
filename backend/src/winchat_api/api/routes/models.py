"""The model catalogue. An allowlist, so a client cannot name an arbitrary model."""

from fastapi import APIRouter
from pydantic import BaseModel

from winchat_api.config import get_settings

router = APIRouter(prefix="/api", tags=["models"])


class ModelInfo(BaseModel):
    id: str
    is_default: bool
    is_eval_reference: bool


class ModelsResponse(BaseModel):
    provider: str
    models: list[ModelInfo]
    # Named explicitly: users may pick freely, but a quality claim is only coherent if it
    # says which model produced it. The eval is always run against this one.
    eval_reference: str


@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    settings = get_settings()
    return ModelsResponse(
        provider=settings.llm_provider,
        eval_reference=settings.eval_model,
        models=[
            ModelInfo(
                id=model,
                is_default=model == settings.llm_model,
                is_eval_reference=model == settings.eval_model,
            )
            for model in settings.allowed_models
        ],
    )
