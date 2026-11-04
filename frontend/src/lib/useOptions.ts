import { useEffect, useState } from "react";
import { api } from "./api";

export interface AccountOptions {
  experience_levels: { value: string; label: string }[];
  timezones: string[];
}

let cache: AccountOptions | null = null;

/** Choices for the signup and profile forms, loaded once from the API. */
export function useAccountOptions(): AccountOptions | null {
  const [options, setOptions] = useState<AccountOptions | null>(cache);
  useEffect(() => {
    if (cache) return;
    void api.get<AccountOptions>("/api/account/options").then((res) => {
      if (res.ok) {
        cache = res.data;
        setOptions(res.data);
      }
    });
  }, []);
  return options;
}
