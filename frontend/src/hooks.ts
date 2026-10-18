import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";

/** Polled system status shared by the layout pill and the Status page. */
export function useSystemStatus(refetchMs = 20_000) {
  return useQuery({
    queryKey: ["system-status"],
    queryFn: ({ signal }) => api.status(signal),
    refetchInterval: refetchMs,
    retry: false,
    staleTime: 5_000,
  });
}
