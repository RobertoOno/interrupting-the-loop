import World.ChallengeEvaluation
import Bridge

namespace P3.CAL3_I_E87C49876088749B

theorem evaluation_solution : Holdout2Statement := by
  intro a h
  have h2 := oracle_bridge h
  have e0 : balance ⟨a + (-2), a + (1), a + (-4)⟩ = 0 := by
    show (a + (-2) - (-2)) * (a + (-4) - (-4)) - (a + (1) - (1)) * (a + (1) - (1)) = 0
    have e1 : a + (-2) - (-2) = a := by omega
    have e2 : a + (-4) - (-4) = a := by omega
    have e3 : a + (1) - (1) = a := by omega
    rw [e1, e2, e3, Int.sub_self]
  rw [e0] at h2
  have hs : balance start = 13 := by decide
  rw [hs] at h2
  exact absurd h2 (by decide)

end P3.CAL3_I_E87C49876088749B
