import World.ChallengeEvaluation
import Bridge

namespace P3.CAL3_I_E87C49876088749B

theorem sq_nonneg' (n : Int) : 0 ≤ n * n := by
  rcases Int.le_total 0 n with h | h
  · exact Int.mul_nonneg h h
  · have h' : 0 ≤ -n := Int.neg_nonneg.mpr h
    have hmul := Int.mul_nonneg h' h'
    simp only [Int.neg_mul, Int.mul_neg, Int.neg_neg] at hmul
    exact hmul

theorem evaluation_solution : Holdout1Statement := by
  intro a b h
  have hb := oracle_bridge h
  have ha := sq_nonneg' a
  have hb2 := sq_nonneg' b
  simp only [balance, start] at hb
  grind

end P3.CAL3_I_E87C49876088749B
