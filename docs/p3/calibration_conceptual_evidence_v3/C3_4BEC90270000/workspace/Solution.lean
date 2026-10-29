import World.ChallengeEvaluation
import Bridge

namespace P3.CAL3_I_E87C49876088749B

theorem mul_self_nonneg' (a : Int) : 0 ≤ a * a := by
  rcases (show 0 ≤ a ∨ 0 ≤ -a by omega) with h | h
  · exact Int.mul_nonneg h h
  · have hm : 0 ≤ (-a) * (-a) := Int.mul_nonneg h h
    have e : (-a) * (-a) = a * a := by grind
    rw [e] at hm
    exact hm

theorem evaluation_solution : Holdout1Statement := by
  intro a b h
  have hb := oracle_bridge h
  have ha := mul_self_nonneg' a
  have hbb := mul_self_nonneg' b
  simp only [balance, start] at hb
  grind
