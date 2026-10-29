import World.ChallengeEvaluation
import Bridge

namespace P3.CAL3_I_E87C49876088749B

theorem sq_nonneg' (a : Int) : 0 ≤ a * a := by
  rcases Int.le_total 0 a with h | h
  · exact Int.mul_nonneg h h
  · have h' : 0 ≤ -a := by omega
    have hm := Int.mul_nonneg h' h'
    have e : -a * -a = a * a := Int.neg_mul_neg a a
    rw [e] at hm
    exact hm

theorem evaluation_solution : Holdout1Statement := by
  intro a b h
  have hb := oracle_bridge h
  have h1 := sq_nonneg' a
  have h2 := sq_nonneg' b
  simp only [balance, start] at hb
  grind

end P3.CAL3_I_E87C49876088749B
