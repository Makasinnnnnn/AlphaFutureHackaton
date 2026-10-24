// Illustrative totals only: the signed agreement contains the rounded schedule.
export function repaymentEstimate(amount: number, payment: number, term: number, overdraft: boolean) {
  if (overdraft || ![amount, payment, term].every(Number.isFinite) || amount <= 0 || payment <= 0 || !Number.isInteger(term) || term <= 0) return null;
  const total = payment * term;
  if (!Number.isFinite(total) || total < amount) return null;
  return { total: Number(total.toFixed(2)), interest: Number((total - amount).toFixed(2)) };
}
