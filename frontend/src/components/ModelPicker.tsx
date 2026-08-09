"use client";

import { useQuery } from "@tanstack/react-query";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchModels } from "@/lib/api/client";

/**
 * Model selector. The list comes from the API and is never hard-coded here: the backend owns
 * the allowlist, and a client-side copy would drift from what the server will actually
 * accept.
 */
export function ModelPicker({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (model: string | null) => void;
}) {
  const { data } = useQuery({
    queryKey: ["models"],
    queryFn: ({ signal }) => fetchModels({ signal }),
  });

  const models = data?.models ?? [];
  if (models.length <= 1) return null;

  const selected =
    value ?? models.find((model) => model.is_default)?.id ?? models[0].id;

  return (
    <Select value={selected} onValueChange={onChange}>
      <SelectTrigger
        size="sm"
        aria-label="Language model"
        className="flex min-w-0 max-w-[7.5rem] shrink font-mono text-xs sm:max-w-[13rem]"
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="end">
        {models.map((model) => (
          <SelectItem
            key={model.id}
            value={model.id}
            className="font-mono text-xs"
          >
            {model.id}
            {model.is_eval_reference && (
              <span className="ml-1.5 font-sans text-[10px] text-muted-foreground">
                eval reference
              </span>
            )}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
