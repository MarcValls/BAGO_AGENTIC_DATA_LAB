export const PROVIDER_RESPONSE_OBSERVED_EVENT = 'bago:provider-response-observed'

export type ProviderResponseObservation = {
  provider_id: string
  model_id: string
  observed_at: string
}

export function readProviderResponseObservation(value: unknown): ProviderResponseObservation | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const item = value as Record<string, unknown>
  if (typeof item.provider_id !== 'string' || !item.provider_id.trim() || typeof item.model_id !== 'string' || !item.model_id.trim()) return null
  if (typeof item.observed_at !== 'string' || !/^\d{4}-\d{2}-\d{2}T.*Z$/.test(item.observed_at) || !Number.isFinite(Date.parse(item.observed_at))) return null
  return {provider_id: item.provider_id, model_id: item.model_id, observed_at: item.observed_at}
}
