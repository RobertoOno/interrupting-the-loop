import World.ChallengeEvaluation
import Bridge

namespace P3.CAL3_I_E87C49876088749B

theorem evaluation_solution : Holdout2Statement := by
  intro a h
  have hb := oracle_bridge h
  have h1 : balance start = 13 := by decide
  have h2 : balance ⟨a + (-2), a + (1), a + (-4)⟩ = 0 := by
    show (a + (-2) - (-2)) * (a + (-4) - (-4)) - (a + (1) - (1)) * (a + (1) - (1)) = 0
    have e1 : a + (-2) - (-2) = a := by omega
    have e2 : a + (-4) - (-4) = a := by omega
    have e3 : a + (1) - (1) = a := by omega
    rw [e1, e2, e3, Int.sub_self]
  rw [h1, h2] at hb
  exact absurd hb (by omega)

end P3.CAL3_I_E87C49876088749B
