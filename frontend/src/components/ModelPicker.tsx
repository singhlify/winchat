"use client";

import { useEffect, useState } from "react";

import { fetchModels, type ModelInfo } from "@/lib/chat";

/**
 * Model selector.
 *
 * The list comes from the API, never hard-coded here: the backend owns the allowlist, and
 * a client-side list would drift from what the server will actually accept.
 *
 * The eval reference model is labelled. Users can pick freely, but every published quality
 * number was measured on one specific model, and the UI should not let those two facts
 * blur together.
 */
export function ModelPicker({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (model: string | null) => void;
}) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [reference, setReference] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchModels().then(
      (catalogue) => {
        if (cancelled) return;
        setModels(catalogue.models);
        setReference(catalogue.eval_reference);
      },
      () => {
        // A missing catalogue just hides the picker; the backend default still applies.
        if (!cancelled) setModels([]);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  if (models.length <= 1) return null;

  const selected = value ?? models.find((model) => model.is_default)?.id ?? models[0].id;

  return (
    <label className="flex items-center gap-1.5 text-xs text-neutral-500">
      <span className="sr-only">Model</span>
      <select
        value={selected}
        onChange={(event) => onChange(event.target.value)}
        className="rounded border border-neutral-300 bg-transparent px-1.5 py-1 text-xs dark:border-neutral-700"
      >
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {model.id}
            {model.id === reference ? " (eval reference)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
