import World.ChallengeEvaluation
import Bridge

namespace P3.CAL3_I_E87C49876088749B

theorem evaluation_solution : Holdout2Statement := by
  intro a h
  have h2 : balance start = balance ⟨a + (-2), a + (1), a + (-4)⟩ := oracle_bridge h
  simp only [balance, start] at h2
  grind

end P3.CAL3_I_E87C49876088749B
