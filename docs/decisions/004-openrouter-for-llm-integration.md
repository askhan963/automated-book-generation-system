# 004 - Use OpenRouter for LLM Integration

## Status
Accepted

## Context
We needed to select an approach for integrating Large Language Models (LLMs) for book outline and chapter generation. Requirements included:
- Access to high-quality text generation models
- Flexibility to switch between different model providers
- Cost control and usage monitoring
- Reliable API with good uptime and latency
- Support for various model sizes and capabilities
- Easy integration with existing codebase
- Potential for future fine-tuning or custom models

Options evaluated:
- Direct OpenAI API integration (strong but vendor-locked)
- Direct Anthropic API integration (good but single provider)
- Hugging Face Inference API (open models but variable quality)
- Replicate API (community models but less consistent)
- OpenRouter (unified API for multiple LLM providers)
- Self-hosted models (maximum control but significant ops overhead)
- Azure OpenAI Service (enterprise-focused but complex setup)

## Decision
Selected OpenRouter as the LLM integration layer because it provides:
- Unified API interface to multiple LLM providers (OpenAI, Anthropic, Google, etc.)
- Ability to switch models without changing integration code
- Competitive pricing and access to various model tiers
- Standardized OpenAI-compatible API format
- Fallback capabilities if one provider experiences issues
- Usage tracking and analytics across providers
- Access to both cutting-edge and cost-effective models
- Simple authentication with single API key
- Active development and growing provider support
- Reduced vendor lock-in risk

## Consequences
### Positive
- Flexibility to use different models for different tasks (e.g., stronger model for outlines, faster/cheaper for chapters)
- Ability to optimize for cost vs. quality based on subscription tier
- Standardized interface reduces integration complexity
- Provider redundancy improves reliability
- Access to emerging models without new integrations
- Transparent pricing and usage metrics
- Easy to add new providers as they become available

### Negative
- Additional abstraction layer (small potential latency overhead)
- Dependency on OpenRouter service availability and performance
- Less direct control over provider-specific features
- Potential for provider-specific quirks or limitations
- Need to manage API key for OpenRouter instead of individual providers

### Neutral
- Uses OpenAI-compatible API format we would likely use anyway
- Can still target specific providers when needed through model selection
- Falls back to direct provider integration if OpenRouter service issues arise

## Related Documents
- [API.md](../API.md) - API contract showing AI service endpoints
- Source code in `app/services/ai_service.py` (OpenRouter/OpenAI integration)
- Source code in `app/core/config.py` (LLM-related configuration settings)
- Source code in `app/models.py` (AI-related request/response models)
- Configuration documentation showing OpenRouter setup