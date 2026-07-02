import { useQuery } from "@tanstack/react-query";
import { fetchTossAccounts } from "../api/client";

/**
 * 트레이딩 계좌 훅.
 * 백엔드에서 TRADING_ENABLED=false 면 /api/account 가 404 → available=false.
 */
export function useTradingAccount() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["toss-accounts"],
    queryFn: fetchTossAccounts,
    staleTime: Infinity,
    retry: 0,
  });

  const account = data && data.length > 0 ? data[0] : null;

  return {
    available: !isError && account != null,
    loading: isLoading,
    account,
    accountSeq: account?.account_seq ?? null,
  };
}
